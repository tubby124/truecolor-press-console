// Live press status pill + expandable card.
//
// Polls /api/press/state every 30s. The backend caches at 15s, so worst case
// the operator sees data ~45s old. The "Refresh" button calls
// /api/press/state/refresh which bypasses the cache.
//
// This sits next to PrinterStatusBanner — that one only knows "PJL reachable
// or not". This one tells the operator *what* is loaded and *why* the press
// is unhappy, sourced from the Standard Printer MIB over SNMP.

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { PressAlert, PressLiveState, PressTrayState } from "../types";

const POLL_INTERVAL_MS = 30_000;

function summarize(state: PressLiveState | null): { label: string; tone: "ok" | "warn" | "danger" | "muted" } {
  if (!state) return { label: "Press: …", tone: "muted" };
  if (!state.reachable) return { label: "Press: not reachable", tone: "danger" };

  const critical = state.alerts.find((a) => a.severity === "critical");
  if (critical) {
    const desc = critical.description?.trim();
    return { label: `Press: ${desc || "critical alert"}`, tone: "danger" };
  }
  const warning = state.alerts.find((a) => a.severity === "warning");
  if (warning) {
    const desc = warning.description?.trim();
    return { label: `Press: ${desc || "warning"}`, tone: "warn" };
  }
  // Tray-empty surfacing even if the press hasn't elevated it to a critical alert.
  for (const [id, t] of Object.entries(state.trays)) {
    if (t.level_label === "empty") {
      return { label: `Press: tray ${id} empty`, tone: "warn" };
    }
  }
  if (state.device_status?.printer_status === "printing") {
    return { label: "Press: printing", tone: "ok" };
  }
  if (state.device_status?.printer_status === "warmup") {
    return { label: "Press: warming up", tone: "warn" };
  }
  return { label: "Press: ready", tone: "ok" };
}

function toneStyle(tone: "ok" | "warn" | "danger" | "muted"): React.CSSProperties {
  // Reuse the design tokens already wired in styles.css.
  const map: Record<typeof tone, { bg: string; fg: string; border: string }> = {
    ok: { bg: "rgba(65,201,119,0.12)", fg: "var(--success)", border: "rgba(65,201,119,0.35)" },
    warn: { bg: "rgba(244,186,58,0.12)", fg: "var(--warn)", border: "rgba(244,186,58,0.4)" },
    danger: { bg: "rgba(255,92,92,0.14)", fg: "var(--danger)", border: "rgba(255,92,92,0.4)" },
    muted: { bg: "var(--panel-2)", fg: "var(--muted)", border: "var(--border)" },
  };
  const c = map[tone];
  return {
    background: c.bg,
    color: c.fg,
    border: `1px solid ${c.border}`,
    padding: "4px 10px",
    borderRadius: 999,
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  };
}

function levelBarColor(label: PressTrayState["level_label"]): string {
  switch (label) {
    case "empty":
      return "var(--danger)";
    case "low":
      return "var(--warn)";
    case "ok":
    case "full":
      return "var(--success)";
    default:
      return "var(--muted)";
  }
}

function severityColor(sev: PressAlert["severity"]): string {
  switch (sev) {
    case "critical":
      return "var(--danger)";
    case "warning":
      return "var(--warn)";
    default:
      return "var(--muted)";
  }
}

export function PressLiveStatus() {
  const [state, setState] = useState<PressLiveState | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const aliveRef = useRef(true);

  const tick = useCallback(async () => {
    setLoading(true);
    try {
      const s = await api.pressState();
      if (aliveRef.current) setState(s);
    } catch (e) {
      if (aliveRef.current) {
        setState((prev) =>
          prev
            ? { ...prev, reachable: false, error: (e as Error).message }
            : {
                ts: new Date().toISOString(),
                host: "",
                reachable: false,
                snmp_available: false,
                trays: {},
                alerts: [],
                lifetime_pagecount: null,
                device_status: null,
                error: (e as Error).message,
                cached: false,
              },
        );
      }
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const s = await api.pressStateRefresh();
      if (aliveRef.current) setState(s);
    } catch (e) {
      if (aliveRef.current && state) {
        setState({ ...state, error: (e as Error).message });
      }
    } finally {
      if (aliveRef.current) setRefreshing(false);
    }
  }, [state]);

  useEffect(() => {
    aliveRef.current = true;
    tick();
    const id = window.setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      aliveRef.current = false;
      window.clearInterval(id);
    };
  }, [tick]);

  const summary = summarize(state);
  const trayEntries = state ? Object.entries(state.trays) : [];

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        type="button"
        style={toneStyle(summary.tone)}
        onClick={() => setExpanded((e) => !e)}
        title={
          state?.cached
            ? `Last refreshed ${new Date(state.ts).toLocaleTimeString()} (cached)`
            : state
            ? `Last refreshed ${new Date(state.ts).toLocaleTimeString()}`
            : "Loading…"
        }
        aria-expanded={expanded}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            background: "currentColor",
            opacity: loading ? 0.5 : 1,
          }}
        />
        {summary.label}
      </button>

      {expanded && (
        <div
          role="dialog"
          aria-label="Press live status detail"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: 380,
            maxHeight: "70vh",
            overflowY: "auto",
            background: "var(--panel)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            boxShadow: "var(--shadow)",
            padding: 14,
            zIndex: 50,
            color: "var(--text)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <strong style={{ fontSize: 13 }}>Live Press State</strong>
            <span style={{ flex: 1 }} />
            <button
              type="button"
              className="ghost"
              onClick={refresh}
              disabled={refreshing}
              style={{ fontSize: 11 }}
              title="Bypass the 15s cache and re-query SNMP"
            >
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => setExpanded(false)}
              style={{ fontSize: 11 }}
              aria-label="Close"
            >
              Close
            </button>
          </div>

          {state?.error && (
            <div
              style={{
                background: "rgba(255,92,92,0.10)",
                border: "1px solid rgba(255,92,92,0.3)",
                color: "var(--danger)",
                fontSize: 12,
                padding: "6px 8px",
                borderRadius: 6,
                marginBottom: 10,
              }}
            >
              {state.error}
            </div>
          )}

          {state && (
            <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
              {state.host || "—"} ·{" "}
              {state.reachable ? "reachable" : "offline"} ·{" "}
              {state.snmp_available ? (state.snmp_used ? "SNMP" : "SNMP idle") : "PJL only"}{" "}
              {state.cached && "· cached"}
              {state.lifetime_pagecount != null && (
                <>
                  {" · "}
                  <strong style={{ color: "var(--text)" }}>
                    {state.lifetime_pagecount.toLocaleString()}
                  </strong>{" "}
                  lifetime pages
                </>
              )}
            </div>
          )}

          {/* Trays */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.4 }}>
              Trays · live
            </div>
            {trayEntries.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                {state?.snmp_available ? "No tray data yet." : "Tray state requires SNMP."}
              </div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {trayEntries.map(([id, t]) => (
                  <div
                    key={id}
                    style={{
                      background: "var(--panel-2)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      padding: 8,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                      <strong>{t.description || `Tray ${id}`}</strong>
                      <span style={{ color: "var(--muted)" }}>
                        {t.paper_size || "—"} · {t.paper_type || "—"}
                      </span>
                    </div>
                    <div
                      style={{
                        marginTop: 6,
                        height: 6,
                        background: "var(--bg)",
                        borderRadius: 3,
                        overflow: "hidden",
                      }}
                      aria-label={`Level ${t.level_label}`}
                    >
                      <div
                        style={{
                          width: `${t.level_pct ?? (t.level_label === "low" ? 10 : 0)}%`,
                          height: "100%",
                          background: levelBarColor(t.level_label),
                          transition: "width 200ms ease",
                        }}
                      />
                    </div>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                      {t.level_pct != null ? `${t.level_pct}%` : t.level_label}
                      {t.capacity ? ` of ${t.capacity}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Alerts */}
          <div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.4 }}>
              Alerts
            </div>
            {state && state.alerts.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--muted)" }}>None active.</div>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
                {state?.alerts.map((a) => (
                  <li
                    key={a.id}
                    style={{
                      fontSize: 12,
                      borderLeft: `3px solid ${severityColor(a.severity)}`,
                      paddingLeft: 8,
                    }}
                  >
                    <div style={{ fontWeight: 500 }}>
                      {a.description || `Alert ${a.code ?? a.id}`}
                    </div>
                    <div style={{ color: "var(--muted)", fontSize: 11 }}>
                      {a.severity} · {a.group}
                      {a.code != null ? ` · code ${a.code}` : ""}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
