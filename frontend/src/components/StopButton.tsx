import { useState } from "react";
import { api } from "../api";
import { useStore } from "../store";

// Always-visible kill switch in the topbar. Hits POST /api/stop, which:
//   1. Deletes any pending / spooled-dry job dirs the app still owns.
//   2. Sends @PJL JOB CANCEL to the press (best effort — sheets already
//      past the imaging unit will still come out).
//   3. On Windows: purges every configured print queue via Remove-PrintJob.
// Per-layer outcome is reported as toasts so the operator can see exactly
// what was stopped (or why a layer failed). Confirm modal on first press so
// nobody nukes a 500-piece run with a stray click.

export function StopButton() {
  const pushToast = useStore((s) => s.pushToast);
  const reset = useStore((s) => s.reset);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function fire() {
    setBusy(true);
    try {
      const res = await api.stop();
      // Job-level summary
      if (res.cancelled_jobs.length > 0) {
        pushToast(
          "success",
          `Dropped ${res.cancelled_jobs.length} pending job${res.cancelled_jobs.length === 1 ? "" : "s"} (${res.cancelled_jobs.join(", ")}).`,
        );
      }
      for (const f of res.failed_jobs) {
        pushToast("error", `Couldn't remove job ${f.job_id}: ${f.error}`);
      }
      // Printer-level summary
      if (res.printer.sent) {
        pushToast("success", `Sent PJL JOB CANCEL to press @ ${res.printer.host}.`);
      } else if (res.printer.reason) {
        pushToast("info", `Press not contacted (${res.printer.reason}).`);
      } else if (res.printer.error) {
        pushToast(
          "error",
          `Couldn't reach press: ${res.printer.error}. Check the network cable and gateway.`,
        );
      }
      // Spool-level summary (Windows-only)
      if (res.spool.supported) {
        if (res.spool.purged.length > 0) {
          pushToast(
            "success",
            `Purged Windows queues: ${res.spool.purged.join(", ")}.`,
          );
        }
        for (const e of res.spool.errors) {
          pushToast("warn", `Spool: ${e}`);
        }
        if (res.spool.purged.length === 0 && res.spool.errors.length === 0) {
          pushToast("info", "Windows queues were already empty.");
        }
      }
      // If nothing happened across any layer, tell the operator explicitly so
      // they don't think the button is broken.
      const anythingHappened =
        res.cancelled_jobs.length > 0 ||
        res.failed_jobs.length > 0 ||
        res.printer.sent ||
        (res.spool.supported && (res.spool.purged.length > 0 || res.spool.errors.length > 0));
      if (!anythingHappened) {
        pushToast(
          "info",
          "Nothing was active to stop. Press is idle, no pending jobs, no spool entries.",
        );
      }
      reset();
    } catch (e) {
      pushToast(
        "error",
        `STOP failed: ${e instanceof Error ? e.message : e}`,
      );
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        disabled={busy}
        title="Stop all printing — drops pending jobs, sends JOB CANCEL to the press, purges Windows queues"
        style={{
          background: busy ? "#7a1a1d" : "#c1272d",
          color: "#fff",
          border: "1px solid #ff5a5a",
          borderRadius: 6,
          fontWeight: 700,
          fontSize: 13,
          padding: "6px 14px",
          marginLeft: 8,
          cursor: busy ? "wait" : "pointer",
          letterSpacing: 0.3,
          boxShadow: "0 1px 4px rgba(193,39,45,0.4)",
        }}
      >
        {busy ? "Stopping…" : "■ STOP"}
      </button>

      {confirming && (
        <div className="modal-backdrop" onClick={() => setConfirming(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ color: "#ff8888" }}>Stop all printing?</h2>
            <p>
              This will:
            </p>
            <ul style={{ marginTop: 4, lineHeight: 1.7 }}>
              <li>Drop every pending job this app is holding.</li>
              <li>Send <code>JOB CANCEL</code> to the C3070 (sheets already in the fuser will still finish).</li>
              <li>Purge every configured Windows print queue (Plain / Booklet / Stapled / Punched).</li>
            </ul>
            <p style={{ color: "var(--muted)", fontSize: 13 }}>
              Use this if a job is misprinting, the wrong file went out, or the press is stuck.
            </p>
            <div className="modal-actions">
              <button className="cta secondary" type="button" onClick={() => setConfirming(false)}>
                Keep printing
              </button>
              <button
                className="cta"
                type="button"
                onClick={fire}
                style={{ background: "#c1272d", borderColor: "#ff5a5a" }}
              >
                Yes — stop everything
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
