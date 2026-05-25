"""Imposition engine — places artwork on parent sheets with bleed + crop marks.

Targets Graphic Wizard 4908 cutter (CCD camera registration). Industry-standard
output: 1/8" bleed all sides, 0.125" gutter between pieces, crop marks at
outer sheet corners offset 0.25" from trim, registration marks at the four
edge midpoints.

All units internally are PDF points (1/72 inch). Convenience constants below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pikepdf
from pikepdf import Name, Page, Rectangle

PT_PER_INCH = 72.0


def inches(x: float) -> float:
    return x * PT_PER_INCH


@dataclass(frozen=True)
class SheetSpec:
    name: str
    width_in: float
    height_in: float

    @property
    def width_pt(self) -> float:
        return inches(self.width_in)

    @property
    def height_pt(self) -> float:
        return inches(self.height_in)


SHEETS = {
    "letter": SheetSpec("LETTER", 8.5, 11.0),
    "letter-l": SheetSpec("LETTER", 11.0, 8.5),
    "legal": SheetSpec("LEGAL", 8.5, 14.0),
    "ledger": SheetSpec("LEDGER", 11.0, 17.0),
    "ledger-l": SheetSpec("LEDGER", 17.0, 11.0),
    "12x18": SheetSpec("P12X18", 12.0, 18.0),
    "18x12": SheetSpec("P12X18", 18.0, 12.0),
    "13x19": SheetSpec("P13X19", 13.0, 19.0),
    "19x13": SheetSpec("P13X19", 19.0, 13.0),
    "sra3": SheetSpec("SRA3", 12.6, 17.7),
    "sra3-l": SheetSpec("SRA3", 17.7, 12.6),
}


@dataclass(frozen=True)
class PieceSpec:
    name: str
    width_in: float
    height_in: float
    bleed_in: float = 0.125

    @property
    def trim_w(self) -> float:
        return inches(self.width_in)

    @property
    def trim_h(self) -> float:
        return inches(self.height_in)

    @property
    def bleed_w(self) -> float:
        return self.trim_w + 2 * inches(self.bleed_in)

    @property
    def bleed_h(self) -> float:
        return self.trim_h + 2 * inches(self.bleed_in)


PIECES = {
    "business_card": PieceSpec("Business Card", 3.5, 2.0),
    "postcard_3x4": PieceSpec("Postcard 3×4", 4.0, 3.0),
    "postcard_4x6": PieceSpec("Postcard 4×6", 6.0, 4.0),
    "postcard_5x7": PieceSpec("Postcard 5×7", 7.0, 5.0),
    "flyer_half": PieceSpec("Half-Letter Flyer", 5.5, 8.5),
    "flyer_half_l": PieceSpec("Half-Letter Flyer L", 8.5, 5.5, bleed_in=0.0),
    "flyer_letter": PieceSpec("Letter Flyer", 8.5, 11.0, bleed_in=0.0),
    "trifold_letter": PieceSpec("Tri-fold Letter", 11.0, 8.5, bleed_in=0.0),
    "bifold_11x17": PieceSpec("Bi-fold 11×17", 17.0, 11.0, bleed_in=0.0),
    "halffold_letter": PieceSpec("Half-fold Letter Card", 11.0, 8.5, bleed_in=0.0),
    "poster_letter": PieceSpec("Letter Poster", 8.5, 11.0, bleed_in=0.0),
    "poster_11x17": PieceSpec("11×17 Poster", 17.0, 11.0, bleed_in=0.0),
}


# Fold layouts: number of fold-guide vertical lines + fractional positions
# along the wide axis. Used by impose_grid via add_fold_guides.
FOLD_GUIDES: dict[str, list[float]] = {
    "trifold_letter": [1 / 3, 2 / 3],
    "bifold_11x17": [0.5],
    "halffold_letter": [0.5],
}


@dataclass(frozen=True)
class GridLayout:
    sheet: SheetSpec
    piece: PieceSpec
    cols: int
    rows: int
    gutter_in: float = 0.125
    margin_in: float = 0.5

    @property
    def total_pieces(self) -> int:
        return self.cols * self.rows

    def fits(self) -> bool:
        gutter = inches(self.gutter_in)
        total_w = self.cols * self.piece.bleed_w + (self.cols - 1) * gutter
        total_h = self.rows * self.piece.bleed_h + (self.rows - 1) * gutter
        margin = inches(self.margin_in)
        return total_w <= self.sheet.width_pt - 2 * margin and total_h <= self.sheet.height_pt - 2 * margin


PRESETS: dict[str, GridLayout] = {
    "bc_21up_12x18": GridLayout(
        SHEETS["12x18"], PIECES["business_card"],
        cols=3, rows=7, gutter_in=0.0, margin_in=0.375,
    ),
    "bc_8up_letter": GridLayout(
        SHEETS["letter"], PIECES["business_card"],
        cols=2, rows=4, gutter_in=0.0, margin_in=0.375,
    ),
    "bc_10up_legal": GridLayout(
        SHEETS["legal"], PIECES["business_card"],
        cols=2, rows=5, gutter_in=0.0, margin_in=0.5,
    ),
    "bc_21up_sra3": GridLayout(
        SHEETS["sra3"], PIECES["business_card"],
        cols=3, rows=7, gutter_in=0.0, margin_in=0.375,
    ),
    "flyer_half_2up_letter": GridLayout(
        SHEETS["letter"], PIECES["flyer_half_l"],
        cols=1, rows=2, gutter_in=0.0, margin_in=0.0,
    ),
    "pc_3x4_12up_18x12": GridLayout(
        SHEETS["18x12"], PIECES["postcard_3x4"],
        cols=4, rows=3, gutter_in=0.0, margin_in=0.375,
    ),
    "pc_4x6_4up_18x12": GridLayout(
        SHEETS["18x12"], PIECES["postcard_4x6"],
        cols=2, rows=2, gutter_in=0.0, margin_in=0.375,
    ),
    "pc_5x7_4up_18x12": GridLayout(
        SHEETS["18x12"], PIECES["postcard_5x7"],
        cols=2, rows=2, gutter_in=0.0, margin_in=0.375,
    ),
    "flyer_1up_letter": GridLayout(
        SHEETS["letter"], PIECES["flyer_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "trifold_1up_letter": GridLayout(
        SHEETS["letter-l"], PIECES["trifold_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "bifold_1up_11x17": GridLayout(
        SHEETS["ledger-l"], PIECES["bifold_11x17"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "halffold_1up_letter": GridLayout(
        SHEETS["letter-l"], PIECES["halffold_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "poster_1up_letter": GridLayout(
        SHEETS["letter"], PIECES["poster_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "poster_1up_11x17": GridLayout(
        SHEETS["ledger-l"], PIECES["poster_11x17"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    # Passthrough presets for finisher-only workflows (stapler, hole-punch).
    # 1-up letter, no scaling, no crop/reg marks — source PDF prints as-is
    # to Letter sheets; the Windows print spooler attaches finishing options
    # via a queue-specific Konica driver preset.
    "stapled_plain_letter": GridLayout(
        SHEETS["letter"], PIECES["poster_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
    "punched_plain_letter": GridLayout(
        SHEETS["letter"], PIECES["poster_letter"],
        cols=1, rows=1, gutter_in=0.0, margin_in=0.0,
    ),
}


# Map preset_key → fold-guide piece key (so the imposition step knows whether
# to draw fold guides instead of crop marks).
FOLD_PRESET_MAP: dict[str, str] = {
    "trifold_1up_letter": "trifold_letter",
    "bifold_1up_11x17": "bifold_11x17",
    "halffold_1up_letter": "halffold_letter",
}


# ───────────────────── Saddle-stitch booklet imposition ─────────────────────
#
# A saddle-stitch booklet is a multi-sheet job: each printed sheet, folded
# once at the spine, contributes 4 booklet pages (2 front + 2 back). Page
# order is "printer's spread" — NOT sequential. For a booklet of N pages
# (padded to next multiple of 4):
#
#   sheet i (0-indexed) front:  page (N - 2i)   |   page (1 + 2i)
#   sheet i back:               page (2 + 2i)   |   page (N - 1 - 2i)
#
# When the stack is folded and stitched, pages emerge in 1, 2, 3 ... order.
#
# The Konica's booklet-maker finisher stays disabled per CLAUDE.md hard rule
# #1 (no finisher activation post-brownout). Fold + stitch happens off-press:
# the operator folds at the Graphic Wizard and staples manually.


@dataclass(frozen=True)
class BookletPreset:
    """Saddle-stitch booklet layout — 2 pages per side of a parent sheet, fold once.

    Unlike GridLayout (which repeats one piece N times), a BookletPreset
    represents a multi-sheet signature where each parent sheet holds 4 booklet
    pages in printer's-spread order. Cost = ceil(page_count / 4) sheets per
    booklet copy.
    """

    sheet: SheetSpec
    page_w_in: float    # finished page trim width
    page_h_in: float    # finished page trim height
    bleed_in: float     # bleed beyond trim — 0 if no trim required, 0.125 if trimming 3 edges
    trim_after: bool    # operator trims 3 edges down to finish size after fold
    label: str          # operator-facing label

    def fits(self) -> bool:
        spread_w = 2 * inches(self.page_w_in) + 2 * inches(self.bleed_in)
        spread_h = inches(self.page_h_in) + 2 * inches(self.bleed_in)
        return spread_w <= self.sheet.width_pt and spread_h <= self.sheet.height_pt


BOOKLET_PRESETS: dict[str, BookletPreset] = {
    # 5.5×8.5 booklet from letter — fold once, no trim. Bleed not possible
    # (page edges = sheet edges). Designer should keep art away from outer
    # edges since there's no margin to trim into.
    "booklet_5.5x8.5_letter": BookletPreset(
        sheet=SHEETS["letter-l"], page_w_in=5.5, page_h_in=8.5,
        bleed_in=0.0, trim_after=False,
        label="Booklet 5.5×8.5 — letter sheet, fold only (no bleed)",
    ),
    # 8.5×11 booklet from 11×17 — fold once, no trim. Bleed not possible.
    "booklet_8.5x11_11x17": BookletPreset(
        sheet=SHEETS["ledger-l"], page_w_in=8.5, page_h_in=11.0,
        bleed_in=0.0, trim_after=False,
        label="Booklet 8.5×11 — 11×17 sheet, fold only (no bleed)",
    ),
    # 8.5×11 booklet from 12×18 — Hasan's primary workflow. Fold once → 9×12
    # spread, then trim head/foot/face on Graphic Wizard down to 8.5×11.
    # Bleed REQUIRED (0.125" all sides).
    "booklet_8.5x11_12x18": BookletPreset(
        sheet=SHEETS["18x12"], page_w_in=8.5, page_h_in=11.0,
        bleed_in=0.125, trim_after=True,
        label="Booklet 8.5×11 — 12×18 sheet, fold + trim 3 edges (bleed required)",
    ),
}


def is_booklet_preset(preset_key: str) -> bool:
    return preset_key in BOOKLET_PRESETS


def saddle_stitch_pairs(page_count: int) -> list[tuple[int | None, int | None, int | None, int | None]]:
    """Page indices for each printed sheet of a saddle-stitch booklet.

    Returns a list of (front_left, front_right, back_left, back_right) tuples
    of 1-based page numbers. None = blank padding (when source page count
    isn't a multiple of 4, the booklet is padded to the next multiple).
    """
    if page_count < 1:
        return []
    n4 = ((page_count + 3) // 4) * 4
    sheets: list[tuple[int | None, int | None, int | None, int | None]] = []

    def in_range(p: int) -> int | None:
        return p if 1 <= p <= page_count else None

    for i in range(n4 // 4):
        fl = n4 - 2 * i
        fr = 1 + 2 * i
        bl = 2 + 2 * i
        br = n4 - 1 - 2 * i
        sheets.append((in_range(fl), in_range(fr), in_range(bl), in_range(br)))
    return sheets


def booklet_sheets_per_copy(page_count: int) -> int:
    """Number of parent sheets one booklet of `page_count` pages requires."""
    if page_count <= 0:
        return 0
    return (page_count + 3) // 4


def booklet_sheets_needed(page_count: int, quantity: int) -> int:
    """Total parent sheets for `quantity` copies of a booklet."""
    return booklet_sheets_per_copy(page_count) * max(quantity, 1)


def _add_booklet_marks(
    target_page,
    sheet: SheetSpec,
    ox: float,
    oy: float,
    pw: float,
    ph: float,
    *,
    add_crop_marks: bool,
    add_reg_marks: bool,
    add_fold_guide: bool,
    out_pdf: pikepdf.Pdf,
) -> None:
    """Draw crop marks at outer corners + spine head/foot, reg marks on sheet
    midpoints, and a dashed fold guide down the spine. Marks are baked into
    the content stream (survive RIP).
    """
    ops_lines: list[str] = []
    spine_x = ox + pw

    if add_crop_marks:
        # Outer corners of the spread (4 marks)
        ops_lines.append(crop_mark_pdf_ops(ox, oy))                          # bottom-left
        ops_lines.append(crop_mark_pdf_ops(ox, oy + ph, length=9, gap=9))    # top-left
        ops_lines.append(crop_mark_pdf_ops(ox + 2 * pw, oy, length=9, gap=-9))           # bottom-right
        ops_lines.append(crop_mark_pdf_ops(ox + 2 * pw, oy + ph, length=9, gap=-9))      # top-right
        # Spine head + foot (so the cutter has a head/foot reference at the fold)
        ops_lines.append(crop_mark_pdf_ops(spine_x, oy))
        ops_lines.append(crop_mark_pdf_ops(spine_x, oy + ph, length=9, gap=9))

    if add_reg_marks:
        ops_lines.append(reg_mark_pdf_ops(sheet.width_pt / 2, inches(0.25)))
        ops_lines.append(reg_mark_pdf_ops(sheet.width_pt / 2, sheet.height_pt - inches(0.25)))
        ops_lines.append(reg_mark_pdf_ops(inches(0.25), sheet.height_pt / 2))
        ops_lines.append(reg_mark_pdf_ops(sheet.width_pt - inches(0.25), sheet.height_pt / 2))

    if add_fold_guide:
        ops_lines.append(fold_guide_pdf_ops(spine_x, inches(0.25), sheet.height_pt - inches(0.5)))

    if not ops_lines:
        return

    content_stream = " ".join(ops_lines).encode("latin-1")
    existing_contents = target_page.obj.get(Name.Contents)
    if existing_contents is None:
        target_page.obj[Name.Contents] = out_pdf.make_stream(content_stream)
    else:
        marks_stream = out_pdf.make_stream(content_stream)
        if isinstance(existing_contents, pikepdf.Array):
            existing_contents.append(marks_stream)
        else:
            target_page.obj[Name.Contents] = pikepdf.Array([existing_contents, marks_stream])


def _booklet_spread_geometry(
    sheet: SheetSpec, pw: float, ph: float, bleed: float
) -> tuple[float, float, Rectangle, Rectangle]:
    """Trim origin (ox, oy) of the centered 2-up spread plus the per-page
    *placement* rects.

    Each page is placed at BLEED size — (pw + 2·bleed) × (ph + 2·bleed) — so a
    full-bleed source (MediaBox = trim + bleed) maps 1:1 and its background
    extends past the trim/cut line on the three outer edges and across the
    spine. Crop marks are still drawn at the trim corners (ox, oy, pw, ph), so
    the operator's cut lands on trim and the bleed gets trimmed off cleanly —
    no white slivers.

    The previous code placed pages into trim-sized rects, which made
    add_overlay scale the bleed artwork ~3% DOWN to fit and left zero bleed
    past the cut line. With bleed=0 (fold-only presets) the rects collapse
    back to the exact trim rects, so those presets are unchanged.
    """
    spread_w = 2 * pw
    spread_h = ph
    ox = (sheet.width_pt - spread_w) / 2
    oy = (sheet.height_pt - spread_h) / 2
    left_rect = Rectangle(ox - bleed, oy - bleed, ox + pw + bleed, oy + ph + bleed)
    right_rect = Rectangle(ox + pw - bleed, oy - bleed, ox + 2 * pw + bleed, oy + ph + bleed)
    return ox, oy, left_rect, right_rect


def impose_booklet(
    artwork_pdf: Path,
    *,
    preset: BookletPreset,
    output_pdf: Path,
    quantity: int = 1,
    add_crop_marks: bool = True,
    add_reg_marks: bool = True,
    add_fold_guide: bool = True,
) -> dict:
    """Impose a multi-page artwork as N saddle-stitch booklet copies.

    Source page 1 = booklet page 1, etc. For each copy, ceil(N/4) sheets are
    emitted in printer's-spread order. Output PDF: front, back, front, back...
    grouped by sheet, then by copy.

    The artwork's page MediaBox is placed at trim size on the sheet — operator
    should run bleed-fix beforehand if the design needs trim-extended bleed.
    """
    if not artwork_pdf.exists():
        raise FileNotFoundError(artwork_pdf)
    if not preset.fits():
        raise ValueError(
            f"Booklet preset doesn't fit: 2× {preset.page_w_in}×{preset.page_h_in} "
            f"+ {preset.bleed_in}\" bleed exceeds {preset.sheet.name} "
            f"({preset.sheet.width_in}×{preset.sheet.height_in})"
        )

    src = pikepdf.open(str(artwork_pdf))
    page_count = len(src.pages)
    if page_count < 1:
        src.close()
        raise ValueError("Booklet needs at least 1 source page")

    sheet = preset.sheet
    pw = inches(preset.page_w_in)
    ph = inches(preset.page_h_in)
    bleed = inches(preset.bleed_in)

    ox, oy, left_rect, right_rect = _booklet_spread_geometry(sheet, pw, ph, bleed)

    out = pikepdf.new()
    pairs = saddle_stitch_pairs(page_count)
    sheets_per_copy = len(pairs)
    copies = max(quantity, 1)

    def place(target, src_idx: int | None, rect: Rectangle) -> None:
        if src_idx is None:
            return
        target.add_overlay(src.pages[src_idx - 1], rect)

    for _copy in range(copies):
        for fl, fr, bl, br in pairs:
            # Front
            front = out.add_blank_page(page_size=(sheet.width_pt, sheet.height_pt))
            place(front, fl, left_rect)
            place(front, fr, right_rect)
            _add_booklet_marks(
                front, sheet, ox, oy, pw, ph,
                add_crop_marks=add_crop_marks,
                add_reg_marks=add_reg_marks,
                add_fold_guide=add_fold_guide,
                out_pdf=out,
            )
            # Back
            back = out.add_blank_page(page_size=(sheet.width_pt, sheet.height_pt))
            place(back, bl, left_rect)
            place(back, br, right_rect)
            _add_booklet_marks(
                back, sheet, ox, oy, pw, ph,
                add_crop_marks=add_crop_marks,
                add_reg_marks=add_reg_marks,
                add_fold_guide=add_fold_guide,
                out_pdf=out,
            )

    out.save(str(output_pdf))
    src.close()
    out.close()

    return {
        "output": str(output_pdf),
        "sheet": sheet.name,
        "source_pages": page_count,
        "sheets_per_copy": sheets_per_copy,
        "copies": copies,
        "total_sheets": sheets_per_copy * copies,
        "bleed_in": preset.bleed_in,
        "trim_after": preset.trim_after,
    }


# Operator-facing labels for each layout. The dropdown shows these instead of
# the raw "21-up Business Card on 12x18" tech string. Keep the friendly label
# focused on what the operator actually picks: the piece + how many fit.
FRIENDLY_PRESET_LABELS: dict[str, str] = {
    "bc_21up_12x18": "Business cards — 21 per sheet (standard)",
    "bc_8up_letter": "Business cards — 8 per letter sheet",
    "bc_10up_legal": "Business cards — 10 per legal sheet",
    "bc_21up_sra3": "Business cards — 21 per SRA3 sheet",
    "flyer_half_2up_letter": "Half-letter flyers — 2 per letter sheet",
    "pc_3x4_12up_18x12": "Postcards 3×4 — 12 per sheet",
    "pc_4x6_4up_18x12": "Postcards 4×6 — 4 per sheet",
    "pc_5x7_4up_18x12": "Postcards 5×7 — 4 per sheet",
    "flyer_1up_letter": "Letter flyer — 1 per sheet",
    "trifold_1up_letter": "Tri-fold brochure — 1 per sheet",
    "bifold_1up_11x17": "Bi-fold brochure — 1 per 11×17 sheet",
    "halffold_1up_letter": "Half-fold card — 1 per sheet",
    "poster_1up_letter": "Letter poster — 1 per sheet",
    "poster_1up_11x17": "11×17 poster — 1 per sheet",
}


def fold_guide_pdf_ops(x: float, y: float, height: float) -> str:
    """Dashed vertical fold-guide line. Light grey, low priority — operator hint."""
    return (
        f"q 0.6 0.6 0.6 RG 0.5 w [3 3] 0 d "
        f"{x} {y} m {x} {y + height} l S "
        "[] 0 d Q"
    )


def crop_mark_pdf_ops(x: float, y: float, length: float = 9.0, gap: float = 9.0) -> str:
    """Return PDF content-stream ops drawing a crop-mark cross at (x,y).

    The mark is two strokes meeting at a corner — horizontal arm to the right,
    vertical arm upward. Caller mirrors as needed for the four corners. `gap`
    is the offset from the trim edge so the mark sits clear of artwork.
    """
    return (
        "q 0 0 0 RG 0.4 w "
        f"{x + gap} {y} m {x + gap + length} {y} l S "
        f"{x} {y + gap} m {x} {y + gap + length} l S "
        "Q"
    )


def reg_mark_pdf_ops(cx: float, cy: float, size: float = 6.0) -> str:
    """Small target-style registration mark (centered cross + outer square)."""
    half = size / 2
    return (
        f"q 0 0 0 RG 0.4 w "
        f"{cx - half} {cy} m {cx + half} {cy} l S "
        f"{cx} {cy - half} m {cx} {cy + half} l S "
        f"{cx - half} {cy - half} {size} {size} re S "
        "Q"
    )


def impose_grid(
    artwork_pdf: Path,
    *,
    layout: GridLayout,
    output_pdf: Path,
    sides: int = 1,
    add_crop_marks: bool = True,
    add_reg_marks: bool = True,
    fold_guides: list[float] | None = None,
) -> dict:
    """Place a single-page artwork PDF onto a parent sheet using a grid layout.

    `sides=2` expects the input PDF to have two pages (front + back). Output is
    a multi-page PDF: page 1 = front imposed, page 2 = back imposed (mirrored).

    Crop and registration marks are baked into the output stream, not drawn as
    annotations — that means they survive RIP and print on the press.
    """
    if not artwork_pdf.exists():
        raise FileNotFoundError(artwork_pdf)
    if not layout.fits():
        raise ValueError(f"Layout {layout} does not fit on sheet {layout.sheet.name}")

    src = pikepdf.open(str(artwork_pdf))
    if len(src.pages) < sides:
        raise ValueError(f"Artwork has {len(src.pages)} page(s); need {sides} for {sides}-sided imposition")

    sheet = layout.sheet
    piece = layout.piece
    gutter = inches(layout.gutter_in)
    bleed = inches(piece.bleed_in)

    total_grid_w = layout.cols * piece.bleed_w + (layout.cols - 1) * gutter
    total_grid_h = layout.rows * piece.bleed_h + (layout.rows - 1) * gutter
    origin_x = (sheet.width_pt - total_grid_w) / 2
    origin_y = (sheet.height_pt - total_grid_h) / 2

    out = pikepdf.new()

    def build_imposed_page(src_page_index: int, mirror: bool) -> None:
        sheet_page = out.add_blank_page(page_size=(sheet.width_pt, sheet.height_pt))
        artwork = src.pages[src_page_index]

        for r in range(layout.rows):
            for c in range(layout.cols):
                col_index = (layout.cols - 1 - c) if mirror else c
                x = origin_x + col_index * (piece.bleed_w + gutter)
                y = origin_y + r * (piece.bleed_h + gutter)
                sheet_page.add_overlay(
                    artwork,
                    Rectangle(x, y, x + piece.bleed_w, y + piece.bleed_h),
                )

        if add_crop_marks or add_reg_marks:
            ops_lines: list[str] = []
            if add_crop_marks:
                for r in range(layout.rows):
                    for c in range(layout.cols):
                        x = origin_x + c * (piece.bleed_w + gutter)
                        y = origin_y + r * (piece.bleed_h + gutter)
                        trim_x = x + bleed
                        trim_y = y + bleed
                        trim_x2 = trim_x + piece.trim_w
                        trim_y2 = trim_y + piece.trim_h
                        ops_lines.append(crop_mark_pdf_ops(trim_x, trim_y))
                        ops_lines.append(crop_mark_pdf_ops(trim_x2, trim_y, length=9, gap=-9))
                        ops_lines.append(crop_mark_pdf_ops(trim_x, trim_y2, length=9, gap=9))
                        ops_lines.append(crop_mark_pdf_ops(trim_x2, trim_y2, length=9, gap=-9))
            if add_reg_marks:
                ops_lines.append(reg_mark_pdf_ops(sheet.width_pt / 2, inches(0.25)))
                ops_lines.append(reg_mark_pdf_ops(sheet.width_pt / 2, sheet.height_pt - inches(0.25)))
                ops_lines.append(reg_mark_pdf_ops(inches(0.25), sheet.height_pt / 2))
                ops_lines.append(reg_mark_pdf_ops(sheet.width_pt - inches(0.25), sheet.height_pt / 2))

            # Fold-guide ghost lines (vertical dashed) for fold workflows.
            if fold_guides:
                for frac in fold_guides:
                    fx = sheet.width_pt * frac
                    ops_lines.append(fold_guide_pdf_ops(fx, inches(0.25), sheet.height_pt - inches(0.5)))

            content_stream = " ".join(ops_lines).encode("latin-1")
            existing_contents = sheet_page.obj.get(Name.Contents)
            if existing_contents is None:
                sheet_page.obj[Name.Contents] = out.make_stream(content_stream)
            else:
                marks_stream = out.make_stream(content_stream)
                if isinstance(existing_contents, pikepdf.Array):
                    existing_contents.append(marks_stream)
                else:
                    sheet_page.obj[Name.Contents] = pikepdf.Array([existing_contents, marks_stream])

    build_imposed_page(0, mirror=False)
    if sides == 2:
        build_imposed_page(1, mirror=True)

    out.save(str(output_pdf))
    src.close()
    out.close()

    return {
        "output": str(output_pdf),
        "sheet": sheet.name,
        "pieces_per_sheet": layout.total_pieces,
        "sides": sides,
        "bleed_in": piece.bleed_in,
        "gutter_in": layout.gutter_in,
    }


def sheets_needed(quantity: int, layout: GridLayout) -> int:
    return -(-quantity // layout.total_pieces)
