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
    hint: "21-up on 12×18 cardstock with crop marks",
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
    hint: "4-up on 12×18 cardstock with crop marks",
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
    hint: "4-up on 12×18 cardstock",
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
    hint: "1-up letter, 100lb gloss",
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
    hint: "Letter landscape, fold guides at 1/3 + 2/3",
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
    hint: "11×17 sheet folded once → 8.5×11 4-page",
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
    hint: "11×17 → 5.5×8.5 greeting card",
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
    hint: "1-up letter, premium gloss",
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
    hint: "1-up tabloid, premium gloss",
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
    hint: "Multi-page + corner staple",
    presetKey: null,
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v2",
    hardwareGate:
      "Stapler unit needs to be verified post-brownout by the Konica technician. Until then this workflow is disabled. See docs/HARDWARE-GATES.md gate 5.",
    emoji: "📎",
  },

  // v3 — booklet maker (hardware-gated)
  {
    key: "booklet",
    label: "Saddle-Stitch Booklet",
    hint: "11×17 sheets folded + stitched at spine",
    presetKey: null,
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v3",
    hardwareGate:
      "Booklet maker unit needs verification post-brownout. Imposition logic (page reorder + creep compensation) is also still on the v3 backlog.",
    emoji: "📖",
  },

  // v4 — hole punch (hardware-gated)
  {
    key: "punched",
    label: "3-Hole Binder Doc",
    hint: "Multi-page duplex + 3-hole punch",
    presetKey: null,
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v4",
    hardwareGate:
      "Hole-punch unit (PK-522) needs verification post-brownout. Workflow tile reserved for v4.",
    emoji: "📑",
  },
];

export function tileByKey(key: string): WorkflowTile | undefined {
  return TILES.find((t) => t.key === key);
}
