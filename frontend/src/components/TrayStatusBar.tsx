import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Stock, TrayKey, TrayState } from "../types";
import { TrayEditor } from "./TrayEditor";

const TRAY_KEYS: TrayKey[] = ["T1", "T2", "T3", "T4", "T5"];

export function TrayStatusBar() {
  const trays = useStore((s) => s.trays);
  const setTrays = useStore((s) => s.setTrays);
  const pushToast = useStore((s) => s.pushToast);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [editing, setEditing] = useState<TrayKey | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api.stocks().then(setStocks).catch((e) => pushToast("error", `Couldn't load paper catalog: ${e.message}`));
    api.trays().then(setTrays).catch((e) => pushToast("error", `Couldn't load tray status: ${e.message}`));
  }, [pushToast, setTrays]);

  const state: TrayState | null = trays?.trays ?? null;
  const loadedCount = state ? Object.values(state).filter((t) => t.stock_code).length : 0;
  const totalTrays = TRAY_KEYS.length;

  // Escalation: count operator-marked low/empty trays. "unknown" doesn't escalate
  // (operator hasn't told us yet). Trays without stock_code can't be empty —
  // they're just unconfigured, which is normal.
  const loadedTrays = state
    ? Object.values(state).filter((t): t is NonNullable<typeof t> => Boolean(t?.stock_code))
    : [];
  const emptyCount = loadedTrays.filter((t) => t.level === "empty").length;
  const lowCount = loadedTrays.filter((t) => t.level === "low").length;

  let pillTone: "muted" | "warn" | "danger" = "muted";
  let pillLabel = `Trays · ${loadedCount} of ${totalTrays} loaded`;
  if (emptyCount > 0) {
    pillTone = "danger";
    pillLabel = `${emptyCount} tray${emptyCount === 1 ? "" : "s"} empty · refill now`;
  } else if (lowCount > 0) {
    pillTone = "warn";
    pillLabel = `${lowCount} tray${lowCount === 1 ? "" : "s"} low · refill soon`;
  }

  const pillStyle: React.CSSProperties =
    pillTone === "muted"
      ? { fontSize: 12, color: "var(--muted)" }
      : pillTone === "warn"
      ? {
          fontSize: 12,
          fontWeight: 600,
          color: "var(--warn)",
          background: "rgba(244,186,58,0.12)",
          border: "1px solid rgba(244,186,58,0.4)",
          borderRadius: 999,
          padding: "4px 10px",
        }
      : {
          fontSize: 12,
          fontWeight: 600,
          color: "var(--danger)",
          background: "rgba(255,92,92,0.14)",
          border: "1px solid rgba(255,92,92,0.4)",
          borderRadius: 999,
          padding: "4px 10px",
        };

  if (!expanded) {
    return (
      <div
        className="tray-bar collapsed"
        role="region"
        aria-label="Press tray status"
        style={{ display: "flex", justifyContent: "flex-end", padding: "6px 12px" }}
      >
        <button
          type="button"
          className={pillTone === "muted" ? "ghost" : undefined}
          onClick={() => setExpanded(true)}
          title={
            pillTone === "muted"
              ? "Show what paper is loaded in each tray"
              : "Click to see which tray needs paper"
          }
          style={pillStyle}
          aria-live={pillTone === "muted" ? undefined : "polite"}
        >
          {pillLabel}
          {pillTone !== "muted" && (
            <span style={{ marginLeft: 8, color: "var(--muted)", fontWeight: 400 }}>
              · {loadedCount}/{totalTrays} loaded
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="tray-bar" role="region" aria-label="Press tray status">
        {TRAY_KEYS.map((k) => {
          const t = state?.[k];
          const stock = stocks.find((s) => s.code === t?.stock_code);
          const level = (t?.level ?? "unknown") as "full" | "low" | "empty" | "unknown";
          return (
            <button
              key={k}
              className="tray-cell"
              type="button"
              onClick={() => setEditing(k)}
              title={stock ? `${stock.name} (${stock.weight})` : "Click to set what's loaded"}
            >
              <span className="key">{k}</span>
              <span className="name">
                <span className={`status-dot ${level}`} />
                {stock ? (stock.friendly_name || stock.name) : <em style={{ color: "var(--muted)" }}>not set</em>}
              </span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                {t?.paper_size ?? (stock ? stock.parent_sheet : "—")}
                {level !== "unknown" ? ` · ${level}` : ""}
              </span>
              {t?.stock_code && t.sheets_used > 0 && (
                <span
                  className={
                    "tray-sheets-used " +
                    (t.sheets_used >= 1000 ? "danger" : t.sheets_used >= 500 ? "warn" : "")
                  }
                  title={`${t.sheets_used} sheets used since last refill — click tray to mark "full" and reset`}
                >
                  {t.sheets_used.toLocaleString()} used
                </span>
              )}
            </button>
          );
        })}
        <button
          type="button"
          className="ghost"
          onClick={() => setExpanded(false)}
          title="Hide tray bar"
          style={{ fontSize: 12, color: "var(--muted)", marginLeft: "auto" }}
        >
          Hide
        </button>
      </div>

      {editing && (
        <TrayEditor
          tray={editing}
          stocks={stocks}
          current={state?.[editing] ?? { stock_code: null, paper_size: null, level: "unknown", updated_at: null, sheets_used: 0 }}
          onClose={() => setEditing(null)}
          onSaved={(t) => {
            setTrays(t);
            pushToast("success", `${editing} updated`);
            setEditing(null);
          }}
        />
      )}
    </>
  );
}
