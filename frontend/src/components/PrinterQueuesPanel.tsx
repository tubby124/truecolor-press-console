import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";

type QueueState = {
  booklet: string;
  stapled: string;
  punched: string;
};

const EMPTY: QueueState = { booklet: "", stapled: "", punched: "" };

const KIND_LABELS: Record<keyof QueueState, { label: string; hint: string; preset: string }> = {
  booklet: {
    label: "Booklet (saddle-stitch + fold)",
    hint: "Konica driver preset: BM-660 booklet maker on, saddle-stitch on, half-fold on, output bin = booklet tray.",
    preset: "C3070 Booklet",
  },
  stapled: {
    label: "Stapled document",
    hint: "Konica driver preset: corner staple top-left, no fold, standard output bin.",
    preset: "C3070 Stapled",
  },
  punched: {
    label: "Hole-punched document",
    hint: "Konica driver preset: 3-hole punch on left edge, no staple, standard output bin.",
    preset: "C3070 Punched",
  },
};

export function PrinterQueuesPanel() {
  const pushToast = useStore((s) => s.pushToast);
  const [supported, setSupported] = useState<boolean | null>(null);
  const [sumatra, setSumatra] = useState<string>("");
  const [state, setState] = useState<QueueState>(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.printerQueues()
      .then((r) => {
        setSupported(r.supported);
        setSumatra(r.sumatra_exe);
        setState({
          booklet: r.queues.booklet || "",
          stapled: r.queues.stapled || "",
          punched: r.queues.punched || "",
        });
      })
      .catch((e) => pushToast("error", `Couldn't load printer queues: ${e.message}`));
  }, [pushToast]);

  async function save() {
    setSaving(true);
    try {
      const r = await api.setPrinterQueues(state);
      pushToast("success", "Printer queues saved.");
      setState({
        booklet: r.queues.booklet || "",
        stapled: r.queues.stapled || "",
        punched: r.queues.punched || "",
      });
    } catch (e) {
      pushToast("error", `Save failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section style={{ marginTop: 32, padding: 16, border: "1px solid var(--border)", borderRadius: 8 }}>
      <h3 style={{ marginTop: 0 }}>Auto-finish printer queues</h3>
      <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
        The press's booklet maker, stapler, and hole punch are controlled by Konica's print driver — not raw PJL.
        On the Windows shop PC, set up the Konica AccurioPress C3070 driver multiple times under different names,
        each with a different finishing preset baked in. Enter those queue names below.
      </p>
      {supported === false && (
        <div className="warn-box" style={{ margin: "12px 0", padding: 10, border: "1px dashed var(--warn)", borderRadius: 6 }}>
          ⚠ This machine isn't Windows — auto-finish jobs will fall back to plain print + manual fold/staple.
          The queue names below still save; they'll take effect when the staff PC OTA-updates and uses the same config.
        </div>
      )}
      <p style={{ fontSize: 12, color: "var(--muted)" }}>
        SumatraPDF expected at: <code>{sumatra}</code>
      </p>

      <div style={{ display: "grid", gap: 16, marginTop: 16 }}>
        {(Object.keys(KIND_LABELS) as (keyof QueueState)[]).map((kind) => {
          const meta = KIND_LABELS[kind];
          return (
            <div key={kind}>
              <label style={{ display: "block", fontWeight: 600, fontSize: 14 }}>
                {meta.label}
              </label>
              <div style={{ fontSize: 12, color: "var(--muted)", margin: "4px 0 6px" }}>
                {meta.hint}
              </div>
              <input
                type="text"
                value={state[kind]}
                placeholder={meta.preset}
                onChange={(e) => setState((s) => ({ ...s, [kind]: e.target.value }))}
                style={{
                  width: "100%", padding: "8px 12px", fontSize: 14,
                  border: "1px solid var(--border)", borderRadius: 6,
                  background: "var(--bg)", color: "var(--text)",
                }}
              />
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <button className="cta" type="button" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save queue names"}
        </button>
      </div>
    </section>
  );
}
