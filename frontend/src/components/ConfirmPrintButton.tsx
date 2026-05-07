import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Stock, TrayKey } from "../types";

const TRAY_KEYS: TrayKey[] = ["T1", "T2", "T3", "T4", "T5"];

export function ConfirmPrintButton() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const trays = useStore((s) => s.trays);
  const setTrays = useStore((s) => s.setTrays);
  const pushToast = useStore((s) => s.pushToast);
  const [confirming, setConfirming] = useState<null | "qty" | "tray">(null);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [pickedTray, setPickedTray] = useState<TrayKey>("T1");

  useEffect(() => {
    api.stocks().then(setStocks).catch(() => {});
  }, []);

  if (stage.kind !== "inspected") return null;

  const blocking = stage.result.findings.some((f) => f.severity === "block");
  const trayMatch =
    !trays?.configured ||
    Object.values(trays.trays).some((t) => t.stock_code === stage.stockCode);
  const disabled = blocking || !trayMatch;
  const stock = stocks.find((s) => s.code === stage.stockCode);
  const recommendedTray = (stock?.default_tray as TrayKey | undefined) ?? "T1";

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

  function openTrayModal() {
    if (stage.kind !== "inspected") return;
    setPickedTray(recommendedTray);
    setConfirming("tray");
  }

  async function markTrayLoaded() {
    if (stage.kind !== "inspected") return;
    try {
      const next = await api.setTray(pickedTray, {
        stock_code: stage.stockCode,
        paper_size: stock?.parent_sheet ?? null,
        level: "full",
      });
      setTrays(next);
      setConfirming(null);
      pushToast("success", `Marked ${pickedTray} loaded with ${(stock?.friendly_name || stock?.name) ?? stage.stockCode}.`);
    } catch (e) {
      pushToast("error", `Couldn't update tray: ${e instanceof Error ? e.message : e}`);
    }
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

      {!blocking && !trayMatch && trays?.configured && (
        <button
          className="cta secondary"
          type="button"
          onClick={openTrayModal}
          title={`Mark a tray as loaded with ${(stock?.friendly_name || stock?.name) ?? stage.stockCode}`}
        >
          Just loaded it
        </button>
      )}

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

      {confirming === "tray" && stage.kind === "inspected" && (
        <div className="modal-backdrop" onClick={() => setConfirming(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Mark tray as loaded</h2>
            <p>
              Which tray did you put <strong>{(stock?.friendly_name || stock?.name) ?? stage.stockCode}</strong> in?
              {recommendedTray && ` (${recommendedTray} is recommended for this stock.)`}
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0" }}>
              {TRAY_KEYS.map((t) => {
                const cur = trays?.trays[t];
                const occupied = cur?.stock_code && cur.stock_code !== stage.stockCode;
                return (
                  <label
                    key={t}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 4,
                      padding: "8px 14px",
                      border: `1px solid ${pickedTray === t ? "var(--accent)" : "var(--border)"}`,
                      borderRadius: 8,
                      cursor: "pointer",
                      background: pickedTray === t ? "var(--panel-2)" : "transparent",
                      minWidth: 70,
                    }}
                  >
                    <input
                      type="radio"
                      name="tray-pick"
                      value={t}
                      checked={pickedTray === t}
                      onChange={() => setPickedTray(t)}
                      style={{ display: "none" }}
                    />
                    <strong>{t}</strong>
                    {occupied ? (
                      <span style={{ color: "var(--warn)", fontSize: 11 }}>
                        currently {cur?.stock_code}
                      </span>
                    ) : cur?.stock_code === stage.stockCode ? (
                      <span style={{ color: "var(--success)", fontSize: 11 }}>already set</span>
                    ) : (
                      <span style={{ color: "var(--muted)", fontSize: 11 }}>empty</span>
                    )}
                  </label>
                );
              })}
            </div>
            <div className="modal-actions">
              <button className="cta secondary" type="button" onClick={() => setConfirming(null)}>
                Cancel
              </button>
              <button className="cta" type="button" onClick={markTrayLoaded}>
                Mark {pickedTray} loaded
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
