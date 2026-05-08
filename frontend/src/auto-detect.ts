// Plain-English mapping of preflight finding codes → operator-friendly text.
// Backend now produces friendly messages directly (phase 4.X.1), so this is
// mostly a pass-through. The WHAT_TO_DO map below provides the expand-to-fix
// instructions surfaced by PreflightFindings.

import type { Finding } from "./types";

export function plainEnglish(f: Finding): string {
  return f.message;
}

export interface WhatToDo {
  /** Steps the operator can take. Rendered as a numbered list. */
  steps: string[];
  /** Whether the system can fix this automatically (drives the inline Fix button). */
  fixable?: boolean;
}

const WHAT_TO_DO: Record<string, WhatToDo> = {
  "missing-file": {
    steps: [
      "Drop the file into this page again.",
      "If the same error repeats, open the file in your design tool and save it as a fresh PDF, then drop that.",
    ],
  },
  "corrupt-pdf": {
    steps: [
      "Open the original design (Illustrator / Photoshop / InDesign / Word).",
      "Re-export it as a new PDF — use 'Save As' or 'Export', not 'Save'.",
      "Drop the freshly-exported PDF into this page.",
    ],
  },
  "fonts-not-embedded": {
    steps: [
      "Open the file in the design tool that made it.",
      "Re-export as PDF with the 'Embed all fonts' (or 'Subset fonts') option turned on.",
      "Drop the new PDF into this page.",
    ],
  },
  "no-trimbox": {
    steps: [
      "If you don't need bleed (no color or photo touching the edge), you can print this as-is.",
      "If you do need bleed: re-export the PDF with crop marks / trim box turned on. Most design tools call this 'Marks and Bleeds'.",
    ],
  },
  "insufficient-bleed": {
    steps: [
      "Tap the 'Fix it for me' button to extend the background out to the trim line — works perfectly when your design has a full-bleed background.",
      "If the design ends right at the cut line, instead re-export from your design tool with at least 1/8\" bleed all around.",
    ],
    fixable: true,
  },
  "low-dpi-image": {
    steps: [
      "Replace the photo on the flagged page with a higher-resolution version (300 dpi at the printed size).",
      "If you can't get a sharper version, this is fine for a draft — just expect soft edges in print.",
    ],
  },
  "mixed-page-sizes": {
    steps: [
      "Open the PDF in Preview or your design tool and check page sizes.",
      "Save a separate PDF for each page size, drop them as a batch, and we'll print each one with the right paper.",
    ],
  },
  "layout-fit": {
    steps: [
      "Pick a different layout from the 'Change layout' chip — make sure the parent sheet is big enough.",
      "If you really need this combination, contact Hasan.",
    ],
  },
};

export function whatToDoFor(code: string): WhatToDo | null {
  return WHAT_TO_DO[code] ?? null;
}

export function severityIcon(s: Finding["severity"]): string {
  if (s === "block") return "✕";
  if (s === "warn") return "⚠";
  return "ⓘ";
}

export function severityColor(s: Finding["severity"]): string {
  if (s === "block") return "var(--danger)";
  if (s === "warn") return "var(--warn)";
  return "var(--muted)";
}

export function dimensionsLabel(width_in: number, height_in: number): string {
  return `${trim(width_in)}″ × ${trim(height_in)}″`;
}

function trim(n: number): string {
  return Number.isInteger(n) ? n.toFixed(1) : n.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatMoney(n: number): string {
  return `$${n.toFixed(2)}`;
}

export function formatPerUnit(total: number, qty: number): string {
  if (!qty) return "—";
  return `$${(total / qty).toFixed(3)} each`;
}
