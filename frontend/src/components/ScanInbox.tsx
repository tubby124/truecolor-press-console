// Scanner inbox tile — shows scans the C3070 has dropped into the operator's
// watch folder via Scan-to-SMB. Polls every 5s; renders nothing if empty so
// it doesn't take up space when there's nothing to do.
//
// "Inspect & print" pulls the file into the standard /api/inspect pipeline
// and transitions the store to `inspected` — same UX as a normal drag-drop.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { ScanItem } from "../types";

const POLL_MS = 5000;

function formatModified(iso: string): string {
  try {
    const d = new Date(iso);
    const diffSec = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (diffSec < 60) return "just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function formatSize(kb: number): string {
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

export function ScanInbox() {
  const stage = useStore((s) => s.stage);
  const setStage = useStore((s) => s.setStage);
  const pushToast = useStore((s) => s.pushToast);
  const [items, setItems] = useState<ScanItem[]>([]);
  const [importing, setImporting] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await api.scanInbox();
      setItems(res.items);
    } catch {
      // Silent fail — scanner is optional. Don't toast on every poll.
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => {
      void refresh();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [refresh]);

  async function importScan(filename: string) {
    setImporting(filename);
    try {
      const result = await api.scanImport(filename);

      // Reconstruct a File object so InspectCard / submitJob can reuse the
      // existing /api/job multipart pipeline. The /api/scan/file/<name>
      // endpoint serves the bytes that just landed in _inspect/.
      const importedName = result.filename;
      const fileRes = await fetch(
        `/api/scan/file/${encodeURIComponent(importedName)}`,
        { credentials: "same-origin" }
      );
      if (!fileRes.ok) {
        throw new Error(`Couldn't read imported scan back: ${fileRes.status}`);
      }
      const blob = await fileRes.blob();
      const file = new File([blob], importedName, {
        type: blob.type || "application/pdf",
      });

      const stockCode = result.detected?.stock_code ?? "14pt-cs-gloss";
      const presetKey = result.detected?.preset_key ?? "bc_21up_12x18";
      const quantity = result.suggested_quantity || 100;

      setStage({
        kind: "inspected",
        file,
        result,
        quantity,
        sides: 1,
        stockCode,
        presetKey,
      });
      pushToast("success", `Imported scan ${importedName}`);
      await refresh();
    } catch (e) {
      pushToast(
        "error",
        `Scan import failed: ${e instanceof Error ? e.message : e}`
      );
    } finally {
      setImporting(null);
    }
  }

  async function dismiss(filename: string) {
    try {
      await api.scanDismiss(filename);
      pushToast("info", `Dismissed ${filename}`);
      await refresh();
    } catch (e) {
      pushToast(
        "error",
        `Dismiss failed: ${e instanceof Error ? e.message : e}`
      );
    }
  }

  // Only show on the home view, and only if there's at least one scan.
  if (stage.kind !== "idle") return null;
  if (items.length === 0) return null;

  return (
    <>
      <div className="section-head" style={{ marginTop: 24 }}>
        <h2>New scan from press</h2>
        <span className="hint">
          {items.length === 1
            ? "1 file waiting"
            : `${items.length} files waiting`}{" "}
          · auto-refreshes every 5s
        </span>
      </div>
      <div className="saved-grid">
        {items.map((item) => {
          const isTrash = item.suggested_workflow === "trash";
          const busy = importing === item.filename;
          return (
            <div key={item.filename} className="saved-tile">
              <div className="saved-pick" style={{ cursor: "default" }}>
                <div className="saved-name" title={item.filename}>
                  {item.filename}
                </div>
                <div className="saved-meta">
                  {formatSize(item.size_kb)} · {formatModified(item.modified_at)}
                </div>
                <div className="saved-meta">
                  {isTrash
                    ? "Unsupported file type — dismiss it"
                    : "Ready to inspect & print"}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  {!isTrash && (
                    <button
                      type="button"
                      className="cta"
                      style={{ flex: 1 }}
                      disabled={busy}
                      onClick={() => void importScan(item.filename)}
                    >
                      {busy ? <span className="spinner" /> : "Inspect & print"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="cta secondary"
                    style={{ flex: isTrash ? 1 : undefined }}
                    disabled={busy}
                    onClick={() => void dismiss(item.filename)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
