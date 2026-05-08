import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { formatMoney } from "../auto-detect";
import { useStore } from "../store";
import type { JobSummary } from "../types";

// Map raw workflow codes to operator-friendly labels for the history view.
// Matches the friendly tile labels in workflows/tiles.ts.
const WORKFLOW_LABEL: Record<string, string> = {
  business_card: "Business cards",
  postcard_3x4: "Postcards 3×4",
  postcard_4x6: "Postcards 4×6",
  postcard_5x7: "Postcards 5×7",
  flyer_letter: "Letter flyer",
  flyer_half: "Half-letter flyer",
  trifold_brochure: "Tri-fold brochure",
  bifold_brochure: "Bi-fold brochure",
  halffold_card: "Half-fold card",
  poster_letter: "Letter poster",
  poster_11x17: "11×17 poster",
  custom: "Custom job",
  batch: "Batch job",
};

function workflowLabel(code: string): string {
  return WORKFLOW_LABEL[code] ?? code.replace(/_/g, " ");
}

export function JobHistory() {
  const showHistory = useStore((s) => s.showHistory);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const pushToast = useStore((s) => s.pushToast);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return jobs;
    const q = search.toLowerCase();
    return jobs.filter(
      (j) =>
        workflowLabel(j.workflow).toLowerCase().includes(q) ||
        j.workflow.toLowerCase().includes(q) ||
        j.job_id.toLowerCase().includes(q) ||
        (j.created_at ?? "").toLowerCase().includes(q),
    );
  }, [jobs, search]);

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

  // Default range: this calendar year. Operator can clear or change for ad-hoc.
  const yearStart = `${new Date().getFullYear()}-01-01`;
  const todayIso = new Date().toISOString().slice(0, 10);

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
          <>
            <input
              type="search"
              value={search}
              placeholder="Search by job type, ID, or date…"
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                marginTop: 12,
                fontSize: 14,
                borderRadius: 6,
                border: "1px solid var(--border)",
                background: "var(--panel-2, #111)",
                color: "var(--text)",
              }}
            />
            {filtered.length === 0 ? (
              <p style={{ color: "var(--muted)", marginTop: 14 }}>
                No jobs match "{search}".
              </p>
            ) : (
              <div className="history-grid" style={{ marginTop: 14 }}>
                {filtered.map((j) => (
                  <button
                    key={j.job_id}
                    type="button"
                    className="history-tile"
                    onClick={() => reprint(j.job_id)}
                    title={`Reprint with ${j.quantity} pcs`}
                  >
                    {j.has_thumb || j.has_imposed ? (
                      <img src={api.thumbUrl(j.job_id)} alt={workflowLabel(j.workflow)} loading="lazy" />
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
                        {workflowLabel(j.workflow)} · {j.quantity} pcs
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
          </>
        )}

        <div className="modal-actions">
          <a
            className="cta secondary"
            href={api.auditCsvUrl(yearStart, todayIso)}
            download
            title={`Download every job from ${yearStart} to ${todayIso} as CSV (Wave / accounting)`}
          >
            Export CSV ({yearStart.slice(0, 4)})
          </a>
          <a
            className="cta secondary"
            href={api.auditCsvUrl()}
            download
            title="Download every job in history as CSV"
          >
            Export all
          </a>
          <button className="cta secondary" type="button" onClick={() => setShowHistory(false)}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
