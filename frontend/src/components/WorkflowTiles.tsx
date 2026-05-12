import { useState } from "react";
import { useStore } from "../store";
import { TILES, type WorkflowTile } from "../workflows/tiles";

// Status pill colors + labels matching tile.status from tiles.ts. Surfaces
// at a glance whether a tile is production-ready, blocked, or untested.
const STATUS_PILL: Record<string, { bg: string; fg: string; label: string }> = {
  confirmed:          { bg: "#1f6b3a", fg: "#fff",     label: "✓ Confirmed" },
  "manual-finish":    { bg: "#a86b00", fg: "#fff",     label: "⚠ Manual finish" },
  "hardware-blocked": { bg: "#c1272d", fg: "#fff",     label: "✗ Blocked" },
  untested:           { bg: "#374151", fg: "#e5e7eb", label: "? Untested" },
};

export function WorkflowTiles() {
  const stage = useStore((s) => s.stage);
  const pushToast = useStore((s) => s.pushToast);
  const [gated, setGated] = useState<WorkflowTile | null>(null);
  const [info, setInfo] = useState<WorkflowTile | null>(null);

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
          const pill = t.status ? STATUS_PILL[t.status] : null;
          return (
            <button
              key={t.key}
              type="button"
              className={`workflow-tile ${disabled ? "gated" : ""} phase-${t.phase}`}
              onClick={() => pick(t)}
              title={t.tip || t.hint}
              style={{ position: "relative" }}
            >
              <div className="tile-icon">{t.emoji}</div>
              <div className="tile-label">{t.label}</div>
              <div className="tile-hint">{t.hint}</div>
              {pill && (
                <div
                  style={{
                    marginTop: 6,
                    display: "inline-block",
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "2px 8px",
                    borderRadius: 999,
                    background: pill.bg,
                    color: pill.fg,
                    letterSpacing: 0.3,
                  }}
                >
                  {pill.label}
                </div>
              )}
              {(t.finisher?.staple || t.finisher?.punch || t.finisher?.fold) && (
                <div
                  style={{
                    marginTop: 4,
                    fontSize: 10,
                    color: "var(--muted, #888)",
                    lineHeight: 1.3,
                  }}
                >
                  {[t.finisher.staple, t.finisher.punch, t.finisher.fold]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              )}
              {t.tip && (
                <span
                  role="button"
                  aria-label="What this tile does"
                  onClick={(e) => {
                    e.stopPropagation();
                    setInfo(t);
                  }}
                  style={{
                    position: "absolute",
                    top: 6,
                    right: 6,
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    background: "var(--panel-2, #2a2a2e)",
                    color: "var(--muted, #888)",
                    fontSize: 10,
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "help",
                  }}
                >
                  ?
                </span>
              )}
              {disabled && <div className="tile-badge">{t.phase}</div>}
            </button>
          );
        })}
      </div>

      {info && (
        <div className="modal-backdrop" onClick={() => setInfo(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <h2>
              {info.emoji} {info.label}
            </h2>
            {info.tip && <p style={{ lineHeight: 1.55 }}>{info.tip}</p>}
            {info.finisher && (
              <div
                style={{
                  marginTop: 12,
                  padding: "10px 12px",
                  background: "var(--panel-2, #2a2a2e)",
                  border: "1px solid var(--border, #333)",
                  borderRadius: 6,
                  fontSize: 13,
                  lineHeight: 1.55,
                }}
              >
                <strong>Finisher action:</strong>
                <ul style={{ margin: "6px 0 0 16px", padding: 0 }}>
                  {info.finisher.staple && <li>Staple: {info.finisher.staple}</li>}
                  {info.finisher.punch && <li>Punch: {info.finisher.punch}</li>}
                  {info.finisher.fold && <li>Fold: {info.finisher.fold}</li>}
                  {info.finisher.output && <li>Output: {info.finisher.output}</li>}
                </ul>
              </div>
            )}
            {info.statusNote && (
              <p
                style={{
                  marginTop: 10,
                  fontSize: 12,
                  color: "var(--muted, #888)",
                  fontStyle: "italic",
                }}
              >
                Note: {info.statusNote}
              </p>
            )}
            <div className="modal-actions">
              <button className="cta" type="button" onClick={() => setInfo(null)}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

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
