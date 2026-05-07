import { useEffect, useState } from "react";
import { api } from "../api";
import { formatMoney, formatPerUnit } from "../auto-detect";
import { useStore } from "../store";
import type { Preset, Stock } from "../types";

export function CostPanel() {
  const stage = useStore((s) => s.stage);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [rates, setRates] = useState<{ color: number; bw: number } | null>(null);

  useEffect(() => {
    api.presets().then(setPresets).catch(() => {});
    api.stocks().then(setStocks).catch(() => {});
    api.rates().then(setRates).catch(() => {});
  }, []);

  if (stage.kind !== "inspected" || !rates) {
    return (
      <div className="card">
        <h3>Cost</h3>
        <p style={{ color: "var(--muted)" }}>Drop a file to see a quote.</p>
      </div>
    );
  }

  const preset = presets.find((p) => p.key === stage.presetKey);
  const stock = stocks.find((s) => s.code === stage.stockCode);
  if (!preset || !stock) {
    return (
      <div className="card">
        <h3>Cost</h3>
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      </div>
    );
  }

  const sheets = Math.ceil(stage.quantity / preset.total);
  const paper = +(sheets * stock.cost_per_unit).toFixed(4);
  const click = +(sheets * stage.sides * rates.color).toFixed(4);
  const total = +(paper + click).toFixed(4);

  // Suggested retail at 3.5× cost markup (Hasan's standard markup floor)
  const suggested = total * 3.5;

  return (
    <div className="card">
      <h3>Cost</h3>
      <div className="cost-rows">
        <span className="label">Sheets through press</span>
        <span className="num">{sheets}</span>

        <span className="label">
          Click ({stage.sides === 2 ? "2-sided" : "1-sided"} · ${rates.color.toFixed(4)}/side)
        </span>
        <span className="num">{formatMoney(click)}</span>

        <span className="label">Paper ({stock.weight})</span>
        <span className="num">{formatMoney(paper)}</span>

        <span className="label">Finishing</span>
        <span className="num" style={{ color: "var(--muted)" }}>none in v1</span>

        <span className="label total-row">Total cost</span>
        <span className="num total-row">{formatMoney(total)}</span>

        <span className="label" style={{ color: "var(--muted)" }}>Per unit</span>
        <span className="num" style={{ color: "var(--muted)" }}>
          {formatPerUnit(total, stage.quantity)}
        </span>

        <span className="label" style={{ color: "var(--muted)", marginTop: 8 }}>
          Suggested retail (3.5× markup)
        </span>
        <span className="num" style={{ color: "var(--accent-strong)", marginTop: 8 }}>
          {formatMoney(suggested)}
        </span>
      </div>
    </div>
  );
}
