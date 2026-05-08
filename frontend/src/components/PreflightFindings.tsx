import { useState, type ReactNode } from "react";
import { plainEnglish, severityIcon, whatToDoFor } from "../auto-detect";
import type { Finding } from "../types";

interface PreflightFindingsProps {
  findings: Finding[];
  /** Per-finding action button. Return null to render no button for that finding. */
  renderAction?: (finding: Finding) => ReactNode;
}

export function PreflightFindings({ findings, renderAction }: PreflightFindingsProps) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  if (!findings.length) return null;
  return (
    <div className="findings">
      {findings.map((f, i) => {
        const help = whatToDoFor(f.code);
        const isOpen = !!expanded[i];
        const action = renderAction ? renderAction(f) : null;
        return (
          <div key={i} className={`finding ${f.severity}`}>
            <span className="icon">{severityIcon(f.severity)}</span>
            <div style={{ flex: 1 }}>
              <div>
                {plainEnglish(f)}
                {f.page != null && <em style={{ color: "var(--muted)" }}> · page {f.page}</em>}
              </div>
              <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {action}
                {help && (
                  <button
                    type="button"
                    onClick={() => setExpanded((s) => ({ ...s, [i]: !s[i] }))}
                    style={{
                      background: "transparent",
                      border: "1px solid var(--border)",
                      color: "var(--muted)",
                      borderRadius: 6,
                      padding: "3px 10px",
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    {isOpen ? "Hide what to do" : "What to do about it"}
                  </button>
                )}
              </div>
              {isOpen && help && (
                <ol style={{ marginTop: 8, paddingLeft: 22, color: "var(--muted)", fontSize: 13, lineHeight: 1.55 }}>
                  {help.steps.map((step, j) => (
                    <li key={j} style={{ marginBottom: 4 }}>{step}</li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
