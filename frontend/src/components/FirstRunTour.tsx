// 3-step guided popover that runs once per machine. Steps:
//   1. DropZone (when idle)
//   2. Recommendation card (after first inspect)
//   3. Print button (still on inspected)
// Stored complete-flag: localStorage["pressConsole.tourCompleted"] = "1".
// Targets use data-tour="<key>" attributes so we can reposition without
// coupling to component internals.

import { useEffect, useState } from "react";
import { useStore } from "../store";

const TOUR_KEY = "pressConsole.tourCompleted";

type StepKey = "drop" | "recommendation" | "print" | "done";

interface Step {
  key: StepKey;
  target: string; // data-tour=<value>
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    key: "drop",
    target: "dropzone",
    title: "Drop a file here",
    body:
      "Drag any design (PDF, JPG, PNG, AI, PSD) onto this box, or click it to pick from your computer. " +
      "We'll figure out what it is and recommend a layout.",
  },
  {
    key: "recommendation",
    target: "recommendation",
    title: "Tap the suggestion if it looks right",
    body:
      "We pre-fill the layout, paper, and quantity. If anything looks off, tap Customize to change it.",
  },
  {
    key: "print",
    target: "print-button",
    title: "Tap the green button to print",
    body:
      "When everything looks good, the green button sends the job to the press. You'll see the imposed sheet preview before it actually prints.",
  },
];

function getDoneFlag(): boolean {
  try {
    return localStorage.getItem(TOUR_KEY) === "1";
  } catch {
    return true; // if localStorage is locked down, treat as done — better than a stuck overlay
  }
}

function setDoneFlag() {
  try {
    localStorage.setItem(TOUR_KEY, "1");
  } catch {
    // ignore
  }
}

export function FirstRunTour() {
  const stage = useStore((s) => s.stage);
  const [done, setDone] = useState<boolean>(getDoneFlag());
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // Auto-advance step based on app stage so the tour follows the operator.
  useEffect(() => {
    if (done) return;
    if (stage.kind === "inspected" && stepIndex === 0) setStepIndex(1);
  }, [stage.kind, stepIndex, done]);

  // Track target rect on each step + on resize/scroll.
  useEffect(() => {
    if (done) return;
    const step = STEPS[stepIndex];
    if (!step) return;

    const update = () => {
      const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      if (el) {
        setRect(el.getBoundingClientRect());
      } else {
        setRect(null);
      }
    };

    update();
    // Re-poll briefly while target may still be mounting.
    const id = window.setInterval(update, 250);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [stepIndex, done]);

  if (done) return null;
  const step = STEPS[stepIndex];
  if (!step || !rect) return null;

  const next = () => {
    if (stepIndex >= STEPS.length - 1) {
      setDoneFlag();
      setDone(true);
    } else {
      setStepIndex(stepIndex + 1);
    }
  };

  const dismiss = () => {
    setDoneFlag();
    setDone(true);
  };

  // Pad the spotlight 12px around the target.
  const pad = 12;
  const sx = rect.left - pad;
  const sy = rect.top - pad;
  const sw = rect.width + pad * 2;
  const sh = rect.height + pad * 2;

  // Tooltip placement: prefer below target. If target is in the bottom third,
  // place above instead.
  const placeBelow = sy + sh + 220 < window.innerHeight;
  const tooltipTop = placeBelow ? sy + sh + 12 : Math.max(12, sy - 220);
  const tooltipLeft = Math.min(
    Math.max(12, sx + sw / 2 - 180),
    Math.max(12, window.innerWidth - 372),
  );

  return (
    <>
      {/* Dimmed page with a hole punched through to the target via inset shadow */}
      <div
        style={{
          position: "fixed",
          left: sx,
          top: sy,
          width: sw,
          height: sh,
          borderRadius: 8,
          boxShadow: "0 0 0 9999px rgba(15, 23, 42, 0.6)",
          pointerEvents: "none",
          zIndex: 9000,
          transition: "all 180ms ease",
          outline: "2px solid rgba(56, 189, 248, 0.9)",
          outlineOffset: 2,
        }}
      />
      {/* Tooltip */}
      <div
        role="dialog"
        aria-label={step.title}
        style={{
          position: "fixed",
          top: tooltipTop,
          left: tooltipLeft,
          width: 360,
          background: "#0f172a",
          color: "white",
          borderRadius: 10,
          padding: "16px 18px",
          boxShadow: "0 12px 32px rgba(0,0,0,0.35)",
          zIndex: 9001,
          fontSize: 14,
          lineHeight: 1.5,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <strong style={{ fontSize: 15 }}>{step.title}</strong>
          <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 12 }}>
            Step {stepIndex + 1} of {STEPS.length}
          </span>
        </div>
        <div style={{ color: "rgba(255,255,255,0.85)" }}>{step.body}</div>
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button
            type="button"
            onClick={dismiss}
            style={{
              background: "transparent",
              color: "rgba(255,255,255,0.7)",
              border: "1px solid rgba(255,255,255,0.25)",
              borderRadius: 6,
              padding: "6px 12px",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Skip tour
          </button>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            onClick={next}
            style={{
              background: "#22c55e",
              color: "white",
              border: "none",
              borderRadius: 6,
              padding: "6px 14px",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {stepIndex >= STEPS.length - 1 ? "Got it" : "Next"}
          </button>
        </div>
      </div>
    </>
  );
}
