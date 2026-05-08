// Plain-English explanations of print-shop jargon. Used by HelpTip popovers.
// Keys are stable so HelpTip refs don't break on copy edits.

export interface GlossaryEntry {
  term: string;
  body: string;
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  bleed: {
    term: "Bleed",
    body:
      "The bit of background art that extends past the cut line so there's no white sliver if the cutter is slightly off. " +
      "We need at least 1/8\" of bleed for clean edges.",
  },
  imposition: {
    term: "Imposition",
    body:
      "How we lay your design out on the big parent sheet. For example, 21 business cards on one 12×18 sheet — " +
      "the cutter slices them apart afterward.",
  },
  dpi: {
    term: "DPI",
    body:
      "Dots per inch — how sharp a photo looks when printed. 300 dpi is the print standard. Below 150 dpi looks visibly blurry.",
  },
  tray: {
    term: "Tray",
    body:
      "One of the press's paper drawers. Each tray holds a different paper. The system needs to know which tray has the right paper " +
      "before it'll print a job — that's why you'll sometimes see a 'put X in tray Y' prompt.",
  },
  stock: {
    term: "Paper / Stock",
    body:
      "What kind of paper the job runs on — thick glossy cardstock for business cards, plain copy paper for documents, glossy text " +
      "weight for flyers, etc. We pick a default based on the workflow; you can change it with the 'Change paper' chip.",
  },
  preset: {
    term: "Layout / Preset",
    body:
      "A pre-built combination of parent sheet size + how many pieces fit on it. 'Business cards — 21 per sheet' is a layout. " +
      "Pick a different one with the 'Change layout' chip if the recommendation isn't right.",
  },
  cropMarks: {
    term: "Crop marks",
    body:
      "Tiny corner lines printed at the trim edge so the cutter (or you with a guillotine) knows exactly where to cut. " +
      "We add them automatically for any job that needs cutting.",
  },
  duplex: {
    term: "Duplex / 2-sided",
    body:
      "Printed on both the front and the back of the sheet. The press flips the paper automatically. " +
      "Your file needs to have both sides as separate pages (front = page 1, back = page 2).",
  },
};

export function lookup(key: keyof typeof GLOSSARY | string): GlossaryEntry | null {
  return GLOSSARY[key] ?? null;
}
