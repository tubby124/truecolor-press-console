import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { TestPattern } from "../types";

// Sits on the home view alongside WorkflowTiles. Only renders when stage is
// idle so it doesn't clutter the inspect / done views. The "for the tech
// visit" framing is intentional — these patterns aren't customer artwork,
// they're shop diagnostic tools, and the operator should know that at a
// glance.

const HELP_LINES = [
  {
    when: "After a brownout / power event / cold start",
    pick: "Color blocks",
    why: "Confirms each CMYK channel still lays down clean solids without banding.",
  },
  {
    when: "When colors look 'off' but you can't tell what",
    pick: "Density bar",
    why: "Side-by-side reference for solid K, the four process colors, and a 5-step grayscale.",
  },
  {
    when: "After a transport-belt swap or registration drift complaint",
    pick: "Registration target",
    why: "The CMYK center cross exposes plate-to-plate offset; the corner crosshairs verify head registration.",
  },
];

export function TestPatternTile() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const pushToast = useStore((s) => s.pushToast);
  const [patterns, setPatterns] = useState<TestPattern[] | null>(null);
  const [loading, setLoading] = useState<string | null>(null); // pattern_id printing
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    api.testPatterns().then(setPatterns).catch(() => setPatterns([]));
  }, []);

  if (stage.kind !== "idle") return null;
  if (!patterns || patterns.length === 0) return null;

  async function printPattern(id: string) {
    setLoading(id);
    // Mimic the WorkflowTiles → InspectCard → submitting → done flow so this
    // looks identical to a normal print from the operator's perspective.
    // We don't have a File object here (the source PDF is already on disk on
    // the backend) — synthesize a minimal placeholder so the submitting
    // stage's `file` prop has something to render. The placeholder File
    // never hits the network; the backend uses the bundled PDF.
    const placeholder = new File([new Uint8Array(0)], `test-pattern-${id}.pdf`, {
      type: "application/pdf",
    });
    setStage({ kind: "submitting", file: placeholder });
    pushToast("info", `Spooling ${id}…`);
    try {
      const job = await api.printTestPattern(id);
      setStage({ kind: "done", job });
      pushToast(
        "success",
        job.status === "spooled-dry"
          ? `Spooled (DRY): test pattern ${id}`
          : `Sent to press: test pattern ${id}`,
      );
    } catch (e) {
      pushToast(
        "error",
        `Couldn't print test pattern: ${e instanceof Error ? e.message : e}`,
      );
      setStage({ kind: "idle" });
    } finally {
      setLoading(null);
    }
  }

  return (
    <div
      className="card"
      style={{ marginTop: 24 }}
      data-testid="test-pattern-tile"
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h3 style={{ margin: 0 }}>Calibration patterns — for the tech visit</h3>
        <button
          type="button"
          className="ghost"
          onClick={() => setShowHelp((s) => !s)}
          style={{ fontSize: 12, padding: "2px 8px" }}
          aria-expanded={showHelp}
        >
          {showHelp ? "Hide help" : "What are these?"}
        </button>
      </div>

      {showHelp && (
        <div
          style={{
            marginTop: 10,
            padding: "10px 12px",
            background: "var(--panel-2, #2a2a2e)",
            border: "1px solid var(--border, #333)",
            borderRadius: 6,
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          <p style={{ margin: "0 0 8px", color: "var(--muted)" }}>
            These are bundled diagnostic sheets. Print one when you want to
            verify the press is healthy without burning customer artwork.
          </p>
          {HELP_LINES.map((row) => (
            <div key={row.pick} style={{ marginBottom: 6 }}>
              <strong>{row.when}</strong>
              <span style={{ color: "var(--muted)" }}> → {row.pick}.</span>
              <span style={{ display: "block", color: "var(--muted)", fontSize: 12 }}>
                {row.why}
              </span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {patterns.map((p) => (
          <div
            key={p.id}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto auto",
              gap: 10,
              alignItems: "center",
              padding: "10px 12px",
              border: "1px solid var(--border, #333)",
              borderRadius: 6,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{p.friendly_label}</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                Recommended paper: {p.recommended_stock}
                {p.file_size_kb != null ? ` · ${p.file_size_kb} KB` : ""}
              </div>
            </div>
            <a
              href={api.testPatternPdfUrl(p.id)}
              target="_blank"
              rel="noreferrer"
              className="ghost"
              style={{ fontSize: 12, padding: "4px 10px", textDecoration: "none" }}
              title="Open the bundled PDF in a new tab"
            >
              Preview
            </a>
            <button
              type="button"
              className="cta secondary"
              disabled={loading !== null || !p.available}
              onClick={() => printPattern(p.id)}
              style={{ fontSize: 13, padding: "6px 14px" }}
              title={
                p.available
                  ? `Print ${p.friendly_label}`
                  : "Pattern PDF missing on disk — run scripts/generate_test_patterns.py"
              }
            >
              {loading === p.id ? "Spooling…" : "Print this"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
