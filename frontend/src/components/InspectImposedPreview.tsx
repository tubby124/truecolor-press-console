import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { PreviewResult } from "../types";

export function InspectImposedPreview() {
  const stage = useStore((s) => s.stage);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pull primitives so the effect dep-array is stable across re-renders.
  const fileName = stage.kind === "inspected" ? stage.file.name : null;
  const presetKey = stage.kind === "inspected" ? stage.presetKey : null;
  const stockCode = stage.kind === "inspected" ? stage.stockCode : null;
  const quantity = stage.kind === "inspected" ? stage.quantity : null;
  const sides = stage.kind === "inspected" ? stage.sides : null;

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
        </>
      )}
    </div>
  );
}
