"""Bleed auto-fix.

When preflight finds insufficient bleed, expand each page's MediaBox by the
missing margin so the imposition step's crop marks can do their job. This is
the cheap "trim-extend" strategy — it works perfectly when the artwork has a
full-bleed background that extends past the trim line; it produces white
slivers if the design literally ends at the trim. We surface that caveat in
the toast on the frontend.

A heavier "render-to-PNG-and-edge-extend" strategy is on the v2 backlog. The
common case at this shop (background colors, patterned art, photographic
backgrounds) is well-served by trim-extend.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf

from .preflight import run as run_preflight


def fix_bleed(pdf_path: Path, *, target_bleed_in: float = 0.125) -> tuple[Path, float]:
    """Expand each page's MediaBox so the bleed margin reaches `target_bleed_in`.

    Writes a sibling file `<stem>__bleedfix.pdf`. Returns (output_path, bleed_added_in)
    where `bleed_added_in` is how much we grew each side (uniform). If the file
    already has enough bleed, returns the original path and 0.0.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    target_pt = target_bleed_in * 72.0
    out_path = pdf_path.with_name(pdf_path.stem + "__bleedfix.pdf")

    src = pikepdf.open(str(pdf_path))
    grew = 0.0

    with src:
        worst_short = target_pt
        for page in src.pages:
            mb = page.mediabox
            trim = page.get("/TrimBox") or page.get("/CropBox")
            if trim is None:
                # No TrimBox — assume zero bleed; we need the full target.
                worst_short = min(worst_short, 0.0)
                continue
            margin = min(
                float(trim[0]) - float(mb[0]),
                float(trim[1]) - float(mb[1]),
                float(mb[2]) - float(trim[2]),
                float(mb[3]) - float(trim[3]),
            )
            worst_short = min(worst_short, margin)

        # Already enough bleed everywhere.
        if worst_short >= target_pt - 1:
            return pdf_path, 0.0

        grew_pt = target_pt - max(worst_short, 0.0)
        grew = grew_pt / 72.0

        for page in src.pages:
            mb = page.mediabox
            x0, y0, x1, y1 = (float(mb[0]), float(mb[1]), float(mb[2]), float(mb[3]))
            page.mediabox = pikepdf.Array([
                x0 - grew_pt,
                y0 - grew_pt,
                x1 + grew_pt,
                y1 + grew_pt,
            ])
            # Don't shift TrimBox — that's what defines the cut line. Preserving it
            # lets imposition/crop marks line up correctly against the original art.

        src.save(str(out_path))

    return out_path, round(grew, 4)


def report_after_fix(fixed_path: Path, expect_bleed_in: float) -> dict:
    """Re-run preflight on the fixed PDF and return a dict suitable for /api response."""
    report = run_preflight(fixed_path, expect_bleed_in=expect_bleed_in)
    return {
        "page_count": report.page_count,
        "page_sizes": report.page_sizes,
        "findings": [
            {"severity": f.severity, "code": f.code, "message": f.message, "page": f.page}
            for f in report.findings
        ],
        "can_send": report.can_send,
    }
