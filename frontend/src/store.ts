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
      setTimeout(() => {
        useStore.getState().dismissToast(id);
      }, 4500);
      return { toasts: [...state.toasts, { id, level, text }] };
    }),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  showHistory: false,
  setShowHistory: (v) => set({ showHistory: v }),
}));
