import { useEffect, useState } from "react";
import { api } from "./api";
import { HardwareGateBanner, PrinterStatusBanner } from "./components/Banners";
import { BatchCard, BatchSubmittingScreen } from "./components/BatchCard";
import { BatchDoneScreen } from "./components/BatchDoneScreen";
import { DropZone } from "./components/DropZone";
import { FirstRunTrayWizard } from "./components/FirstRunTrayWizard";
import { ImposedPreview, SubmittingScreen } from "./components/ImposedPreview";
import { InspectCard } from "./components/InspectCard";
import { JobHistory } from "./components/JobHistory";
import { SavedPresets } from "./components/SavedPresets";
import { Toasts } from "./components/Toasts";
import { TrayStatusBar } from "./components/TrayStatusBar";
import { WorkflowTiles } from "./components/WorkflowTiles";
import { useStore } from "./store";
import type { Health } from "./types";

export default function App() {
  const stage = useStore((s) => s.stage);
  const reset = useStore((s) => s.reset);
  const trays = useStore((s) => s.trays);
  const setShowHistory = useStore((s) => s.setShowHistory);
  const showHistory = useStore((s) => s.showHistory);
  const [health, setHealth] = useState<Health | null>(null);
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  // First-run tray wizard if config doesn't exist yet
  useEffect(() => {
    if (trays && !trays.configured) setShowWizard(true);
  }, [trays]);

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
        <span className="grow" />
        <button className="ghost" type="button" onClick={() => setShowHistory(true)} title="⌘ + H">
          History
        </button>
        <form action="/logout" method="POST" style={{ display: "inline" }}>
          <button className="ghost" type="submit">Log out</button>
        </form>
      </div>

      <TrayStatusBar />
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
            <WorkflowTiles />
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
    </div>
  );
}
