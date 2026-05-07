import { useEffect, useState } from "react";
import { useStore } from "../store";

interface SavedPreset {
  name: string;
  workflow: string;
  preset_key: string;
  stock_code: string;
  quantity: number;
  sides: number;
  updated_at: string;
}

export function SavedPresets() {
  const stage = useStore((s) => s.stage);
  const pushToast = useStore((s) => s.pushToast);
  const [presets, setPresets] = useState<SavedPreset[]>([]);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    fetch("/api/saved-presets", { credentials: "same-origin" })
      .then((r) => r.json())
      .then(setPresets)
      .catch(() => setPresets([]));
  }, [refreshTick]);

  async function deleteOne(name: string) {
    if (!confirm(`Delete saved preset "${name}"?`)) return;
    try {
      await fetch(`/api/saved-presets/${encodeURIComponent(name)}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      pushToast("success", `Deleted "${name}"`);
      setRefreshTick((n) => n + 1);
    } catch (e) {
      pushToast("error", `Delete failed: ${e instanceof Error ? e.message : e}`);
    }
  }

  function pick(p: SavedPreset) {
    document.body.dataset.preselectedTile = "saved:" + p.name;
    document.body.dataset.savedPresetJson = JSON.stringify(p);
    pushToast(
      "info",
      `Loaded "${p.name}" — drop a file to apply.`
    );
  }

  if (stage.kind !== "idle") return null;
  if (!presets.length) return null;

  return (
    <>
      <div className="section-head" style={{ marginTop: 24 }}>
        <h2>Saved presets</h2>
        <span className="hint">One-click recall · drop a file after picking one</span>
      </div>
      <div className="saved-grid">
        {presets.map((p) => (
          <div key={p.name} className="saved-tile">
            <button type="button" className="saved-pick" onClick={() => pick(p)} title="Use this preset">
              <div className="saved-name">{p.name}</div>
              <div className="saved-meta">
                {p.workflow} · {p.quantity} pcs · {p.sides === 2 ? "2-sided" : "1-sided"}
              </div>
              <div className="saved-meta">
                {p.preset_key.replace(/_/g, " ")} · {p.stock_code}
              </div>
            </button>
            <button
              type="button"
              className="saved-delete"
              onClick={() => deleteOne(p.name)}
              title="Delete saved preset"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

export function SaveCurrentAsPreset() {
  const stage = useStore((s) => s.stage);
  const pushToast = useStore((s) => s.pushToast);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  if (stage.kind !== "inspected") return null;

  async function save() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await fetch("/api/saved-presets", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          workflow: stage.kind === "inspected" ? stage.result.detected?.workflow ?? "custom" : "custom",
          preset_key: stage.kind === "inspected" ? stage.presetKey : "",
          stock_code: stage.kind === "inspected" ? stage.stockCode : "",
          quantity: stage.kind === "inspected" ? stage.quantity : 1,
          sides: stage.kind === "inspected" ? stage.sides : 1,
        }),
      });
      pushToast("success", `Saved as "${name.trim()}"`);
      setOpen(false);
      setName("");
    } catch (e) {
      pushToast("error", `Save failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="cta secondary"
        onClick={() => setOpen(true)}
        title="Save these settings for one-click recall later"
      >
        Save preset
      </button>
      {open && (
        <div className="modal-backdrop" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Save current settings as preset</h2>
            <p>Name it something the next operator will recognize.</p>
            <div className="tray-editor-row">
              <label>Name</label>
              <input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Hasan BC 14pt matte"
              />
            </div>
            <div className="modal-actions">
              <button className="cta secondary" type="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className="cta" type="button" onClick={save} disabled={!name.trim() || saving}>
                {saving ? <span className="spinner" /> : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
