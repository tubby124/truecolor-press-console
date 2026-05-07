// Plain-English mapping of preflight finding codes → operator-friendly text.
// Backend returns generic codes; we translate at the UI edge.

import type { Finding } from "./types";

const MAP: Record<string, (f: Finding) => string> = {
  "missing-file": () => "We couldn't read that file. Try saving it as PDF and dropping again.",
  "corrupt-pdf": (f) => `That PDF looks corrupted. ${f.message.split(":").pop()?.trim() ?? ""}`,
  "fonts-not-embedded": (f) =>
    `Your design uses a font that isn't embedded in the PDF. The press would swap it for Courier (looks like a typewriter). Re-export with "Embed all fonts" turned on. ${f.message.replace(/^Fonts not embedded.*?:/, "Missing:")}`,
  "no-trimbox": () =>
    "We can't auto-verify your bleed because the file has no trim marks. We'll add bleed for you, but check the preview before printing.",
  "insufficient-bleed": (f) =>
    `Your design goes near the edge but the bleed is too small (${f.message.match(/[\d.]+/)?.[0] ?? "?"}"). After cutting, you may see white slivers. Re-export with at least 1/8" bleed, or print and accept some edge clipping.`,
  "layout-fit": () =>
    "The chosen layout doesn't fit on the parent sheet. Pick a different paper size or workflow.",
};

export function plainEnglish(f: Finding): string {
  const fn = MAP[f.code];
  return fn ? fn(f) : f.message;
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
