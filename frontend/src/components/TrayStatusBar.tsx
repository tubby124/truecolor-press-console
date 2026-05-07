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

  useEffect(() => {
    api.stocks().then(setStocks).catch((e) => pushToast("error", `Couldn't load paper catalog: ${e.message}`));
    api.trays().then(setTrays).catch((e) => pushToast("error", `Couldn't load tray status: ${e.message}`));
  }, [pushToast, setTrays]);

  const state: TrayState | null = trays?.trays ?? null;

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
                {stock ? stock.name : <em style={{ color: "var(--muted)" }}>not set</em>}
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
