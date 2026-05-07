import type { ReactNode } from "react";
import { plainEnglish, severityIcon } from "../auto-detect";
import type { Finding } from "../types";

interface PreflightFindingsProps {
  findings: Finding[];
  /** Per-finding action button. Return null to render no button for that finding. */
  renderAction?: (finding: Finding) => ReactNode;
}

export function PreflightFindings({ findings, renderAction }: PreflightFindingsProps) {
  if (!findings.length) return null;
  return (
    <div className="findings">
      {findings.map((f, i) => (
        <div key={i} className={`finding ${f.severity}`}>
          <span className="icon">{severityIcon(f.severity)}</span>
          <div>
            {plainEnglish(f)}
            {f.page != null && <em style={{ color: "var(--muted)" }}> · page {f.page}</em>}
            {renderAction && <div style={{ marginTop: 6 }}>{renderAction(f)}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
