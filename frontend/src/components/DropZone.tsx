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

  const validateExt = useCallback(
    (file: File): boolean => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (BLOCKED_HINT[ext]) {
        pushToast("error", `${file.name}: ${BLOCKED_HINT[ext]}`);
        return false;
      }
      if (!ACCEPTED.includes(ext)) {
        pushToast("error", `${file.name}: ${ext} isn't supported. Save as PDF first.`);
        return false;
      }
      return true;
    },
    [pushToast]
  );

  const handleFiles = useCallback(
    async (files: File[]) => {
      const valid = files.filter(validateExt);
      if (valid.length === 0) return;
      if (valid.length > 1) {
        // Multi-file → batch flow. Skip per-file inspection; user picks one
        // workflow + paper that applies to all. Defaults match the single-file
        // happy path (21-up business cards on 14pt cardstock).
        setStage({
          kind: "batch_pending",
          files: valid,
          quantity: 100,
          sides: 1,
          stockCode: "14pt-cs-gloss",
          presetKey: "bc_21up_12x18",
        });
        return;
      }
      const file = valid[0];
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
    [pushToast, setStage, validateExt]
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
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) void handleFiles(files);
      setOver(false);
    };
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("drop", onDrop);
    };
  }, [handleFiles]);

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
        multiple
        style={{ display: "none" }}
        onChange={(e) => {
          const files = e.target.files ? Array.from(e.target.files) : [];
          if (files.length > 0) void handleFiles(files);
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
          <p className="formats">
            Drop one to inspect, or multiple to batch · PDF / AI / PSD / PNG / JPG / TIFF / EPS · Word docs: save as PDF first
          </p>
        </>
      )}
    </div>
  );
}
