import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { PreviewResult } from "../types";

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
            if (!explainer) return null;
            return (
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
            );
          })()}
        </>
      )}
    </div>
  );
}
