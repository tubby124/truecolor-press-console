import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { PreviewResult } from "../types";

// Tiny inline SVG fold diagram. Operator-facing — labels A/B/C panels and
// shows the fold sequence with arrows so the operator knows which panel
// folds in first. We render this beneath the friendly explainer; size is
// fixed at ~120x60 so it doesn't dominate the card.
//
// Tri-fold (letter, 11x8.5 long-edge): three vertical panels A | B | C.
//   Step 1 — fold A inward over B.
//   Step 2 — fold C over the now-stacked A+B (so C ends up on top).
//
// Bi-fold (11x17 → 8.5x11 brochure): two vertical panels A | B, single
//   fold along the centerline.
//
// Half-fold (greeting card): same as bi-fold but the fold is horizontal —
//   A top, B bottom, fold up.
function FoldDiagram({ presetKey }: { presetKey: string }) {
  const W = 120;
  const H = 60;
  const stroke = "var(--muted, #888)";
  const fill = "var(--panel-2, #2a2a2e)";
  const labelColor = "var(--text, #f5f5f5)";

  if (presetKey.startsWith("trifold")) {
    const pad = 4;
    const cellW = (W - 2 * pad) / 3;
    return (
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-label="tri-fold diagram"
      >
        {/* three panels */}
        {[0, 1, 2].map((i) => {
          const x = pad + i * cellW;
          return (
            <g key={i}>
              <rect
                x={x}
                y={pad}
                width={cellW}
                height={H - 2 * pad}
                fill={fill}
                stroke={stroke}
                strokeWidth={0.8}
                strokeDasharray={i === 0 ? "0" : "2 2"}
              />
              <text
                x={x + cellW / 2}
                y={H / 2 + 4}
                textAnchor="middle"
                fontSize={11}
                fill={labelColor}
                fontFamily="system-ui, sans-serif"
              >
                {["A", "B", "C"][i]}
              </text>
            </g>
          );
        })}
        {/* arrow: A → B (fold left panel inward) */}
        <path
          d={`M ${pad + 4} ${H / 2 - 16} Q ${pad + cellW} ${H / 2 - 22} ${pad + cellW + 4} ${H / 2 - 16}`}
          fill="none"
          stroke="var(--accent, #4a8cff)"
          strokeWidth={1}
          markerEnd="url(#tri-arrow)"
        />
        {/* arrow: C → AB (fold right panel over) */}
        <path
          d={`M ${pad + 3 * cellW - 4} ${H / 2 + 16} Q ${pad + 2 * cellW} ${H / 2 + 22} ${pad + 2 * cellW - 4} ${H / 2 + 16}`}
          fill="none"
          stroke="var(--accent, #4a8cff)"
          strokeWidth={1}
          markerEnd="url(#tri-arrow)"
        />
        <defs>
          <marker
            id="tri-arrow"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M 0 0 L 6 3 L 0 6 z" fill="var(--accent, #4a8cff)" />
          </marker>
        </defs>
      </svg>
    );
  }

  if (presetKey.startsWith("bifold")) {
    const pad = 4;
    const cellW = (W - 2 * pad) / 2;
    return (
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-label="bi-fold diagram"
      >
        {[0, 1].map((i) => {
          const x = pad + i * cellW;
          return (
            <g key={i}>
              <rect
                x={x}
                y={pad}
                width={cellW}
                height={H - 2 * pad}
                fill={fill}
                stroke={stroke}
                strokeWidth={0.8}
                strokeDasharray={i === 0 ? "0" : "2 2"}
              />
              <text
                x={x + cellW / 2}
                y={H / 2 + 4}
                textAnchor="middle"
                fontSize={11}
                fill={labelColor}
                fontFamily="system-ui, sans-serif"
              >
                {["A", "B"][i]}
              </text>
            </g>
          );
        })}
        {/* single fold-arrow over the centerline */}
        <path
          d={`M ${pad + cellW + cellW - 6} ${H / 2 - 14} Q ${pad + cellW} ${H / 2 - 24} ${pad + cellW - cellW + 6} ${H / 2 - 14}`}
          fill="none"
          stroke="var(--accent, #4a8cff)"
          strokeWidth={1}
          markerEnd="url(#bi-arrow)"
        />
        <defs>
          <marker
            id="bi-arrow"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M 0 0 L 6 3 L 0 6 z" fill="var(--accent, #4a8cff)" />
          </marker>
        </defs>
      </svg>
    );
  }

  if (presetKey.startsWith("halffold")) {
    const pad = 4;
    const cellH = (H - 2 * pad) / 2;
    return (
      <svg
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-label="half-fold diagram"
      >
        {[0, 1].map((i) => {
          const y = pad + i * cellH;
          return (
            <g key={i}>
              <rect
                x={pad}
                y={y}
                width={W - 2 * pad}
                height={cellH}
                fill={fill}
                stroke={stroke}
                strokeWidth={0.8}
                strokeDasharray={i === 0 ? "0" : "2 2"}
              />
              <text
                x={W / 2}
                y={y + cellH / 2 + 4}
                textAnchor="middle"
                fontSize={11}
                fill={labelColor}
                fontFamily="system-ui, sans-serif"
              >
                {["A", "B"][i]}
              </text>
            </g>
          );
        })}
        {/* fold-up arrow on the right */}
        <path
          d={`M ${W - 12} ${H - pad - 4} Q ${W - 4} ${H / 2} ${W - 12} ${pad + 4}`}
          fill="none"
          stroke="var(--accent, #4a8cff)"
          strokeWidth={1}
          markerEnd="url(#half-arrow)"
        />
        <defs>
          <marker
            id="half-arrow"
            markerWidth="6"
            markerHeight="6"
            refX="5"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M 0 0 L 6 3 L 0 6 z" fill="var(--accent, #4a8cff)" />
          </marker>
        </defs>
      </svg>
    );
  }

  return null;
}

// Plain-English hint that explains what the operator is looking at, keyed by
// preset family. Returns null for self-explanatory presets (single 1-up
// posters / flyers) so we don't add noise where none is needed.
function friendlyExplainer(presetKey: string | null, totalPerSheet: number | null, qty: number | null): string | null {
  if (!presetKey) return null;
  if (presetKey.startsWith("bc_")) {
    const sheets = totalPerSheet && qty ? Math.max(1, Math.ceil(qty / totalPerSheet)) : null;
    const totalCards = sheets && totalPerSheet ? sheets * totalPerSheet : null;
    if (totalCards) {
      return `We're printing ${totalPerSheet} cards per sheet. After ${sheets} sheet${sheets !== 1 ? "s" : ""} go through the press, the cutter slices them apart — you end up with ${totalCards} finished cards.`;
    }
    return "We're laying out cards on a big sheet, then the cutter slices them apart afterward.";
  }
  if (presetKey.startsWith("pc_")) {
    if (totalPerSheet) {
      return `We're printing ${totalPerSheet} postcards per sheet. After printing, the cutter slices them apart along the dashed lines.`;
    }
    return "We're laying out postcards on a big sheet, then the cutter slices them apart afterward.";
  }
  if (presetKey.startsWith("trifold")) {
    return "This is the unfolded sheet. After it prints, fold it into thirds along the dashed fold lines.";
  }
  if (presetKey.startsWith("bifold")) {
    return "This is the unfolded 11×17 sheet. After it prints, fold it once down the middle to make a 4-page brochure.";
  }
  if (presetKey.startsWith("halffold")) {
    return "This is the unfolded sheet. After it prints, fold it once down the middle to make a greeting-card-style fold.";
  }
  if (presetKey.startsWith("flyer_half_2up")) {
    return "Two half-letter flyers per sheet. After printing, cut along the dashed line to separate them.";
  }
  // 1-up posters / flyers / large prints — what you see is what you get.
  return null;
}

export function InspectImposedPreview() {
  const stage = useStore((s) => s.stage);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [presets, setPresets] = useState<{ key: string; total: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pull primitives so the effect dep-array is stable across re-renders.
  const fileName = stage.kind === "inspected" ? stage.file.name : null;
  const presetKey = stage.kind === "inspected" ? stage.presetKey : null;
  const stockCode = stage.kind === "inspected" ? stage.stockCode : null;
  const quantity = stage.kind === "inspected" ? stage.quantity : null;
  const sides = stage.kind === "inspected" ? stage.sides : null;

  useEffect(() => {
    api.presets().then((ps) => setPresets(ps.map((p) => ({ key: p.key, total: p.total })))).catch(() => {});
  }, []);

  useEffect(() => {
    if (!fileName || !presetKey || !stockCode || quantity == null || sides == null) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    const t = setTimeout(async () => {
      try {
        const r = await api.preview({
          inspect_filename: fileName,
          preset_key: presetKey,
          stock_code: stockCode,
          quantity,
          sides,
        });
        if (!cancelled) setPreview(r);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [fileName, presetKey, stockCode, quantity, sides]);

  if (stage.kind !== "inspected") return null;

  return (
    <div className="card preview-card">
      <h3>Imposed sheet preview</h3>
      {loading && !preview && (
        <div className="preview-thumb-skeleton">
          <span className="spinner" /> Imposing…
        </div>
      )}
      {error && (
        <div className="finding warn">
          <span className="icon">⚠</span>
          <div>Preview unavailable: {error}</div>
        </div>
      )}
      {preview && (
        <>
          <a
            href={preview.preview_url}
            target="_blank"
            rel="noreferrer"
            className="preview-thumb-link"
            title="Open full imposed PDF in a new tab"
          >
            <img
              src={preview.thumb_url}
              alt={`${preview.sheets} sheet preview`}
              className="preview-thumb"
              loading="lazy"
            />
          </a>
          <p className="preview-meta">
            {preview.sheets} sheet{preview.sheets !== 1 ? "s" : ""} · click to open full PDF
            {loading && <span className="preview-refresh"> · updating…</span>}
          </p>
          {(() => {
            const totalPerSheet = presets.find((p) => p.key === presetKey)?.total ?? null;
            const explainer = friendlyExplainer(presetKey, totalPerSheet, quantity);
            const showFoldDiagram =
              presetKey != null &&
              (presetKey.startsWith("trifold_") ||
                presetKey.startsWith("bifold_") ||
                presetKey.startsWith("halffold_"));
            if (!explainer && !showFoldDiagram) return null;
            return (
              <>
                {explainer && (
                  <p
                    className="preview-explainer"
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      color: "var(--muted)",
                      lineHeight: 1.5,
                      borderLeft: "2px solid var(--border)",
                      paddingLeft: 10,
                    }}
                  >
                    {explainer}
                  </p>
                )}
                {showFoldDiagram && presetKey && (
                  <div
                    style={{
                      marginTop: 8,
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      paddingLeft: 10,
                    }}
                  >
                    <FoldDiagram presetKey={presetKey} />
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>
                      {presetKey.startsWith("trifold")
                        ? "A folds in first, then C over."
                        : presetKey.startsWith("bifold")
                          ? "Single fold along centerline."
                          : "Single fold, A folds up over B."}
                    </span>
                  </div>
                )}
              </>
            );
          })()}
        </>
      )}
    </div>
  );
}
