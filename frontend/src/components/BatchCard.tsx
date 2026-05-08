import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Preset, Stock } from "../types";

export function BatchCard() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const reset = useStore((s) => s.reset);
  const pushToast = useStore((s) => s.pushToast);
  const trays = useStore((s) => s.trays);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const announcedRef = useRef(false);

  useEffect(() => {
    api.presets().then(setPresets).catch(() => {});
    api.stocks().then(setStocks).catch(() => {});
  }, []);

  // One-shot batch-mode-engaged toast so the operator notices that batch
  // mode is now active. Fires the first time we land on batch_pending.
  useEffect(() => {
    if (stage.kind === "batch_pending" && !announcedRef.current) {
      announcedRef.current = true;
      const n = stage.files.length;
      pushToast("info", `Batch mode — ${n} file${n !== 1 ? "s" : ""} queued. Pick paper + layout once below; we'll print all of them.`);
    }
    if (stage.kind === "idle") {
      announcedRef.current = false;
    }
  }, [stage, pushToast]);

  if (stage.kind !== "batch_pending") return null;

  const { files, presetKey, stockCode, quantity, sides } = stage;
  const preset = presets.find((p) => p.key === presetKey);
  const stock = stocks.find((s) => s.code === stockCode);

  const loadedTray =
    trays && stockCode
      ? Object.entries(trays.trays).find(([, t]) => t.stock_code === stockCode)?.[0] ?? null
      : null;

  const update = <K extends keyof typeof stage>(k: K, v: (typeof stage)[K]) =>
    setStage({ ...stage, [k]: v });

  const removeFile = (idx: number) => {
    const next = files.filter((_, i) => i !== idx);
    if (next.length === 0) {
      reset();
      return;
    }
    if (next.length === 1) {
      pushToast("info", "Down to one file — drop it again to use single-file inspect.");
      reset();
      return;
    }
    setStage({ ...stage, files: next });
  };

  const submit = async () => {
    setStage({ kind: "batch_submitting", files });
    try {
      const results = await api.submitBatch({
        files,
        workflow: "batch",
        preset_key: presetKey,
        stock_code: stockCode,
        quantity,
        sides,
      });
      const errs = results.filter((r) => r.error).length;
      const oks = results.length - errs;
      if (errs > 0) {
        pushToast("warn", `${oks} succeeded, ${errs} failed — see results below.`);
      } else {
        pushToast("success", `Batched ${oks} job${oks !== 1 ? "s" : ""}.`);
      }
      setStage({ kind: "batch_done", results });
    } catch (e) {
      pushToast("error", `Batch failed: ${e instanceof Error ? e.message : e}`);
      setStage({ kind: "idle" });
    }
  };

  const sheetsPerFile = preset ? Math.ceil(quantity / preset.total) : 0;
  const totalSheets = sheetsPerFile * files.length;

  return (
    <div>
      <div className="section-head">
        <h2>Batch · {files.length} files</h2>
        <span className="hint">
          One workflow + paper applied to every file. Each file becomes its own job.
        </span>
      </div>

      <div className="card">
        <h3>Files in this batch</h3>
        <ul className="batch-file-list">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="batch-file-row">
              <span className="batch-file-name">{f.name}</span>
              <span className="batch-file-size">{(f.size / 1024).toFixed(0)} KB</span>
              <button
                className="batch-file-remove"
                type="button"
                onClick={() => removeFile(i)}
                title="Remove from batch"
                aria-label={`Remove ${f.name}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>

        <h3 style={{ marginTop: 18 }}>Apply to all</h3>
        <div className="recommendation-grid">
          <div className="key">Layout</div>
          <div>
            <select value={presetKey} onChange={(e) => update("presetKey", e.target.value)}>
              {presets.map((p) => (
                <option key={p.key} value={p.key} title={`${p.total}-up ${p.piece} on ${p.sheet}`}>
                  {p.friendly_label && p.friendly_label.length > 0
                    ? p.friendly_label
                    : `${p.total}-up ${p.piece} on ${p.sheet}`}
                </option>
              ))}
            </select>
          </div>

          <div className="key">Paper</div>
          <div>
            <select value={stockCode} onChange={(e) => update("stockCode", e.target.value)}>
              {stocks.map((s) => (
                <option key={s.code} value={s.code} title={`${s.name} · ${s.weight}`}>
                  {s.friendly_name || s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="key">Tray</div>
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

          <div className="key">Quantity / file</div>
          <div>
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => update("quantity", Math.max(1, parseInt(e.target.value || "1", 10)))}
              style={{ width: 100 }}
            />
            {preset && (
              <span style={{ marginLeft: 8, color: "var(--muted)" }}>
                = {sheetsPerFile} sheet{sheetsPerFile !== 1 ? "s" : ""} per file ·{" "}
                {totalSheets} total across {files.length} files
              </span>
            )}
          </div>

          <div className="key">Sides</div>
          <div>
            <label style={{ marginRight: 12 }}>
              <input
                type="radio"
                name="batch-sides"
                checked={sides === 1}
                onChange={() => update("sides", 1)}
              />{" "}
              1-sided
            </label>
            <label>
              <input
                type="radio"
                name="batch-sides"
                checked={sides === 2}
                onChange={() => update("sides", 2)}
              />{" "}
              2-sided
            </label>
          </div>
        </div>

        <div className="cta-row">
          <button className="cta" type="button" onClick={submit}>
            Print {files.length} files
          </button>
          <button className="cta danger" type="button" onClick={reset} title="Discard and start over (Esc)">
            Discard
          </button>
        </div>
      </div>
    </div>
  );
}

export function BatchSubmittingScreen() {
  const stage = useStore((s) => s.stage);
  if (stage.kind !== "batch_submitting") return null;
  return (
    <div className="card" style={{ textAlign: "center", padding: 32 }}>
      <h2>
        <span className="spinner" /> Imposing {stage.files.length} files…
      </h2>
      <p style={{ color: "var(--muted)" }}>
        Normalizing, preflighting, and laying out every file. Stay on this page.
      </p>
    </div>
  );
}
