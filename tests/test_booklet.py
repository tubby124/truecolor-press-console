"""Saddle-stitch booklet imposition tests.

Covers the page-ordering math (printer's spread) for typical and edge-case
booklet sizes, plus an end-to-end smoke test that renders an imposed PDF
and verifies the page count + sheet dimensions.

Run with: ``python -m pytest tests/test_booklet.py``
"""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from backend import impose


# ───────────────────────── saddle_stitch_pairs ─────────────────────────


def test_saddle_stitch_4_pages():
    """4-page booklet = 1 sheet: front (4|1), back (2|3)."""
    pairs = impose.saddle_stitch_pairs(4)
    assert pairs == [(4, 1, 2, 3)]


def test_saddle_stitch_8_pages():
    """8-page booklet = 2 sheets in printer's spread order."""
    pairs = impose.saddle_stitch_pairs(8)
    # Sheet 0: F=8|1, B=2|7    Sheet 1: F=6|3, B=4|5
    assert pairs == [
        (8, 1, 2, 7),
        (6, 3, 4, 5),
    ]


def test_saddle_stitch_12_pages():
    pairs = impose.saddle_stitch_pairs(12)
    assert pairs == [
        (12, 1, 2, 11),
        (10, 3, 4, 9),
        (8, 5, 6, 7),
    ]


def test_saddle_stitch_pads_to_multiple_of_4():
    """5-page booklet pads to 8 — pages 6,7,8 become None (blank)."""
    pairs = impose.saddle_stitch_pairs(5)
    # n4=8, sheet 0: F=(8,1) → (None, 1), B=(2,7) → (2, None)
    # sheet 1: F=(6,3) → (None, 3), B=(4,5) → (4, 5)
    assert pairs == [
        (None, 1, 2, None),
        (None, 3, 4, 5),
    ]


def test_saddle_stitch_zero_pages():
    assert impose.saddle_stitch_pairs(0) == []


def test_booklet_sheets_per_copy():
    assert impose.booklet_sheets_per_copy(4) == 1
    assert impose.booklet_sheets_per_copy(8) == 2
    assert impose.booklet_sheets_per_copy(5) == 2  # padded to 8
    assert impose.booklet_sheets_per_copy(0) == 0


def test_booklet_sheets_needed_quantity():
    # 8 pages × 5 copies = 2 sheets/copy × 5 = 10 sheets
    assert impose.booklet_sheets_needed(8, 5) == 10
    # quantity 0 still produces at least 1 copy (matches max(quantity, 1))
    assert impose.booklet_sheets_needed(8, 0) == 2


# ───────────────────────── BookletPreset.fits ─────────────────────────


def test_8_5x11_on_12x18_fits_with_bleed():
    p = impose.BOOKLET_PRESETS["booklet_8.5x11_12x18"]
    assert p.fits()
    assert p.bleed_in == 0.125
    assert p.trim_after is True


def test_5_5x8_5_on_letter_fits():
    p = impose.BOOKLET_PRESETS["booklet_5.5x8.5_letter"]
    assert p.fits()
    assert p.bleed_in == 0.0
    assert p.trim_after is False


def test_oversized_booklet_doesnt_fit():
    """Sanity: 11×17 pages on letter sheet should fail .fits()."""
    bad = impose.BookletPreset(
        sheet=impose.SHEETS["letter-l"],
        page_w_in=11.0, page_h_in=17.0,
        bleed_in=0.0, trim_after=False, label="bad",
    )
    assert not bad.fits()


# ───────────────────────── impose_booklet end-to-end ─────────────────────────


def _make_source_pdf(path: Path, page_count: int, page_w_in: float = 8.5, page_h_in: float = 11.0) -> None:
    """Create a minimal multi-page PDF for booklet imposition tests."""
    pdf = pikepdf.new()
    for _ in range(page_count):
        pdf.add_blank_page(page_size=(page_w_in * 72, page_h_in * 72))
    pdf.save(str(path))
    pdf.close()


def test_impose_booklet_8page_single_copy(tmp_path: Path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "imposed.pdf"
    _make_source_pdf(src, 8)
    result = impose.impose_booklet(
        src,
        preset=impose.BOOKLET_PRESETS["booklet_8.5x11_12x18"],
        output_pdf=out,
        quantity=1,
    )
    assert result["sheets_per_copy"] == 2
    assert result["copies"] == 1
    assert result["total_sheets"] == 2
    assert result["bleed_in"] == 0.125
    assert result["trim_after"] is True

    # Output PDF: 2 sheets × 2 sides = 4 pages, all 18×12
    with pikepdf.open(str(out)) as p:
        assert len(p.pages) == 4
        for page in p.pages:
            mb = page.mediabox
            w_pt = float(mb[2]) - float(mb[0])
            h_pt = float(mb[3]) - float(mb[1])
            assert round(w_pt / 72, 1) == 18.0
            assert round(h_pt / 72, 1) == 12.0


def test_impose_booklet_quantity_multiplies_pages(tmp_path: Path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "imposed.pdf"
    _make_source_pdf(src, 4)  # 1 sheet per copy
    result = impose.impose_booklet(
        src,
        preset=impose.BOOKLET_PRESETS["booklet_8.5x11_12x18"],
        output_pdf=out,
        quantity=3,
    )
    assert result["total_sheets"] == 3
    with pikepdf.open(str(out)) as p:
        # 3 copies × 1 sheet × 2 sides = 6 PDF pages
        assert len(p.pages) == 6


def test_impose_booklet_5_5x8_5_letter(tmp_path: Path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "imposed.pdf"
    _make_source_pdf(src, 8, page_w_in=5.5, page_h_in=8.5)
    result = impose.impose_booklet(
        src,
        preset=impose.BOOKLET_PRESETS["booklet_5.5x8.5_letter"],
        output_pdf=out,
        quantity=1,
    )
    assert result["sheets_per_copy"] == 2
    assert result["bleed_in"] == 0.0
    assert result["trim_after"] is False
    with pikepdf.open(str(out)) as p:
        assert len(p.pages) == 4  # 2 sheets × 2 sides
        for page in p.pages:
            mb = page.mediabox
            w_pt = float(mb[2]) - float(mb[0])
            h_pt = float(mb[3]) - float(mb[1])
            # Letter landscape: 11 × 8.5
            assert round(w_pt / 72, 1) == 11.0
            assert round(h_pt / 72, 1) == 8.5


def test_impose_booklet_pads_blank_pages(tmp_path: Path):
    """5 source pages → padded to 8 (3 blanks). Output still renders 2 sheets."""
    src = tmp_path / "src.pdf"
    out = tmp_path / "imposed.pdf"
    _make_source_pdf(src, 5)
    result = impose.impose_booklet(
        src,
        preset=impose.BOOKLET_PRESETS["booklet_8.5x11_12x18"],
        output_pdf=out,
        quantity=1,
    )
    assert result["source_pages"] == 5
    assert result["sheets_per_copy"] == 2
    with pikepdf.open(str(out)) as p:
        assert len(p.pages) == 4


def test_impose_booklet_empty_source_raises(tmp_path: Path):
    src = tmp_path / "src.pdf"
    out = tmp_path / "imposed.pdf"
    _make_source_pdf(src, 0)
    with pytest.raises(ValueError, match="at least 1 source page"):
        impose.impose_booklet(
            src,
            preset=impose.BOOKLET_PRESETS["booklet_8.5x11_12x18"],
            output_pdf=out,
        )


def test_is_booklet_preset_helper():
    assert impose.is_booklet_preset("booklet_8.5x11_12x18") is True
    assert impose.is_booklet_preset("booklet_5.5x8.5_letter") is True
    assert impose.is_booklet_preset("bc_21up_12x18") is False
    assert impose.is_booklet_preset("nonexistent") is False
