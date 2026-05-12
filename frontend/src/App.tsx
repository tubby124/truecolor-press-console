import { useEffect, useState } from "react";
import { api } from "./api";
import { HardwareGateBanner, PrinterStatusBanner, UpdateBanner } from "./components/Banners";
import { BatchCard, BatchSubmittingScreen } from "./components/BatchCard";
import { BatchDoneScreen } from "./components/BatchDoneScreen";
import { DropZone } from "./components/DropZone";
import { FirstRunTour } from "./components/FirstRunTour";
import { FirstRunTrayWizard } from "./components/FirstRunTrayWizard";
import { ImposedPreview, SubmittingScreen } from "./components/ImposedPreview";
import { InspectCard } from "./components/InspectCard";
import { JobHistory } from "./components/JobHistory";
import { PressLiveStatus } from "./components/PressLiveStatus";
import { PrinterQueuesPanel } from "./components/PrinterQueuesPanel";
import { SavedPresets } from "./components/SavedPresets";
import { ScanInbox } from "./components/ScanInbox";
import { StopButton } from "./components/StopButton";
import { TestPatternTile } from "./components/TestPatternTile";
import { Toasts } from "./components/Toasts";
import { TrayStatusBar } from "./components/TrayStatusBar";
import { WorkflowTiles } from "./components/WorkflowTiles";
import { useStore } from "./store";
import type { Health, Job } from "./types";

function timeShort(iso: string): string {
  // ISO from backend is UTC. Render in operator-local time, no seconds.
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function LastJobPill({ job, onDismiss }: { job: Job; onDismiss: () => void }) {
  // Click anywhere on the pill (except the ✕) opens the imposed PDF in a new
  // tab. The ✕ stops propagation so dismiss doesn't also fire the open-PDF
  // handler.
  const open = () => {
    if (job.imposed_path) {
      window.open(api.imposedPdfUrl(job.job_id), "_blank", "noopener");
    }
  };
  return (
    <button
      type="button"
      onClick={open}
      title={`Open imposed PDF for ${job.workflow}`}
      style={{
        marginLeft: 12,
        background: "var(--panel-2, #2a2a2e)",
        color: "var(--text, #f5f5f5)",
        border: "1px solid var(--border, #333)",
        borderRadius: 999,
        padding: "4px 8px 4px 12px",
        fontSize: 12,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        cursor: job.imposed_path ? "pointer" : "default",
      }}
    >
      <span>
        Last: <strong>{job.workflow}</strong> · {job.sheets} sheet{job.sheets !== 1 ? "s" : ""} · {timeShort(job.created_at)}
      </span>
      <span
        role="button"
        aria-label="Dismiss last-job pill"
        onClick={(e) => {
          e.stopPropagation();
          onDismiss();
        }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 18,
          height: 18,
          borderRadius: 999,
          background: "var(--panel, #1a1a1d)",
          color: "var(--muted, #888)",
          fontSize: 12,
          lineHeight: 1,
          cursor: "pointer",
        }}
      >
        ×
      </span>
    </button>
  );
}

export default function App() {
  const stage = useStore((s) => s.stage);
  const reset = useStore((s) => s.reset);
  const trays = useStore((s) => s.trays);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const showHistory = useStore((s) => s.showHistory);
  const lastJob = useStore((s) => s.lastJob);
  const lastJobAck = useStore((s) => s.lastJobAck);
  const setLastJob = useStore((s) => s.setLastJob);
  const ackLastJob = useStore((s) => s.ackLastJob);
  const [health, setHealth] = useState<Health | null>(null);
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  // First-run tray wizard if config doesn't exist yet
  useEffect(() => {
    if (trays && !trays.configured) setShowWizard(true);
  }, [trays]);

  // Capture every successful print into the last-job pill. setLastJob
  // resets the ack flag when the job_id changes, so a new print
  // automatically replaces a dismissed pill from the previous job.
  useEffect(() => {
    if (stage.kind === "done") {
      setLastJob(stage.job);
    }
  }, [stage, setLastJob]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (e.key === "Escape") {
        if (showHistory) {
          setShowHistory(false);
        } else if (
          stage.kind === "inspected" ||
          stage.kind === "done" ||
          stage.kind === "batch_pending" ||
          stage.kind === "batch_done"
        ) {
          reset();
        }
      }
      if (meta && e.key.toLowerCase() === "h") {
        e.preventDefault();
        setShowHistory(!showHistory);
      }
      if (meta && e.key === "Enter" && stage.kind === "inspected") {
        e.preventDefault();
        document
          .querySelector<HTMLButtonElement>(".cta-row .cta:not(.secondary):not(.danger)")
          ?.click();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stage.kind, showHistory, reset, setShowHistory]);

  return (
    <div className={`shell ${health?.safe_print_mode === "dry" ? "dry-mode" : ""}`}>
      <div className="topbar">
        <span className="brand">True Color · Press Console</span>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          C3070 @ 172.16.1.149 · v{health?.version ?? "—"}
        </span>
        {lastJob && !lastJobAck && (
          <LastJobPill job={lastJob} onDismiss={ackLastJob} />
        )}
        <span className="grow" />
        <PressLiveStatus />
        <StopButton />
        <button
          className="ghost"
          type="button"
          onClick={() => {
            try {
              localStorage.removeItem("pressConsole.tourCompleted");
            } catch {
              // ignore
            }
            window.location.reload();
          }}
          title="Replay the 3-step intro popover"
        >
          Show tour
        </button>
        <button className="ghost" type="button" onClick={() => setShowHistory(true)} title="⌘ + H">
          History
        </button>
        <form action="/logout" method="POST" style={{ display: "inline" }}>
          <button className="ghost" type="submit">Log out</button>
        </form>
      </div>

      <TrayStatusBar />
      <UpdateBanner />
      <HardwareGateBanner health={health} />
      <PrinterStatusBanner />

      <main className="main">
        {showWizard && <FirstRunTrayWizard onDone={() => setShowWizard(false)} />}

        {stage.kind === "idle" && (
          <>
            <DropZone />
            <p className="empty-hint" style={{ marginTop: 18 }}>
              Tip · ⌘H opens recent jobs · accepts PDF, AI, PSD, PNG, JPG, TIFF, EPS
            </p>
            <SavedPresets />
            <ScanInbox />
            <WorkflowTiles />
            <TestPatternTile />
            <PrinterQueuesPanel />
          </>
        )}

        {stage.kind === "inspecting" && <DropZone />}

        {stage.kind === "inspected" && <InspectCard />}

        {stage.kind === "submitting" && <SubmittingScreen />}

        {stage.kind === "done" && <ImposedPreview />}

        {stage.kind === "batch_pending" && <BatchCard />}

        {stage.kind === "batch_submitting" && <BatchSubmittingScreen />}

        {stage.kind === "batch_done" && <BatchDoneScreen />}
      </main>

      <JobHistory />
      <Toasts />
      <FirstRunTour />
    </div>
  );
}
