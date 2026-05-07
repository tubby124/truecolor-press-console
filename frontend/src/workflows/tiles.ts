// Workflow tile catalog — what shows on the home screen launcher.
// Keep enabled set in sync with backend impose.PRESETS. Disabled tiles are
// scaffolded for hardware gates (v2/v3/v4 finishers) and click-to-explain.

export type Phase = "v1" | "v2" | "v3" | "v4";

export interface WorkflowTile {
  key: string;
  label: string;
  hint: string;
  presetKey: string | null; // null for disabled scaffolding tiles
  defaultStock: string;
  defaultQty: number;
  defaultSides: 1 | 2;
  phase: Phase;
  hardwareGate?: string; // shown when tile is disabled
  emoji: string;
}

export const TILES: WorkflowTile[] = [
  // v1 — passive pass-through, no finishers
  {
    key: "business_card",
    label: "Business Cards",
    hint: "Standard business cards — up to 21 cards from one sheet",
    presetKey: "bc_21up_12x18",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 100,
    defaultSides: 2,
    phase: "v1",
    emoji: "🪪",
  },
  {
    key: "postcard_4x6",
    label: "Postcards 4×6",
    hint: "4×6 postcards — 4 per sheet, cut apart after printing",
    presetKey: "pc_4x6_4up_18x12",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 50,
    defaultSides: 2,
    phase: "v1",
    emoji: "✉️",
  },
  {
    key: "postcard_5x7",
    label: "Postcards 5×7",
    hint: "5×7 postcards — 4 per sheet, cut apart after printing",
    presetKey: "pc_5x7_4up_18x12",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 50,
    defaultSides: 2,
    phase: "v1",
    emoji: "📮",
  },
  {
    key: "flyer",
    label: "Letter Flyer",
    hint: "Single-page letter flyer on glossy paper",
    presetKey: "flyer_1up_letter",
    defaultStock: "100lb-gloss-text",
    defaultQty: 50,
    defaultSides: 1,
    phase: "v1",
    emoji: "📄",
  },
  {
    key: "trifold",
    label: "Tri-fold Brochure",
    hint: "Letter sheet folded into thirds — fold lines included",
    presetKey: "trifold_1up_letter",
    defaultStock: "80lb-gloss-text",
    defaultQty: 100,
    defaultSides: 2,
    phase: "v1",
    emoji: "📂",
  },
  {
    key: "bifold",
    label: "Bi-fold Brochure",
    hint: "11×17 sheet folded once → 4-page letter-size brochure",
    presetKey: "bifold_1up_11x17",
    defaultStock: "80lb-gloss-text",
    defaultQty: 100,
    defaultSides: 2,
    phase: "v1",
    emoji: "📓",
  },
  {
    key: "halffold",
    label: "Half-fold Card",
    hint: "Greeting-card style — 11×17 sheet folded once",
    presetKey: "halffold_1up_letter",
    defaultStock: "100lb-gloss-text",
    defaultQty: 25,
    defaultSides: 2,
    phase: "v1",
    emoji: "💌",
  },
  {
    key: "poster_letter",
    label: "Letter Poster",
    hint: "Letter-size poster on premium glossy paper",
    presetKey: "poster_1up_letter",
    defaultStock: "100lb-gloss-text",
    defaultQty: 1,
    defaultSides: 1,
    phase: "v1",
    emoji: "🖼️",
  },
  {
    key: "poster_11x17",
    label: "11×17 Poster",
    hint: "11×17 poster on premium glossy paper",
    presetKey: "poster_1up_11x17",
    defaultStock: "100lb-gloss-text",
    defaultQty: 1,
    defaultSides: 1,
    phase: "v1",
    emoji: "🖼️",
  },

  // v2 — stapler (hardware-gated)
  {
    key: "stapled_doc",
    label: "Stapled Document",
    hint: "Multi-page document with a corner staple",
    presetKey: null,
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v2",
    hardwareGate:
      "The stapler still needs to be checked over by the Konica technician after the power surge. We've turned this off until that's done.",
    emoji: "📎",
  },

  // v3 — booklet maker (hardware-gated)
  {
    key: "booklet",
    label: "Saddle-Stitch Booklet",
    hint: "Booklet stapled at the spine — 11×17 sheets folded in half",
    presetKey: null,
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v3",
    hardwareGate:
      "The booklet maker still needs to be checked over by the technician, and the page-ordering logic is still being built. Disabled until both are ready.",
    emoji: "📖",
  },

  // v4 — hole punch (hardware-gated)
  {
    key: "punched",
    label: "3-Hole Binder Doc",
    hint: "Multi-page document with 3 binder holes punched on the side",
    presetKey: null,
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v4",
    hardwareGate:
      "The hole-punch attachment still needs to be checked over by the technician. Disabled until that's done.",
    emoji: "📑",
  },
];

export function tileByKey(key: string): WorkflowTile | undefined {
  return TILES.find((t) => t.key === key);
}
