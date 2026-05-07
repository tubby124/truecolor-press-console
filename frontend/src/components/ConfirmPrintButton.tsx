import { useState } from "react";
import { api } from "../api";
import { useStore } from "../store";

export function ConfirmPrintButton() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const trays = useStore((s) => s.trays);
  const pushToast = useStore((s) => s.pushToast);
  const [confirming, setConfirming] = useState<null | "qty">(null);

  if (stage.kind !== "inspected") return null;

  const blocking = stage.result.findings.some((f) => f.severity === "block");
  const trayMatch =
    !trays?.configured ||
    Object.values(trays.trays).some((t) => t.stock_code === stage.stockCode);
  const disabled = blocking || !trayMatch;

  async function send() {
    if (stage.kind !== "inspected") return;
    const sheetsNeeded = Math.ceil(stage.quantity / 1); // exact sheet count handled by backend
    setConfirming(null);
    pushToast("info", `Spooling ${stage.file.name}…`);
    setStage({ kind: "submitting", file: stage.file });
    try {
      const job = await api.submitJob({
        file: stage.file,
        workflow: stage.result.detected?.workflow ?? "custom",
        preset_key: stage.presetKey,
        stock_code: stage.stockCode,
        quantity: stage.quantity,
        sides: stage.sides,
      });
      setStage({ kind: "done", job });
      pushToast(
        "success",
        job.status === "spooled-dry"
          ? `Spooled (DRY): ${job.sheets} sheet${job.sheets !== 1 ? "s" : ""}`
          : `Sent to press: ${job.sheets} sheet${job.sheets !== 1 ? "s" : ""}`
      );
    } catch (e) {
      pushToast("error", `Submit failed: ${e instanceof Error ? e.message : e}`);
      setStage(stage);
    }
    void sheetsNeeded;
  }

  function clickHandler() {
    if (stage.kind !== "inspected") return;
    if (stage.quantity > 100) {
      setConfirming("qty");
      return;
    }
    void send();
  }

  return (
    <>
      <button className="cta" type="button" onClick={clickHandler} disabled={disabled} title="⌘ + Enter">
        {disabled
          ? blocking
            ? "Fix blockers above to print"
            : "Load matching paper to print"
          : `Looks good — print ${stage.quantity}`}
      </button>

      {confirming === "qty" && stage.kind === "inspected" && (
        <div className="modal-backdrop" onClick={() => setConfirming(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Confirm large run</h2>
            <p>
              You're about to print <strong>{stage.quantity}</strong> finished pieces. That's a real
              chunk of paper and clicks. Proceed?
            </p>
            <div className="modal-actions">
              <button className="cta secondary" type="button" onClick={() => setConfirming(null)}>
                Cancel
              </button>
              <button className="cta" type="button" onClick={send}>
                Yes, print {stage.quantity}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
