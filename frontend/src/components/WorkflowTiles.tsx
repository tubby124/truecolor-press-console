import { useState } from "react";
import { useStore } from "../store";
import { TILES, type WorkflowTile } from "../workflows/tiles";

export function WorkflowTiles() {
  const stage = useStore((s) => s.stage);
  const pushToast = useStore((s) => s.pushToast);
  const [gated, setGated] = useState<WorkflowTile | null>(null);

  if (stage.kind !== "idle") return null;

  function pick(t: WorkflowTile) {
    if (t.presetKey === null) {
      setGated(t);
      return;
    }
    pushToast(
      "info",
      `${t.label} selected — drop a file to continue (or pick saved preset).`
    );
    // Stash the chosen tile in the body data attribute so DropZone reads it
    document.body.dataset.preselectedTile = t.key;
  }

  return (
    <>
      <div className="section-head" style={{ marginTop: 24 }}>
        <h2>Or pick a workflow tile</h2>
        <span className="hint">
          Auto-detect handles most jobs · use a tile to override or for jobs without standard sizes
        </span>
      </div>

      <div className="tile-grid">
        {TILES.map((t) => {
          const disabled = t.presetKey === null;
          return (
            <button
              key={t.key}
              type="button"
              className={`workflow-tile ${disabled ? "gated" : ""} phase-${t.phase}`}
              onClick={() => pick(t)}
              title={t.hint}
            >
              <div className="tile-icon">{t.emoji}</div>
              <div className="tile-label">{t.label}</div>
              <div className="tile-hint">{t.hint}</div>
              {disabled && <div className="tile-badge">{t.phase}</div>}
            </button>
          );
        })}
      </div>

      {gated && (
        <div className="modal-backdrop" onClick={() => setGated(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>
              {gated.emoji} {gated.label} — not yet available
            </h2>
            <p>{gated.hardwareGate}</p>
            <div className="modal-actions">
              <button className="cta" type="button" onClick={() => setGated(null)}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
