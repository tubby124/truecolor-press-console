// Workflow tile catalog — what shows on the home screen launcher.
// Keep enabled set in sync with backend impose.PRESETS. Disabled tiles are
// scaffolded for hardware gates (v2/v3/v4 finishers) and click-to-explain.

export type Phase = "v1" | "v2" | "v3" | "v4";

// Per-tile finisher behavior + tested status — surfaces in the UI so
// operators know what each tile actually produces on this specific press.
// Confirmed against TC1 + AccurioPress C3070 + LS-506 + SD-510 on 2026-05-11.
export type FinisherStatus = "confirmed" | "manual-finish" | "hardware-blocked" | "untested";

export interface FinisherInfo {
  staple?: string;       // e.g. "1 staple, upper-left corner"
  punch?: string;        // e.g. "3 holes, left edge"
  fold?: string;         // e.g. "Half-fold, 5.5×8.5 finished"
  output?: string;       // e.g. "Stapler main tray"
}

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
  // New in v0.3.5: operator-facing tip + production status
  tip?: string;            // 1-2 sentence operator hint shown on the tile
  finisher?: FinisherInfo; // surfaces in tile + on inspect screen
  status?: FinisherStatus; // confirmed | manual-finish | hardware-blocked | untested
  statusNote?: string;     // why the status — e.g. "BM-660 doesn't fold letter on this press"
}

export const TILES: WorkflowTile[] = [
  // ─── Plain print (always works) ─────────────────────────────────────────
  {
    key: "business_card",
    label: "Business Cards",
    hint: "Standard business cards — up to 21 cards from one sheet",
    presetKey: "bc_21up_12x18",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "🪪",
    tip: "21-up on 12×18 cardstock from Tray 4. Cut down at the Graphic Wizard.",
    finisher: { output: "Top tray" },
    status: "confirmed",
  },
  {
    key: "postcard_4x6",
    label: "Postcards 4×6",
    hint: "4×6 postcards — 4 per sheet, cut apart after printing",
    presetKey: "pc_4x6_4up_18x12",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "✉️",
    tip: "4-up on 12×18 cardstock from Tray 4. Cut down at the Graphic Wizard.",
    finisher: { output: "Top tray" },
    status: "confirmed",
  },
  {
    key: "postcard_5x7",
    label: "Postcards 5×7",
    hint: "5×7 postcards — 4 per sheet, cut apart after printing",
    presetKey: "pc_5x7_4up_18x12",
    defaultStock: "14pt-cs-gloss",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📮",
    tip: "4-up on 12×18 cardstock from Tray 4. Cut down at the Graphic Wizard.",
    finisher: { output: "Top tray" },
    status: "confirmed",
  },
  {
    key: "flyer",
    label: "Letter Flyer",
    hint: "Single-page letter flyer on glossy paper",
    presetKey: "flyer_1up_letter",
    defaultStock: "100lb-gloss-text",
    defaultQty: 1,
    defaultSides: 1,
    phase: "v1",
    emoji: "📄",
    tip: "Letter sheet, 1-sided. Pulls from a tray with 100lb gloss text.",
    finisher: { output: "Top tray" },
    status: "confirmed",
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
    tip: "Letter sheet, 1-sided. Premium glossy text stock.",
    finisher: { output: "Top tray" },
    status: "confirmed",
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
    tip: "11×17 sheet, 1-sided. Premium glossy text stock.",
    finisher: { output: "Top tray" },
    status: "confirmed",
  },

  // ─── Finisher-active (LS-506 stapler + punch confirmed 2026-05-11) ──────
  {
    key: "stapled_doc",
    label: "Stapled Document",
    hint: "Multi-page document — auto-stapled in the corner",
    presetKey: "stapled_plain_letter",
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📎",
    tip: "Auto-staples a single corner staple in the upper-left. Pulls letter from Tray 1 (plain bond). To change staple position later, ask devs.",
    finisher: {
      staple: "1 staple, upper-left corner",
      output: "Stapler main tray",
    },
    status: "confirmed",
  },
  {
    key: "punched",
    label: "3-Hole Binder Doc",
    hint: "Multi-page document — auto-punched with 3 holes for a binder",
    presetKey: "punched_plain_letter",
    defaultStock: "24lb-bond",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📑",
    tip: "Auto-punches 3 holes along the left edge. Ready to drop into a 3-ring binder.",
    finisher: {
      punch: "3 holes, left edge",
      output: "Stapler main tray",
    },
    status: "confirmed",
  },

  // ─── Booklets ───────────────────────────────────────────────────────────
  {
    key: "booklet_8.5x11_12x18",
    label: "8.5×11 Booklet (12×18)",
    hint: "Saddle-stitch booklet on 12×18 — fold once, trim to 8.5×11. Bleed required.",
    presetKey: "booklet_8.5x11_12x18",
    defaultStock: "100lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📖",
    tip: "12×18 sheets from Tray 4, duplex. Press should fold + saddle-stitch via SD-510. Trim 3 edges at Graphic Wizard if bleed.",
    finisher: {
      fold: "Half-fold + saddle stitch at spine",
      output: "Saddle stitcher tray",
    },
    status: "untested",
    statusNote: "Needs 12×18 path test with proper bleed source PDF. Letter saddle is hardware-blocked on this press.",
  },
  {
    key: "booklet_5.5x8.5_letter",
    label: "5.5×8.5 Booklet (letter — MANUAL FINISH)",
    hint: "Letter sheets imposed for a 5.5×8.5 booklet. You fold + staple by hand.",
    presetKey: "booklet_5.5x8.5_letter",
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📖",
    tip: "Prints flat letter sheets. The SD-510 saddle won't fold letter (hardware limit). Fold in half + hand-stitch with a long-arm stapler.",
    finisher: { output: "Top tray (then manual fold + stitch)" },
    status: "manual-finish",
    statusNote: "BM-660/SD-510 won't fold sheets below 11×17. Confirmed 2026-05-11.",
  },
  {
    key: "booklet_8.5x11_11x17",
    label: "8.5×11 Booklet (11×17)",
    hint: "Saddle-stitch booklet on 11×17 — fold once into 8.5×11. No trim.",
    presetKey: "booklet_8.5x11_11x17",
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📖",
    tip: "11×17 sheets, duplex. If 11×17 is loaded, press should fold + saddle-stitch. Untested.",
    finisher: {
      fold: "Half-fold + saddle stitch at spine",
      output: "Saddle stitcher tray",
    },
    status: "untested",
    statusNote: "Need 11×17 loaded to test. Hardware should support saddle on 11×17.",
  },

  // ─── Brochures (FD-503 or SD-510 fold path — see status notes) ──────────
  {
    key: "trifold",
    label: "Tri-fold Brochure",
    hint: "Letter sheet folded into thirds (Z or C fold)",
    presetKey: "trifold_1up_letter",
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📂",
    tip: "Press won't auto-fold letter on this machine. Prints flat — fold by hand or run through the Graphic Wizard's fold guide.",
    finisher: { output: "Top tray (then manual fold)" },
    status: "manual-finish",
    statusNote: "Letter folding doesn't engage on this press. Confirmed 2026-05-11.",
  },
  {
    key: "bifold",
    label: "Bi-fold Brochure",
    hint: "11×17 sheet folded once → 4-page letter-size brochure",
    presetKey: "bifold_1up_11x17",
    defaultStock: "80lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "📓",
    tip: "11×17 sheet duplex. If 11×17 is loaded, the SD-510 should half-fold automatically. Untested on this press.",
    finisher: {
      fold: "Half-fold (11×17 → 8.5×11 finished)",
      output: "Saddle stitcher tray",
    },
    status: "untested",
    statusNote: "Untested. Hardware supports 11×17 fold; need to load 11×17 in a tray.",
  },
  {
    key: "halffold",
    label: "Half-fold Card",
    hint: "Greeting-card style — sheet folded once down the middle",
    presetKey: "halffold_1up_letter",
    defaultStock: "100lb-gloss-text",
    defaultQty: 1,
    defaultSides: 2,
    phase: "v1",
    emoji: "💌",
    tip: "Press won't half-fold letter (same hardware limit as saddle booklet). Prints flat — fold by hand or at the Graphic Wizard.",
    finisher: { output: "Top tray (then manual fold)" },
    status: "manual-finish",
    statusNote: "Letter folding doesn't engage on this press. Confirmed 2026-05-11.",
  },
];

export function tileByKey(key: string): WorkflowTile | undefined {
  return TILES.find((t) => t.key === key);
}
