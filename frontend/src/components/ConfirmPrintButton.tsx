import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Stock, TrayKey } from "../types";

const TRAY_KEYS: TrayKey[] = ["T1", "T2", "T3", "T4", "T5"];

// Friendly noun for the green print button. Keyed by detected.workflow so the
// button reads "Looks good — print 100 business cards" instead of just "100".
const WORKFLOW_NOUN: Record<string, { one: string; many: string }> = {
  business_card: { one: "business card", many: "business cards" },
  postcard_3x4: { one: "postcard", many: "postcards" },
  postcard_4x6: { one: "postcard", many: "postcards" },
  postcard_5x7: { one: "postcard", many: "postcards" },
  flyer_letter: { one: "flyer", many: "flyers" },
  flyer_half: { one: "flyer", many: "flyers" },
  trifold_brochure: { one: "tri-fold brochure", many: "tri-fold brochures" },
  bifold_brochure: { one: "bi-fold brochure", many: "bi-fold brochures" },
  halffold_card: { one: "card", many: "cards" },
  poster_letter: { one: "poster", many: "posters" },
  poster_11x17: { one: "poster", many: "posters" },
};

function workflowNoun(workflow: string | undefined, qty: number): string | null {
  if (!workflow) return null;
  const entry = WORKFLOW_NOUN[workflow];
  if (!entry) return null;
  return qty === 1 ? entry.one : entry.many;
}

export function ConfirmPrintButton() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const trays = useStore((s) => s.trays);
  const setTrays = useStore((s) => s.setTrays);
  const pushToast = useStore((s) => s.pushToast);
  const [confirming, setConfirming] = useState<null | "qty" | "tray" | "load">(null);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [pickedTray, setPickedTray] = useState<TrayKey>("T1");
  // Operator override on hard blockers. When true, the disabled main button
  // re-enables and the label flips to "(overriding warnings)". Cleared by an
  // effect any time the stage shape changes (kind transition or different
  // file) so the override never carries across jobs.
  const [override, setOverride] = useState(false);
  // Cancel-in-flight: visible while stage=submitting. Auto-disappears 5s
  // after submitting starts OR when stage moves past submitting.
  const [cancelVisible, setCancelVisible] = useState(false);
  // Hold the most recent job_id so the Cancel handler can hit cancel-spool.
  // Set right before stage moves to submitting so the handler doesn't have
  // to read it back from the store mid-update.
  const [inFlightJobId, setInFlightJobId] = useState<string | null>(null);

  useEffect(() => {
    api.stocks().then(setStocks).catch(() => {});
  }, []);

  // Reset the override flag when the operator transitions away from
  // "inspected". Watching stage.kind covers Discard, successful submit, and
  // any other path that exits this card.
  useEffect(() => {
    if (stage.kind !== "inspected") setOverride(false);
  }, [stage.kind]);

  // Cancel-in-flight visibility lifecycle. Show on submitting → hide after
  // 5s OR when stage moves past submitting. The auto-hide is the safety
  // net: by then the job has either spooled or errored, and the cancel
  // endpoint would either succeed silently (dry mode) or 409 (live).
  useEffect(() => {
    if (stage.kind !== "submitting") {
      setCancelVisible(false);
      return;
    }
    setCancelVisible(true);
    const t = window.setTimeout(() => setCancelVisible(false), 5000);
    return () => window.clearTimeout(t);
  }, [stage.kind]);

  if (stage.kind === "submitting") {
    // While submitting, render a minimal Cancel button (the main green CTA
    // is no longer interactive — stage has moved past inspected). The
    // ImposedPreview / SubmittingScreen elsewhere handles spinner + status.
    if (!cancelVisible) return null;
    return (
      <button
        type="button"
        className="cta secondary"
        onClick={async () => {
          if (!inFlightJobId) {
            // Job_id not captured yet (network in flight): nothing to cancel
            // remotely. Just hide the button.
            setCancelVisible(false);
            return;
          }
          try {
            await api.cancelSpool(inFlightJobId);
            pushToast("info", "Cancelled — job dropped.");
            setStage({ kind: "idle" });
          } catch (e) {
            pushToast(
              "warn",
              `Cancel rejected: ${e instanceof Error ? e.message : e}. The press may have already taken it.`,
            );
          } finally {
            setCancelVisible(false);
            setInFlightJobId(null);
          }
        }}
        style={{ fontSize: 13 }}
      >
        Cancel
      </button>
    );
  }

  if (stage.kind !== "inspected") return null;

  const blocking = stage.result.findings.some((f) => f.severity === "block");
  const trayMatch =
    !trays?.configured ||
    Object.values(trays.trays).some((t) => t.stock_code === stage.stockCode);
  // Print is blocked by hard preflight blockers UNLESS the operator has
  // explicitly overridden the warnings. Tray mismatch opens a
  // load-confirmation modal instead of disabling the button.
  const disabled = blocking && !override;
  const stock = stocks.find((s) => s.code === stage.stockCode);
  const recommendedTray = (stock?.default_tray as TrayKey | undefined) ?? "T1";
  const stockLabel = (stock?.friendly_name || stock?.name) ?? stage.stockCode;

  async function send() {
    if (stage.kind !== "inspected") return;
    const sheetsNeeded = Math.ceil(stage.quantity / 1); // exact sheet count handled by backend
    setConfirming(null);
    pushToast("info", `Spooling ${stage.file.name}…`);
    setStage({ kind: "submitting", file: stage.file });
    setInFlightJobId(null);
    try {
      const job = await api.submitJob({
        file: stage.file,
        workflow: stage.result.detected?.workflow ?? "custom",
        preset_key: stage.presetKey,
        stock_code: stage.stockCode,
        quantity: stage.quantity,
        sides: stage.sides,
      });
      // Capture the new job_id so the Cancel button (rendered while stage
      // is "submitting") can call /cancel-spool. Note: the API call has
      // already returned, so cancel will mostly be useful in dry mode for
      // the brief window between response and stage transition.
      setInFlightJobId(job.job_id);
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
    if (!trayMatch && trays?.configured) {
      setPickedTray(recommendedTray);
      setConfirming("load");
      return;
    }
    if (stage.quantity > 100) {
      setConfirming("qty");
      return;
    }
    void send();
  }

  async function confirmLoadAndPrint() {
    if (stage.kind !== "inspected") return;
    try {
      const next = await api.setTray(recommendedTray, {
        stock_code: stage.stockCode,
        paper_size: stock?.parent_sheet ?? null,
        level: "full",
      });
      setTrays(next);
      setConfirming(null);
      pushToast("success", `Marked ${recommendedTray} loaded with ${stockLabel}.`);
      // Chain straight into the print so the operator only confirms once.
      if (stage.quantity > 100) {
        setConfirming("qty");
      } else {
        void send();
      }
    } catch (e) {
      pushToast("error", `Couldn't update tray: ${e instanceof Error ? e.message : e}`);
    }
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
      <button
        data-tour="print-button"
        className="cta"
        type="button"
        onClick={clickHandler}
        disabled={disabled}
        title="⌘ + Enter"
      >
        {blocking && !override
          ? "Fix the issues above first"
          : (() => {
              const noun = workflowNoun(stage.result.detected?.workflow, stage.quantity);
              const label = noun
                ? `Looks good — print ${stage.quantity} ${noun}`
                : `Looks good — print ${stage.quantity}`;
              return blocking && override
                ? `${label} (overriding warnings)`
                : label;
            })()}
      </button>

      {/* Print-anyway escape hatch. Hard blockers in preflight catch real
          issues (corrupt fonts, no pages, etc.) but the operator may know
          something the preflight can't see — the press has already been
          calibrated for this paper, the warning is a known false positive,
          they're running a calibration sheet, etc. The override re-enables
          the main button rather than spawning a separate code path so the
          confirmation flow (qty modal, tray load modal) stays identical. */}
      {blocking && !override && (
        <button
          className="cta secondary"
          type="button"
          onClick={() => setOverride(true)}
          title="Bypass preflight blockers and print anyway"
          style={{ fontSize: 13 }}
        >
          Print anyway, I know
        </button>
      )}

      {!blocking && !trayMatch && trays?.configured && (
        <button
          className="cta secondary"
          type="button"
          onClick={openTrayModal}
          title="Pick a different tray than the recommended one"
          style={{ fontSize: 13 }}
        >
          Different tray…
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

      {confirming === "load" && stage.kind === "inspected" && (
        <div className="modal-backdrop" onClick={() => setConfirming(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Load paper, then tap when done</h2>
            <p style={{ fontSize: 16, lineHeight: 1.55 }}>
              Put <strong>{stockLabel}</strong> in <strong>{recommendedTray}</strong>, then tap the green button below.
            </p>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              The press needs to know which tray has the right paper before it'll print this job.
            </p>
            <div className="modal-actions">
              <button
                className="cta secondary"
                type="button"
                onClick={() => {
                  setConfirming("tray");
                }}
              >
                Different tray…
              </button>
              <span style={{ flex: 1 }} />
              <button className="cta secondary" type="button" onClick={() => setConfirming(null)}>
                Cancel
              </button>
              <button
                className="cta"
                type="button"
                onClick={confirmLoadAndPrint}
                style={{ fontSize: 16, padding: "10px 18px" }}
              >
                Done — print now
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
