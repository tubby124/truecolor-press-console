import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import { TILES } from "../workflows/tiles";

const ACCEPTED = [".pdf", ".ai", ".psd", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".eps"];
const BLOCKED_HINT: Record<string, string> = {
  ".docx": "Save the Word doc as PDF first (File → Save As → PDF).",
  ".pptx": "Save the PowerPoint as PDF first (File → Export → Create PDF).",
  ".xlsx": "Save the Excel as PDF first.",
};

export function DropZone() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const pushToast = useStore((s) => s.pushToast);
  const fileRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (BLOCKED_HINT[ext]) {
        pushToast("error", `${ext} isn't supported. ${BLOCKED_HINT[ext]}`);
        return;
      }
      if (!ACCEPTED.includes(ext)) {
        pushToast("error", `File type ${ext} isn't supported. Save as PDF first.`);
        return;
      }
      setStage({ kind: "inspecting", file });

      // Read pre-selected tile or saved preset (set by WorkflowTiles / SavedPresets).
      const preTile = document.body.dataset.preselectedTile;
      const presetJson = document.body.dataset.savedPresetJson;
      delete document.body.dataset.preselectedTile;
      delete document.body.dataset.savedPresetJson;

      try {
        const result = await api.inspect(file, 100);
        let stockCode = result.detected?.stock_code ?? "14pt-cs-gloss";
        let presetKey = result.detected?.preset_key ?? "bc_21up_12x18";
        let quantity = result.suggested_quantity;
        let sides: 1 | 2 = 1;

        // Saved-preset override takes priority over tile pre-select
        if (presetJson) {
          try {
            const sp = JSON.parse(presetJson) as {
              preset_key: string;
              stock_code: string;
              quantity: number;
              sides: number;
            };
            stockCode = sp.stock_code;
            presetKey = sp.preset_key;
            quantity = sp.quantity;
            sides = sp.sides === 2 ? 2 : 1;
          } catch {
            // ignore malformed
          }
        } else if (preTile && !preTile.startsWith("saved:")) {
          const tile = TILES.find((t) => t.key === preTile);
          if (tile && tile.presetKey) {
            stockCode = tile.defaultStock;
            presetKey = tile.presetKey;
            quantity = tile.defaultQty;
            sides = tile.defaultSides;
          }
        }

        setStage({
          kind: "inspected",
          file,
          result,
          quantity,
          sides,
          stockCode,
          presetKey,
        });
      } catch (e) {
        pushToast("error", `Inspection failed: ${e instanceof Error ? e.message : e}`);
        setStage({ kind: "idle" });
      }
    },
    [pushToast, setStage]
  );

  // Global drag-drop on window so dropping anywhere lands here
  useEffect(() => {
    const onDragOver = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) {
        e.preventDefault();
      }
    };
    const onDrop = (e: DragEvent) => {
      if (!e.dataTransfer?.types.includes("Files")) return;
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) void handleFile(file);
      setOver(false);
    };
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("drop", onDrop);
    };
  }, [handleFile]);

  if (stage.kind !== "idle" && stage.kind !== "inspecting") return null;

  return (
    <div
      className={`dropzone ${over ? "over" : ""} ${stage.kind === "inspecting" ? "busy" : ""}`}
      onClick={() => fileRef.current?.click()}
      onDragEnter={() => setOver(true)}
      onDragLeave={() => setOver(false)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
      }}
    >
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED.join(",")}
        style={{ display: "none" }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />
      {stage.kind === "inspecting" ? (
        <>
          <h2>
            <span className="spinner" /> Reading {stage.file.name}…
          </h2>
          <p>Checking dimensions, fonts, bleed, and color mode.</p>
        </>
      ) : (
        <>
          <h2>Drop a PDF anywhere</h2>
          <p>We'll auto-detect the job type, recommend paper, and quote it.</p>
          <p className="formats">PDF in v1 · PSD / AI / EPS coming in v2 · Word docs: save as PDF first</p>
        </>
      )}
    </div>
  );
}
