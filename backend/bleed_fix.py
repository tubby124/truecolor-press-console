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

────── Edge sampling ──────

Before any extend we render the page at low DPI with Ghostscript and look at
the average luminance of the strip just inside each trim edge. If all four
edges are near-white (>240/255 by default), there is no background to
extend — trim-extending would just hide white slivers behind crop marks and
mislead the operator. In that case we raise `BleedNoContentError` and the
route catches it and returns 422 with a friendlier message ("re-export with
bleed in your design tool").

Threshold philosophy: fail-safe to extend. If we can't render the page
(missing Ghostscript, malformed PDF, exception), we skip the check and
proceed with the extend — that's the existing behavior the operator already
accepts.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pikepdf

from .preflight import run as run_preflight


class BleedNoContentError(Exception):
    """Raised when the design ends at the trim line with no background to extend."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "The design appears to end exactly at the cut line — there's no "
            "background to stretch outward. Re-export from your design tool with "
            "at least 1/8 inch bleed."
        )


def fix_bleed(pdf_path: Path, *, target_bleed_in: float = 0.125) -> tuple[Path, float]:
    """Expand each page's MediaBox so the bleed margin reaches `target_bleed_in`.

    Writes a sibling file `<stem>__bleedfix.pdf`. Returns (output_path, bleed_added_in)
    where `bleed_added_in` is how much we grew each side (uniform). If the file
    already has enough bleed, returns the original path and 0.0.

    Raises `BleedNoContentError` if the page-1 trim edges are all near-white
    (i.e. the design has no background to extend).
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

        # Pre-flight the trim edges: if they're all near-white, extending the
        # MediaBox just makes the white slivers wider. Tell the operator to
        # re-export from their design tool with bleed instead.
        if _trim_edges_are_white(pdf_path):
            raise BleedNoContentError()

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


# ─────────────────────── edge-luminance sampling ────────────────────────


# Threshold: average pixel value (0-255) above which we treat the edge as
# "white". 240 is a reasonable cutoff — paper-white scanned art comes in at
# 250+, while even the lightest tints (5% gray) average ~243 when sampled
# at 72 DPI.
_WHITE_THRESHOLD = 240
_EDGE_SAMPLE_DPI = 72  # plenty for an "is this near-white" decision
_EDGE_BAND_PT = 6.0    # pt-thick band measured from the trim edge inward


def _trim_edges_are_white(pdf_path: Path, threshold: int = _WHITE_THRESHOLD) -> bool:
    """Render page 1 at low DPI and check the four trim edges.

    Returns True iff every one of the four edge bands averages brighter than
    `threshold` (0-255 luminance). False means at least one edge has design
    content past the trim line and we can safely trim-extend.

    Fails open: any exception (missing Ghostscript, render error, Pillow not
    available) returns False so the caller proceeds with the extend.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return False

    gs = shutil.which("gs")
    if gs is None:
        return False

    try:
        with pikepdf.open(str(pdf_path)) as src:
            if len(src.pages) == 0:
                return False
            page = src.pages[0]
            mb = page.mediabox
            mb_x0, mb_y0, mb_x1, mb_y1 = (float(mb[0]), float(mb[1]), float(mb[2]), float(mb[3]))
            trim = page.get("/TrimBox") or page.get("/CropBox")
            if trim is None:
                # Without a trim box, the whole page is the trim — sample the
                # outer edges of the MediaBox itself.
                tx0, ty0, tx1, ty1 = mb_x0, mb_y0, mb_x1, mb_y1
            else:
                tx0, ty0, tx1, ty1 = (float(trim[0]), float(trim[1]), float(trim[2]), float(trim[3]))

        # Render at _EDGE_SAMPLE_DPI to PNG via Ghostscript.
        with tempfile.TemporaryDirectory() as tmp:
            png_path = Path(tmp) / "p1.png"
            cmd = [
                gs,
                "-dBATCH",
                "-dNOPAUSE",
                "-dQUIET",
                f"-r{_EDGE_SAMPLE_DPI}",
                "-sDEVICE=pnggray",
                "-dFirstPage=1",
                "-dLastPage=1",
                f"-sOutputFile={png_path}",
                str(pdf_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
            if not png_path.exists():
                return False
            img = Image.open(png_path).convert("L")

        # Convert PDF coords (origin BL, points) → image coords (origin TL, px).
        pt_to_px = _EDGE_SAMPLE_DPI / 72.0
        img_w, img_h = img.size

        # Map MediaBox onto pixel space so edge bands are referenced from
        # the trim, not the page corner.
        def x_to_px(x_pt: float) -> int:
            return max(0, min(img_w - 1, int(round((x_pt - mb_x0) * pt_to_px))))

        def y_to_px(y_pt: float) -> int:
            # PDF y increases upward; image y increases downward.
            return max(0, min(img_h - 1, int(round((mb_y1 - y_pt) * pt_to_px))))

        band_px = max(1, int(round(_EDGE_BAND_PT * pt_to_px)))

        # Four bands measured from the trim line inward (so we sample what
        # WOULD be exposed past the cut line if the press over-trimmed).
        # left edge band: x = trim left, band of width `band_px` to the right
        left_box = (x_to_px(tx0), y_to_px(ty1), x_to_px(tx0) + band_px, y_to_px(ty0))
        right_box = (x_to_px(tx1) - band_px, y_to_px(ty1), x_to_px(tx1), y_to_px(ty0))
        # top edge: y = trim top, band of height `band_px` downward (in image)
        top_box = (x_to_px(tx0), y_to_px(ty1), x_to_px(tx1), y_to_px(ty1) + band_px)
        bottom_box = (x_to_px(tx0), y_to_px(ty0) - band_px, x_to_px(tx1), y_to_px(ty0))

        edge_means: list[float] = []
        for box in (left_box, right_box, top_box, bottom_box):
            x0, y0, x1, y1 = box
            if x1 <= x0 or y1 <= y0:
                continue
            crop = img.crop((x0, y0, x1, y1))
            # Use the histogram instead of getdata() for speed on big crops.
            hist = crop.histogram()  # 256 buckets for L mode
            n = sum(hist)
            if n == 0:
                continue
            mean = sum(i * c for i, c in enumerate(hist)) / n
            edge_means.append(mean)

        if not edge_means:
            return False
        # All edges must be brighter than the threshold to declare "no content".
        return all(m >= threshold for m in edge_means)
    except Exception:
        # Any rendering / IO failure: fail open so we extend as before.
        return False


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


# Re-export for routes that want to catch the explicit case.
__all__ = ["fix_bleed", "report_after_fix", "BleedNoContentError"]
