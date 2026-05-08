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
        <h3>What it costs</h3>
        <p style={{ color: "var(--muted)" }}>Drop a file to see a quote.</p>
      </div>
    );
  }

  const preset = presets.find((p) => p.key === stage.presetKey);
  const stock = stocks.find((s) => s.code === stage.stockCode);
  if (!preset || !stock) {
    return (
      <div className="card">
        <h3>What it costs</h3>
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
  const stockLabel = stock.friendly_name || stock.name;
  const costUnverified = stock.tags?.includes("_cost_unverified");

  return (
    <div className="card">
      <h3>What it costs</h3>
      <div className="cost-rows">
        <span className="label">Sheets through press</span>
        <span className="num">{sheets}</span>

        <span
          className="label"
          title={`Press cost · ${stage.sides === 2 ? "2-sided" : "1-sided"} · $${rates.color.toFixed(4)} per side`}
        >
          Press cost ({stage.sides === 2 ? "front + back" : "1 side"})
        </span>
        <span className="num">{formatMoney(click)}</span>

        <span className="label" title={`${stock.name} · ${stock.weight}`}>
          Paper ({stockLabel})
          {costUnverified && (
            <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: 6 }}>· est.</span>
          )}
        </span>
        <span className="num">{formatMoney(paper)}</span>

        <span className="label">Finishing (staple / fold / punch)</span>
        <span className="num" style={{ color: "var(--muted)" }}>not yet enabled</span>

        <span className="label total-row">Total cost to run</span>
        <span className="num total-row">{formatMoney(total)}</span>

        <span className="label" style={{ color: "var(--muted)" }}>Cost per piece</span>
        <span className="num" style={{ color: "var(--muted)" }}>
          {formatPerUnit(total, stage.quantity)}
        </span>

        <span
          className="label"
          style={{ color: "var(--muted)", marginTop: 8 }}
          title="3.5× markup of total cost — True Color minimum margin floor"
        >
          Suggested customer price (3.5× markup)
        </span>
        <span className="num" style={{ color: "var(--accent-strong)", marginTop: 8 }}>
          {formatMoney(suggested)}
        </span>
      </div>
      {costUnverified && (
        <p style={{ color: "var(--muted)", fontSize: 11, marginTop: 8, lineHeight: 1.5 }}>
          The paper cost for this stock is a best-guess estimate. Real cost may be ±20% off until
          Hasan confirms the supplier invoice. Quote with a buffer.
        </p>
      )}
    </div>
  );
}
