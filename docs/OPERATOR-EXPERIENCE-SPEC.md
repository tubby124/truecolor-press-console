# Operator Experience Spec — True Color Press Console

The operator is **not a print expert**. They opened Photoshop, designed something, exported a file, and now want it to come out of the C3070 looking right. The UI is the print expert. It catches everything they didn't think about, explains in plain English, fixes what it can, blocks what it can't, and tells them exactly what tray to load.

---

## The Drop Experience (the magic moment)

Operator drags `business_card_v3.psd` onto the dropzone. Within 2 seconds, the UI shows:

```
┌─────────────────────────────────────────────────────────┐
│  business_card_v3.psd                                   │
│  3.5" × 2"  ·  300 dpi  ·  CMYK  ·  fonts embedded      │
│                                                         │
│  We think this is a:  [BUSINESS CARD]   ← auto-detected │
│                                                         │
│  Recommended:                                           │
│    Layout      10-up on letter (best for 100-1000 cards)│
│    Paper       14pt matte cardstock                     │
│    Tray        Tray 2  ✓ (already loaded)               │
│    Bleed       Auto-add 1/8"  ✓                         │
│    Crop marks  Auto-add for cutter  ✓                   │
│    Cost        100 cards = $0.86 (paper) + $0.86 (clicks)│
│                                                         │
│  Preview:  [visual of imposed sheet here]               │
│                                                         │
│         [ Looks good — print 100 ]                      │
│         [ Customize ]                                   │
└─────────────────────────────────────────────────────────┘
```

That's the whole UX. Zero forms. Zero dropdowns. The operator just confirms.

If the file has issues:

```
┌─────────────────────────────────────────────────────────┐
│  business_card_v3.psd                                   │
│                                                         │
│  ⚠ Your photo on the back will look blurry              │
│    Image is 150 dpi at print size. Print needs 300 dpi. │
│    [Replace photo] [Use anyway — I know what I'm doing] │
│                                                         │
│  ⚠ Your phone number is 6pt — too small for print       │
│    Recommend 8pt minimum.                               │
│    [Open in Photoshop] [Use anyway]                     │
│                                                         │
│  ✗ Font "Brush Script MT" isn't embedded                │
│    Press will substitute as Courier.                    │
│    [Fix in Photoshop and re-drop file]                  │
└─────────────────────────────────────────────────────────┘
```

Hard rule: every problem reads like one human telling another. Never `RGB_COLOR_SPACE_DETECTED_NORMALIZE_REQUIRED`.

---

## Auto-Detection Rules (PDF metadata → workflow)

| File dimensions | Pages | Auto-detected as | Default workflow |
|---|---|---|---|
| 3.5×2 in (or close) | 1-2 | Business card | 10-up letter, 14pt CS |
| 4×6 in | 1-2 | Postcard | 4-up letter, 14pt CS |
| 5.5×8.5 in | 1-2 | Half-letter flyer | 2-up letter, 100lb gloss |
| 8.5×11 in | 1 | Flyer / Poster (small) | Plain print, 100lb gloss |
| 8.5×11 in | 2-50 | Multi-page document | Duplex, 24lb bond |
| 8.5×11 in | even, 4+ | Possible booklet | Ask: doc or booklet? |
| 8.5×14 in | any | Legal doc | Plain print legal |
| 11×17 in | 1 | Poster | Plain print 11×17 |
| 11×17 in | even, 4+ | Booklet (folded → 8.5×11) | Saddle-stitch booklet |
| 12×18 in | 1 | Bleed-allowed 11×17 poster | T4, with bleed |
| 13×19 in | 1 | Bleed-allowed 12×18 / SRA3 | T5, with bleed |
| Unknown / odd size | any | Ask operator | Custom |

When ambiguous (e.g. 8.5×11, 8 pages — could be doc or booklet), show a quick chooser: "Print as document or fold into booklet?"

---

## Workflow Tiles (full v1-v4 set)

### v1 — no finishers (passive pass-through, top output bin)
1. **Plain print** — 1-up, any size, duplex toggle, tray select
2. **Business cards** — 10-up letter / 21-up SRA3 / 8-up legal, crop marks + bleed
3. **Postcards** — 4-up letter (4×6) or 2-up letter (5×7)
4. **Bi-fold brochure** — 2-up letter or 11×17, fold guides as ghost lines
5. **Tri-fold brochure** — 3-up letter or legal, fold guides
6. **Half-fold card** — 2-up 11×17 → folded to 8.5×11 greeting card
7. **Multi-page document** — duplex toggle, no finishing
8. **Poster** — single page, large size (11×17, 12×18, 13×19)
9. **Flyer** — single page, gloss recommended

### v2 — staple (after stapler verified)
10. **Stapled doc** — corner staple or dual edge staple
11. **Course/training packet** — multi-section + corner staple

### v3 — booklet maker (after booklet maker verified)
12. **Saddle-stitch booklet** — page reorder + creep + cover wrap
13. **Magazine** — booklet with separate cover stock

### v4 — hole punch (after punch verified)
14. **3-hole binder doc** — punch + duplex
15. **2-hole filing** — top punch

---

## Smart Paper Recommendations (the print expert in software)

### Stock catalog (shop's actual inventory)

We need Hasan to confirm this list. v1 starts with these defaults; the catalog is a JSON file the shop can edit.

| Stock name | Weight | Tray default | Use for |
|---|---|---|---|
| 24lb bond white | 90gsm | T1, T3 | Multi-page docs, letterhead, drafts |
| 70lb opaque text | 105gsm | T1, T3 | Newsletters, flyers (matte) |
| 80lb gloss text | 118gsm | T3 | Brochures, color flyers |
| 100lb gloss text | 148gsm | T3, T4 | Premium brochures, posters |
| 80lb cover matte | 218gsm | T2 | Postcards (matte) |
| 100lb cover gloss | 270gsm | T2, T4 | Premium postcards, business card runs |
| 14pt C2S matte | 350gsm | T2 | Business cards (matte) |
| 16pt C2S gloss | 350gsm | T2 | Business cards (premium gloss) |
| Synthetic / waterproof | varies | T4 | Outdoor posters, signage proofs |

### Recommendation rules
- Business cards → 14pt C2S matte (T2) by default. Offer 16pt gloss as upgrade.
- Postcards → 100lb cover gloss (T2)
- Brochures → 80lb gloss text (T3) for budget, 100lb gloss text (T3) for premium
- Booklets — inner: 80lb text. Cover: 100lb cover.
- Posters → 100lb gloss text (T3 letter, T4 12×18)
- Multi-page docs → 24lb bond (T1)

---

## Tray-Awareness UX

The C3070 has 5 trays. Each can be loaded with different stock. The operator should never have to guess. Two surfaces:

### Always-visible tray status bar
At the top of the UI, show what's currently loaded:

```
T1: 8.5×11 24lb bond   ✓        T4: 12×18 80lb gloss   ✓
T2: 3.5×2 14pt CS      ✓        T5: empty              ⚠
T3: 8.5×11 80lb gloss  low ⚠
```

Source: operator marks what they loaded via a "Set tray" button per tray. The press doesn't tell us what's in each tray (Konica IC doesn't expose loaded paper type via PJL/SNMP). So we keep our own lightweight tray state in `~/.config/press-console/trays.json` and ask the operator to confirm at start of session or when they load.

### Pre-print confirm
Before sending: "Tray 2 should have 14pt cardstock. Did you just load it?"

---

## Preflight (plain English mode)

Convert technical findings to operator language:

| Technical issue | Plain English |
|---|---|
| RGB color space | "Your colors will shift slightly — they were made for screen, we're converting to print colors. Greens/blues most affected." |
| Resolution < 300 DPI | "Your photo will look blurry. Replace with a higher-quality version, or print anyway if it's a draft." |
| No bleed | "Your design goes to the edge but has no bleed. We'll auto-add 1/8" so the cutter doesn't leave white edges." |
| Font not embedded | "Your design uses 'Brush Script' but didn't include the font file. The press will swap it for Courier (looks like a typewriter). Fix in Photoshop and re-export." |
| Hairline < 0.25pt | "You have very thin lines — they may not print or will look broken. Use 0.5pt or thicker." |
| TAC > 300% | "Your dark areas use too much ink (will smudge / not dry). We'll lighten the blacks slightly." |
| Spot color | "You used a Pantone color — the C3070 can't print exact Pantone, only simulate it. Color will be close but not identical." |
| Transparency / live effects | "Some effects will be flattened during printing. Preview to see how it looks." |
| Pure 100K black background | "Solid black backgrounds look more solid with rich black (CMYK 40/30/30/100) instead of just K. Switch?" |
| QR code < 0.75" | "Your QR code is small — may not scan reliably. Recommend 0.75 inch or larger." |

### Hard blocks (won't let you print)
- File corrupt / unreadable
- Fonts not embedded (would substitute → unacceptable)
- Page count vs paper size mismatch can't be resolved
- Trying to use a finisher that's currently disabled

### Warnings (one-click "use anyway")
- Resolution warning
- Color shift warning
- Black-mode optimization

### Auto-fixes (silent, with notice in summary)
- Add bleed if missing and template requires
- Add crop marks
- Convert RGB → CMYK with Konica/Fogra39 ICC
- Flatten transparency
- Embed standard 14 fonts if substitution requested

---

## Imposition Rules

### Business cards 10-up letter
- 5 rows × 2 columns of 3.5×2 cards
- 1/8" bleed all sides → bleed box is 3.75×2.25
- 0.125" gutter between cards (auto-cutter cuts in the gutter)
- Crop marks at outer corners + center registration marks

### Business cards 21-up SRA3
- 7 rows × 3 columns
- Same bleed/gutter

### Postcard 4-up letter (4×6)
- 2 rows × 2 columns
- 1/8" bleed, 1/8" gutter

### Bi-fold letter brochure (2-up letter, lands as 8.5×5.5 each panel)
- Print 11×17 paper folded once
- Pages 1+4 outside, 2+3 inside
- Fold guide at center as ghost line (operator folds manually after print)

### Tri-fold letter brochure (3-up legal, lands as 4.25×11 each panel — wait, that's wrong)
- Tri-fold uses 8.5×11 letter folded into 3 panels of 3.66"
- Print as 1-up letter, two-sided
- Fold guides at panel boundaries (3.66" and 7.33")
- Note: the "outside" panel is slightly narrower for the gate-fold version. Default to standard tri-fold.

### Saddle-stitch booklet (8.5×11 final → 11×17 sheets folded)
- Page count must be ÷4. Auto-pad with blanks if not.
- Page reorder: For an 8-page booklet → sheet 1: pages 8,1 outside / 2,7 inside · sheet 2: pages 6,3 outside / 4,5 inside
- **Creep compensation**: inner pages shift outward slightly because folded pages get pushed out. For thin booklets (<24 pages), creep is < 0.5mm and ignored. For thick, calculate per page-count × paper-thickness.
- Cover wrap option: separate 11×17 cover stock for thicker cover paper.

### Half-fold card (8.5×11 → 5.5×8.5 greeting card)
- 11×17 sheet, fold once
- Outside: pages 1+4 / Inside: pages 2+3
- Common for greeting cards, save-the-dates

---

## Cost & Quote Visibility

Real-time cost panel updates as workflow / quantity / paper changes:

```
This job:
  Sheets through press   10
  Click charge           10 × $0.0573 = $0.57
  Paper cost             10 × $0.05   = $0.50  (14pt C2S)
  Finishing              none in v1
  TOTAL                  $1.07

Per-card cost            $0.011
Suggested sell price     $39 (3.5× markup) for 100 cards = $0.39/card
```

Source: click rate from `truecolor-estimator/data/tables/config.v1.csv`. Paper cost from a per-stock JSON catalog (TBD with Hasan).

---

## Saved Presets / Templates

One-click reprint of named jobs:

- "Hasan business card 14pt matte"
- "True Color tri-fold brochure"
- "Generic 100lb flyer"
- "Standard 8-page booklet"

Operator clicks → file picker opens → drop file → all settings pre-filled.

Stored in `~/.config/press-console/presets.json`.

---

## Job History + Reprint

Every job (dry or live) is logged:

```
~/Library/Application Support/PressConsole/jobs/
  └── 2026-05-07/
      └── 153022-business-cards-acme-co/
          ├── original.pdf
          ├── normalized.pdf
          ├── imposed.pdf
          ├── pjl-bundle.spool
          ├── job.json   (workflow, settings, cost, status)
          └── thumbnail.png
```

UI shows last 50 jobs, search by filename. "Reprint" replays the exact same imposition + settings.

---

## Multi-File Batch

Drop multiple files at once:

- "Print all as separate jobs in the order I dropped" (default)
- "Combine into one document" (PDF concat)
- "Use the same settings for all" (apply preset to batch)

Useful for: 5 different business cards back-to-back, or 12 pages of a magazine submitted as separate exports.

---

## Error Recovery

- **Paper jam mid-print** — When tech is around to detect, show "spool position N of M; resume from page X".
- **Out of toner** — Pause queue, alert.
- **Wrong tray loaded** — Block submission. "Tray 2 has bond, you need cardstock. Load 14pt CS first."
- **Job stalls** — Show last status, allow cancel + resend.

The press exposes job state via PJL `USTATUS JOB=ON`. We subscribe and stream status into the UI.

---

## File Format Coverage

| Input | Pipeline |
|---|---|
| **PDF** | preflight → normalize (CMYK convert, embed fonts) → impose → PJL |
| **PSD** | psd-tools or ImageMagick → flatten layers → composite to PDF → preflight from PDF |
| **EPS** | Ghostscript → PDF → preflight |
| **AI (Adobe Illustrator)** | Read as PDF (AI files are PDF-compatible) → preflight |
| **PNG / JPG** | Auto-place at design size or fit-to-paper → wrap in PDF → preflight |
| **TIFF** | Same as PNG/JPG |
| **DOCX** | Block with friendly message: "We can't print Word docs directly. Save as PDF first (File → Save As → PDF)." |
| **PPT/PPTX** | Same as DOCX |
| **HTML / web URL** | Block: "Use Save as PDF in your browser first." |

For raster inputs (PSD/PNG/JPG), DPI is calculated as: pixel-dimension / desired-print-size. We need to know the intended print size — extract from PSD metadata if present, else ask operator: "How big should this be? Business card / poster / fit to page?"

---

## v2+ Future Items

- ICC profile management (per-stock profiles for color accuracy on different papers)
- Pantone simulation accuracy report (which Pantones are reproducible)
- Variable data printing (mail merge — list of names → 50 personalized business cards)
- Proof printing (low-res preview before big run)
- Color correction tools (live curves on the imposed PDF)
- Multi-language UI (English / Spanish / Filipino if shop staff varies)
- Mobile companion (operator on phone confirms paper loaded → triggers print)
- Inventory tracking (paper stock running low alerts)

---

## Must-Have / Nice / Future Triage (for Hasan to mark)

| # | Feature | Triage |
|---|---|---|
| 1 | Auto-detect job type from PDF dimensions | _ |
| 2 | Tray-state JSON + status bar in UI | _ |
| 3 | Plain-English preflight messages | _ |
| 4 | Smart paper recommendation per workflow | _ |
| 5 | Visual preview of imposed sheet | _ |
| 6 | Live cost panel | _ |
| 7 | Saved presets | _ |
| 8 | Job history + thumbnails + reprint | _ |
| 9 | Multi-file batch | _ |
| 10 | RGB→CMYK with Konica ICC | _ |
| 11 | Bleed auto-add | _ |
| 12 | Crop marks for auto-cutter | _ |
| 13 | Booklet imposition + creep + cover wrap | _ |
| 14 | Stapler workflows (v2) | _ |
| 15 | Punch workflows (v4) | _ |
| 16 | Variable data printing | _ |
| 17 | Mobile companion app | _ |
| 18 | Proof printing | _ |
| 19 | Pantone reproducibility report | _ |
| 20 | Multi-language UI | _ |

Mark each: **MUST** (v1), **NICE** (v2), **FUTURE** (v3+), **SKIP** (don't build).

---

## Open Questions for Hasan

1. **Auto-cutter model?** (Duplo DC-746 reads barcoded crop marks for sub-mm precision; Polar manual reads standard crop marks; affects what we generate.)
2. **Paper stock catalog** — confirm or correct the 9-stock list above. Add per-stock paper cost ($/sheet).
3. **Bleed standard** — 1/8" (industry) or 1/16" (some print shops)?
4. **Default cardstock weight** — 14pt or 16pt for business cards?
5. **Color profile preference** — use Konica's official C3070 ICC, generic Coated FOGRA39, or US SWOP v2?
6. **Job naming convention** — auto-name as `client-date-workflow` or `filename-as-uploaded`?
7. **Who else uses the press besides you?** — affects whether we need user accounts / job ownership in v1.
