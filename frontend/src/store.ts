// Zustand store — global UI state. No business logic here; just the shared
// pieces multiple components read/write (current job, current toast, history
// pointer, etc.).

import { create } from "zustand";
import type { BatchItem, InspectResult, Job, TraysResponse } from "./types";

export type Toast = { id: number; level: "info" | "warn" | "error" | "success"; text: string };

export type Stage =
  | { kind: "idle" }
  | { kind: "inspecting"; file: File }
  | { kind: "inspected"; file: File; result: InspectResult; quantity: number; sides: 1 | 2; stockCode: string; presetKey: string }
  | { kind: "submitting"; file: File }
  | { kind: "done"; job: Job }
  | { kind: "batch_pending"; files: File[]; quantity: number; sides: 1 | 2; stockCode: string; presetKey: string }
  | { kind: "batch_submitting"; files: File[] }
  | { kind: "batch_done"; results: BatchItem[] };

interface Store {
  trays: TraysResponse | null;
  setTrays: (t: TraysResponse) => void;

  stage: Stage;
  setStage: (s: Stage) => void;
  reset: () => void;

  toasts: Toast[];
  pushToast: (level: Toast["level"], text: string) => void;
  dismissToast: (id: number) => void;

  showHistory: boolean;
  setShowHistory: (v: boolean) => void;

  // "Last job" pill — appears in the topbar after a successful print and
  // sticks around (across stage transitions back to idle) until the operator
  // dismisses it. Cleared automatically when a NEW job hits stage=done so the
  // pill always reflects the most recent print.
  //
  // lastJob: the Job rendered in the pill. Read from stage when stage.kind ==
  //   "done" and persisted into the store as the operator moves away.
  // lastJobAck: true when the operator has clicked the ✕ on the pill.
  //   Resets to false whenever lastJob changes.
  lastJob: import("./types").Job | null;
  lastJobAck: boolean;
  setLastJob: (job: import("./types").Job | null) => void;
  ackLastJob: () => void;
}

let toastCounter = 0;

export const useStore = create<Store>((set) => ({
  trays: null,
  setTrays: (t) => set({ trays: t }),

  stage: { kind: "idle" },
  setStage: (s) => set({ stage: s }),
  reset: () => set({ stage: { kind: "idle" } }),

  toasts: [],
  pushToast: (level, text) =>
    set((state) => {
      const id = ++toastCounter;
      // Errors persist until the operator dismisses them — the previous 4.5s
      // auto-dismiss meant real failures (e.g. preset mismatches, preflight
      // blocks) disappeared before anyone read them. Warn gets a longer
      // window than success/info for the same reason.
      const ttl =
        level === "error" ? 0
        : level === "warn" ? 8000
        : level === "success" ? 4500
        : 3000;
      if (ttl > 0) {
        setTimeout(() => {
          useStore.getState().dismissToast(id);
        }, ttl);
      }
      return { toasts: [...state.toasts, { id, level, text }] };
    }),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  showHistory: false,
  setShowHistory: (v) => set({ showHistory: v }),

  lastJob: null,
  lastJobAck: false,
  setLastJob: (job) =>
    set((state) => {
      // Same job_id → keep ack state (operator may have already dismissed).
      // Different job → clear ack so the pill shows again.
      if (job && state.lastJob && state.lastJob.job_id === job.job_id) {
        return { lastJob: job };
      }
      return { lastJob: job, lastJobAck: false };
    }),
  ackLastJob: () => set({ lastJobAck: true }),
}));
