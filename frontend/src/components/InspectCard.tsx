import { useEffect, useState } from "react";
import { api } from "../api";
import { dimensionsLabel } from "../auto-detect";
import { useStore } from "../store";
import type { Finding, Preset, Stock } from "../types";
import { ConfirmPrintButton } from "./ConfirmPrintButton";
import { CostPanel } from "./CostPanel";
import { HelpTip } from "./HelpTip";
import { InspectImposedPreview } from "./InspectImposedPreview";
import { PreflightFindings } from "./PreflightFindings";
import { SaveCurrentAsPreset } from "./SavedPresets";

export function InspectCard() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const trays = useStore((s) => s.trays);
  const reset = useStore((s) => s.reset);
  const pushToast = useStore((s) => s.pushToast);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  // Progressive disclosure: only one section editable at a time.
  // null = static recommendation, "paper"/"layout"/"quantity" = that row in edit mode.
  const [customizing, setCustomizing] = useState<null | "paper" | "layout" | "quantity">(null);
  const [bleedFixing, setBleedFixing] = useState(false);

  useEffect(() => {
    api.presets().then(setPresets).catch(() => {});
    api.stocks().then(setStocks).catch(() => {});
  }, []);

  if (stage.kind !== "inspected") return null;

  const { file, result, quantity, sides, stockCode, presetKey } = stage;
  const preset = presets.find((p) => p.key === presetKey);
  const stock = stocks.find((s) => s.code === stockCode);
  const orientedDims = dimensionsLabel(result.width_in, result.height_in);

  const loadedTray =
    trays && stockCode
      ? Object.entries(trays.trays).find(([, t]) => t.stock_code === stockCode)?.[0] ?? null
      : null;
  const trayMatch = !!loadedTray;

  const updateQty = (q: number) => setStage({ ...stage, quantity: Math.max(1, q) });
  const updateSides = (n: 1 | 2) => setStage({ ...stage, sides: n });
  const updatePreset = (k: string) => setStage({ ...stage, presetKey: k });
  const updateStock = (c: string) => setStage({ ...stage, stockCode: c });

  const presetLabel = (p: Preset) =>
    p.friendly_label && p.friendly_label.length > 0
      ? p.friendly_label
      : `${p.total}-up ${p.piece} on ${p.sheet}`;
  const presetTechDetail = (p: Preset) => `${p.total}-up ${p.piece} on ${p.sheet}`;
  const stockLabel = (s: Stock) => (s.friendly_name && s.friendly_name.length > 0 ? s.friendly_name : s.name);

  async function fixBleed() {
    if (stage.kind !== "inspected") return;
    setBleedFixing(true);
    try {
      const after = await api.bleedFix({ inspect_filename: stage.file.name, target_bleed_in: 0.125 });
      setStage({
        ...stage,
        result: {
          ...stage.result,
          findings: after.findings,
          can_send: after.can_send,
          page_count: after.page_count,
        },
      });
      pushToast(
        "success",
        `Extended your background ${after.bleed_added_in.toFixed(3)}" so the color reaches the edge.`,
      );
    } catch (e) {
      pushToast(
        "error",
        `Couldn't extend the bleed: ${e instanceof Error ? e.message : e}. Try re-exporting from your design tool with full-page bleed.`,
      );
    } finally {
      setBleedFixing(false);
    }
  }

  const renderFindingAction = (f: Finding) => {
    if (f.code !== "insufficient-bleed") return null;
    return (
      <button
        type="button"
        className="cta secondary"
        style={{ fontSize: 13, padding: "4px 10px" }}
        onClick={fixBleed}
        disabled={bleedFixing}
      >
        {bleedFixing ? "Extending background…" : "Fix it for me"}
      </button>
    );
  };

  return (
    <div>
      <div className="section-head">
        <h2>{file.name}</h2>
        <span className="hint">
          {orientedDims} · {result.page_count} page{result.page_count !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="inspect-card">
        <div className="card" data-tour="recommendation">
          <h3>Recommendation</h3>

          {result.detected ? (
            <>
              <div className="detected-row">
                We think this is a <span className="detected-label">{result.detected.label}</span>.
              </div>
              <div className="detected-meta">{result.detected.notes}</div>
            </>
          ) : (
            <>
              <div className="detected-row">Unrecognized size — pick a workflow below.</div>
              <div className="detected-meta">
                {orientedDims} doesn't match a standard preset. You can still print it as a custom
                job by choosing layout + paper.
              </div>
            </>
          )}

          <div className="recommendation-grid">
            <div className="key">
              Layout<HelpTip glossaryKey="preset" />
            </div>
            <div className="value-with-chip">
              {customizing === "layout" ? (
                <>
                  <select value={presetKey} onChange={(e) => updatePreset(e.target.value)} autoFocus>
                    {presets.map((p) => (
                      <option key={p.key} value={p.key} title={presetTechDetail(p)}>
                        {presetLabel(p)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="customize-chip active"
                    onClick={() => setCustomizing(null)}
                  >
                    Done
                  </button>
                </>
              ) : (
                <>
                  <span title={preset ? presetTechDetail(preset) : undefined}>
                    {preset ? presetLabel(preset) : "—"}
                  </span>
                  <button
                    type="button"
                    className="customize-chip"
                    onClick={() => setCustomizing("layout")}
                  >
                    Change layout
                  </button>
                </>
              )}
            </div>

            <div className="key">
              Paper<HelpTip glossaryKey="stock" />
            </div>
            <div className="value-with-chip">
              {customizing === "paper" ? (
                <>
                  <select value={stockCode} onChange={(e) => updateStock(e.target.value)} autoFocus>
                    {stocks.map((s) => (
                      <option key={s.code} value={s.code} title={`${s.name} · ${s.weight}`}>
                        {stockLabel(s)}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="customize-chip active"
                    onClick={() => setCustomizing(null)}
                  >
                    Done
                  </button>
                </>
              ) : (
                <>
                  <span title={stock ? `${stock.name} · ${stock.weight}` : undefined}>
                    {stock ? stockLabel(stock) : stockCode}
                  </span>
                  <button
                    type="button"
                    className="customize-chip"
                    onClick={() => setCustomizing("paper")}
                  >
                    Change paper
                  </button>
                </>
              )}
            </div>

            <div className="key">
              Tray<HelpTip glossaryKey="tray" />
            </div>
            <div>
              {loadedTray ? (
                <>
                  <strong>{loadedTray}</strong>
                  <span className="check">✓ already loaded</span>
                </>
              ) : (
                <>
                  <em style={{ color: "var(--muted)" }}>
                    {stock?.default_tray ?? "—"} (recommended)
                  </em>
                  {trays?.configured && <span className="miss">⚠ not currently loaded</span>}
                </>
              )}
            </div>

            <div className="key">
              Bleed<HelpTip glossaryKey="bleed" />
            </div>
            <div>
              {result.detected && result.detected.expect_bleed_in > 0
                ? `1/8" — auto-add if missing`
                : "no bleed needed"}
              {result.detected && result.detected.expect_bleed_in > 0 && (
                <span className="check">✓</span>
              )}
            </div>

            <div className="key">
              Crop marks<HelpTip glossaryKey="cropMarks" />
            </div>
            <div>
              {result.detected && result.detected.expect_bleed_in > 0
                ? "Auto-add for cutter"
                : "n/a"}
              {result.detected && result.detected.expect_bleed_in > 0 && (
                <span className="check">✓</span>
              )}
            </div>

            <div className="key">Quantity</div>
            <div className="value-with-chip">
              {customizing === "quantity" ? (
                <>
                  <input
                    type="number"
                    min={1}
                    value={quantity}
                    onChange={(e) => updateQty(parseInt(e.target.value || "1", 10))}
                    style={{ width: 100 }}
                    autoFocus
                  />
                  {preset && (
                    <span style={{ marginLeft: 8, color: "var(--muted)" }}>
                      = {Math.ceil(quantity / preset.total)} sheet
                      {Math.ceil(quantity / preset.total) !== 1 ? "s" : ""}
                    </span>
                  )}
                  <button
                    type="button"
                    className="customize-chip active"
                    onClick={() => setCustomizing(null)}
                  >
                    Done
                  </button>
                </>
              ) : (
                <>
                  <span>
                    {quantity}
                    {preset && (
                      <span style={{ marginLeft: 8, color: "var(--muted)" }}>
                        = {Math.ceil(quantity / preset.total)} sheet
                        {Math.ceil(quantity / preset.total) !== 1 ? "s" : ""}
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="customize-chip"
                    onClick={() => setCustomizing("quantity")}
                  >
                    Change quantity
                  </button>
                </>
              )}
            </div>

            <div className="key">
              Sides<HelpTip glossaryKey="duplex" />
            </div>
            <div>
              {customizing === "quantity" ? (
                <>
                  <label style={{ marginRight: 12 }}>
                    <input
                      type="radio"
                      name="sides"
                      checked={sides === 1}
                      onChange={() => updateSides(1)}
                    />{" "}
                    1-sided
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="sides"
                      checked={sides === 2}
                      onChange={() => updateSides(2)}
                      disabled={result.page_count < 2}
                    />{" "}
                    2-sided{" "}
                    {result.page_count < 2 && (
                      <span style={{ color: "var(--muted)" }}>(file has 1 page)</span>
                    )}
                  </label>
                </>
              ) : (
                <span>{sides === 2 ? "2-sided (front + back)" : "1-sided"}</span>
              )}
            </div>
          </div>

          <PreflightFindings findings={result.findings} renderAction={renderFindingAction} />

          {trays?.configured && !trayMatch && (
            <div className="finding info">
              <span className="icon">📄</span>
              <div>
                When you tap print, we'll ask you to put <strong>{stock ? stockLabel(stock) : stockCode}</strong> in the recommended tray.
              </div>
            </div>
          )}

          <div className="cta-row">
            <ConfirmPrintButton />
            <SaveCurrentAsPreset />
            <button className="cta danger" type="button" onClick={reset} title="Discard and start over (Esc)">
              Discard
            </button>
          </div>
        </div>

        <div className="inspect-side">
          <InspectImposedPreview />
          <CostPanel />
        </div>
      </div>
    </div>
  );
}
