import { api } from "../api";
import { useStore } from "../store";

export function BatchDoneScreen() {
  const stage = useStore((s) => s.stage);
  const reset = useStore((s) => s.reset);

  if (stage.kind !== "batch_done") return null;

  const { results } = stage;
  const oks = results.filter((r) => r.job).length;
  const errs = results.length - oks;
  const totalSheets = results.reduce((sum, r) => sum + (r.job?.sheets ?? 0), 0);
  const totalCost = results.reduce((sum, r) => sum + (r.job?.total_cost ?? 0), 0);

  return (
    <div>
      <div className="section-head">
        <h2>Batch complete</h2>
        <span className="hint">
          {oks} job{oks !== 1 ? "s" : ""} created
          {errs > 0 ? ` · ${errs} failed` : ""} · {totalSheets} sheets · ${totalCost.toFixed(2)}
        </span>
      </div>

      <div className="card">
        <ul className="batch-file-list">
          {results.map((r, i) => (
            <li key={`${r.file}-${i}`} className="batch-file-row">
              <span className="batch-file-name">{r.file}</span>
              {r.job ? (
                <>
                  <span className="batch-file-meta">
                    {r.job.sheets} sheet{r.job.sheets !== 1 ? "s" : ""} · ${r.job.total_cost.toFixed(2)}
                  </span>
                  <a
                    href={api.imposedPdfUrl(r.job.job_id)}
                    target="_blank"
                    rel="noreferrer"
                    className="batch-file-link"
                  >
                    Open PDF
                  </a>
                </>
              ) : (
                <span className="batch-file-error" title={r.error}>
                  ⚠ {r.error ?? "unknown error"}
                </span>
              )}
            </li>
          ))}
        </ul>

        <div className="cta-row">
          <button className="cta" type="button" onClick={reset}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
