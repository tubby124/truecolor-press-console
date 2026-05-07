import { plainEnglish, severityIcon } from "../auto-detect";
import type { Finding } from "../types";

export function PreflightFindings({ findings }: { findings: Finding[] }) {
  if (!findings.length) return null;
  return (
    <div className="findings">
      {findings.map((f, i) => (
        <div key={i} className={`finding ${f.severity}`}>
          <span className="icon">{severityIcon(f.severity)}</span>
          <div>
            {plainEnglish(f)}
            {f.page != null && <em style={{ color: "var(--muted)" }}> · page {f.page}</em>}
          </div>
        </div>
      ))}
    </div>
  );
}
