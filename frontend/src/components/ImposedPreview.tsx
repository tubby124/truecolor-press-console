// Browser-native PDF preview via <embed>. Avoids pulling in pdf.js/react-pdf
// for v1 — Safari and Chrome both render embedded PDFs fine on the shop Mac.

import { useEffect, useState } from "react";
import { api } from "../api";
import { formatMoney } from "../auto-detect";
import { useStore } from "../store";
import type { Job } from "../types";

export function ImposedPreview() {
  const stage = useStore((s) => s.stage);
  const reset = useStore((s) => s.reset);
  const pushToast = useStore((s) => s.pushToast);
  const [reprinting, setReprinting] = useState(false);

  if (stage.kind !== "done") return null;
  const job: Job = stage.job;

  async function reprintNow() {
    setReprinting(true);
    try {
      const newJob = await api.reprint(job.job_id);
      pushToast("success", `Reprinted as ${newJob.job_id}`);
    } catch (e) {
      pushToast("error", `Reprint failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setReprinting(false);
    }
  }

  return (
    <div>
      <div className="section-head">
        <h2>
          {job.status === "spooled-dry" ? "Spooled (DRY)" : "Sent to press"} —{" "}
          {job.sheets} sheet{job.sheets !== 1 ? "s" : ""}
        </h2>
        <span className="hint">
          job <code>{job.job_id}</code> · {formatMoney(job.total_cost)}
        </span>
      </div>

      <div className="preview-shell">
        {job.imposed_path ? (
          <embed src={api.imposedPdfUrl(job.job_id)} type="application/pdf" />
        ) : (
          <p style={{ color: "var(--muted)" }}>No imposed PDF — preflight blocked.</p>
        )}
      </div>

      <div className="cta-row">
        <button className="cta" type="button" onClick={reset}>
          Print another
        </button>
        <button
          className="cta secondary"
          type="button"
          onClick={reprintNow}
          disabled={reprinting || !job.imposed_path}
        >
          {reprinting ? <span className="spinner" /> : "Re-spool same job"}
        </button>
        {job.imposed_path && (
          <a className="cta secondary" href={api.imposedPdfUrl(job.job_id)} target="_blank" rel="noreferrer">
            Open PDF
          </a>
        )}
      </div>

      <DryReminder status={job.status} />
    </div>
  );
}

function DryReminder({ status }: { status: string }) {
  if (status !== "spooled-dry") return null;
  return (
    <div className="finding warn" style={{ marginTop: 14 }}>
      <span className="icon">ⓘ</span>
      <div>
        <strong>Dry mode:</strong> the PJL bundle was written to disk but not sent to{" "}
        172.16.1.149. Hardware repair must clear C-6753 before live printing —{" "}
        see <code>docs/HARDWARE-GATES.md</code>.
      </div>
    </div>
  );
}

// Auto-mount preview in App when stage = submitting
export function SubmittingScreen() {
  const stage = useStore((s) => s.stage);
  useEffect(() => {}, [stage.kind]);
  if (stage.kind !== "submitting") return null;
  return (
    <div className="card" style={{ textAlign: "center", padding: 60 }}>
      <span className="spinner" /> &nbsp; Imposing & spooling {stage.file.name}…
    </div>
  );
}
