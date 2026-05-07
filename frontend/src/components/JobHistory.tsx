import { useEffect, useState } from "react";
import { api } from "../api";
import { formatMoney } from "../auto-detect";
import { useStore } from "../store";
import type { JobSummary } from "../types";

export function JobHistory() {
  const showHistory = useStore((s) => s.showHistory);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const pushToast = useStore((s) => s.pushToast);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!showHistory) return;
    setLoading(true);
    api
      .jobs(50)
      .then(setJobs)
      .catch((e) => pushToast("error", `History load failed: ${e.message}`))
      .finally(() => setLoading(false));
  }, [showHistory, pushToast]);

  async function reprint(id: string) {
    try {
      const job = await api.reprint(id);
      pushToast("success", `Reprinted as ${job.job_id}`);
      const fresh = await api.jobs(50);
      setJobs(fresh);
    } catch (e) {
      pushToast("error", `Reprint failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  if (!showHistory) return null;

  return (
    <div className="modal-backdrop" onClick={() => setShowHistory(false)}>
      <div className="modal" style={{ minWidth: 720, width: 840 }} onClick={(e) => e.stopPropagation()}>
        <div className="section-head" style={{ margin: 0 }}>
          <h2>Recent jobs</h2>
          <span className="hint">last 50 · click a tile to re-spool the same settings</span>
        </div>

        {loading ? (
          <p>
            <span className="spinner" /> Loading…
          </p>
        ) : jobs.length === 0 ? (
          <p style={{ color: "var(--muted)" }}>No jobs yet.</p>
        ) : (
          <div className="history-grid" style={{ marginTop: 14 }}>
            {jobs.map((j) => (
              <button
                key={j.job_id}
                type="button"
                className="history-tile"
                onClick={() => reprint(j.job_id)}
                title={`Reprint with ${j.quantity} pcs`}
              >
                {j.has_thumb || j.has_imposed ? (
                  <img src={api.thumbUrl(j.job_id)} alt={j.workflow} loading="lazy" />
                ) : (
                  <div
                    style={{
                      aspectRatio: "1.4",
                      background: "#222",
                      borderRadius: 6,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "var(--muted)",
                      fontSize: 11,
                    }}
                  >
                    {j.status}
                  </div>
                )}
                <div className="meta">
                  <div className="label">
                    {j.workflow} · {j.quantity} pcs
                  </div>
                  <div className="sub">
                    {j.sheets} sheet{j.sheets !== 1 ? "s" : ""} · {formatMoney(j.total_cost ?? 0)}
                  </div>
                  <div className="sub">{j.created_at?.slice(0, 16).replace("T", " ")}</div>
                </div>
              </button>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button className="cta secondary" type="button" onClick={() => setShowHistory(false)}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
