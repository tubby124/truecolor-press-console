// Top-of-page status banners: hardware gate (dry mode), printer offline,
// and OTA update available.

import { useEffect, useState } from "react";
import { api } from "../api";
import type { UpdateCheck } from "../api";
import type { Health, PrinterStatus } from "../types";

export function HardwareGateBanner({ health }: { health: Health | null }) {
  if (!health) return null;
  if (health.safe_print_mode === "live") return null;
  return (
    <div className="banner dry">
      <strong>DRY MODE</strong> · jobs are spooled to disk but not sent to the press · hardware
      repair pending (C-6753) · see <code>docs/HARDWARE-GATES.md</code>
    </div>
  );
}

export function PrinterStatusBanner() {
  const [status, setStatus] = useState<PrinterStatus | null>(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const s = await api.printer();
        if (alive) setStatus(s);
      } catch {
        if (alive) setStatus({ reachable: false, error: "fetch failed" });
      }
    }
    tick();
    const id = setInterval(tick, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!status) return null;
  if (status.reachable) return null;
  return (
    <div className="banner offline">
      Press at 172.16.1.149 is unreachable — {String(status.error || "no PJL response")}.
      Check network or power.
    </div>
  );
}

// Polls /api/update/check on mount and every 30 min. When a newer release
// is published on GitHub, shows a banner with a button that downloads + swaps
// the bundle, then auto-relaunches. Hidden in dev / Mac (supports_apply=false).
export function UpdateBanner() {
  const [info, setInfo] = useState<UpdateCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const data = await api.updateCheck();
        if (alive) setInfo(data);
      } catch {
        // Silent — no network, GitHub rate-limit, etc. Try again next tick.
      }
    }
    tick();
    const id = setInterval(tick, 30 * 60 * 1000); // 30 min
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!info || !info.update_available) return null;

  // Dev / Mac: show "update available" but no button — user pulls git instead.
  if (!info.supports_apply) {
    return (
      <div className="banner" style={{ background: "#2a3a4a", color: "#cce" }}>
        Update available: {info.tag} (current: v{info.current}). Auto-apply only
        works in the packaged Windows build — pull from git on dev.
      </div>
    );
  }

  async function applyUpdate() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.updateApply();
      if (result.ok) {
        setMessage(result.message || "Update starting — the app will restart in a moment.");
        // Server is about to exit. Stop polling, show the message until restart.
      } else {
        setError(result.error || "Update failed.");
        setBusy(false);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Update request failed.";
      setError(msg);
      setBusy(false);
    }
  }

  return (
    <div
      className="banner"
      style={{
        background: "#234",
        color: "#cdf",
        display: "flex",
        alignItems: "center",
        gap: 12,
        flexWrap: "wrap",
      }}
    >
      <strong>Update available</strong>
      <span>
        {info.tag} {info.name && info.name !== info.tag ? `· ${info.name}` : null} (current:
        v{info.current})
      </span>
      {message ? (
        <span style={{ marginLeft: "auto", color: "#9f9" }}>{message}</span>
      ) : (
        <button
          type="button"
          disabled={busy}
          onClick={applyUpdate}
          style={{
            marginLeft: "auto",
            background: "#39c",
            color: "white",
            border: 0,
            borderRadius: 6,
            padding: "6px 12px",
            cursor: busy ? "wait" : "pointer",
            fontWeight: 600,
          }}
        >
          {busy ? "Downloading..." : "Download & install"}
        </button>
      )}
      {error ? <span style={{ color: "#f99", flexBasis: "100%" }}>{error}</span> : null}
    </div>
  );
}
