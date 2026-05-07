import { useState } from "react";
import { api } from "../api";
import type { Stock, TrayInfo, TrayKey, TraysResponse } from "../types";

interface Props {
  tray: TrayKey;
  stocks: Stock[];
  current: TrayInfo;
  onClose: () => void;
  onSaved: (response: TraysResponse) => void;
}

export function TrayEditor({ tray, stocks, current, onClose, onSaved }: Props) {
  const [stockCode, setStockCode] = useState<string | null>(current.stock_code);
  const [level, setLevel] = useState<string>(current.level || "full");
  const [paperSize, setPaperSize] = useState<string | null>(current.paper_size);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const stock = stocks.find((s) => s.code === stockCode);
      const r = await api.setTray(tray, {
        stock_code: stockCode,
        paper_size: paperSize ?? stock?.parent_sheet ?? null,
        level: level || "unknown",
      });
      onSaved(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function clear() {
    setSaving(true);
    setError(null);
    try {
      const r = await api.setTray(tray, { stock_code: null, paper_size: null, level: "unknown" });
      onSaved(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const selectedStock = stocks.find((s) => s.code === stockCode);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Set tray {tray} contents</h2>
        <p>Tell the console what paper you just loaded into this tray.</p>

        <div className="tray-editor-row">
          <label>Paper</label>
          <select
            value={stockCode ?? ""}
            onChange={(e) => {
              const code = e.target.value || null;
              setStockCode(code);
              const s = stocks.find((x) => x.code === code);
              if (s) setPaperSize(s.parent_sheet);
            }}
          >
            <option value="">— empty —</option>
            {stocks.map((s) => (
              <option key={s.code} value={s.code} title={`${s.name} · ${s.weight}`}>
                {s.friendly_name || s.name} ({s.weight})
              </option>
            ))}
          </select>
        </div>

        <div className="tray-editor-row">
          <label>Size</label>
          <input
            type="text"
            placeholder={selectedStock?.parent_sheet ?? "e.g. 12x18, LETTER"}
            value={paperSize ?? ""}
            onChange={(e) => setPaperSize(e.target.value || null)}
          />
        </div>

        <div className="tray-editor-row">
          <label>Level</label>
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="full">Full</option>
            <option value="low">Low</option>
            <option value="empty">Empty</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {error && <p style={{ color: "var(--danger)" }}>{error}</p>}

        <div className="modal-actions">
          <button className="cta secondary" type="button" onClick={clear} disabled={saving}>
            Mark empty
          </button>
          <button className="cta secondary" type="button" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="cta" type="button" onClick={save} disabled={saving}>
            {saving ? <span className="spinner" /> : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
