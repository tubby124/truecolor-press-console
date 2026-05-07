// Top-of-page status banners: hardware gate (dry mode) and printer offline.

import { useEffect, useState } from "react";
import { api } from "../api";
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
