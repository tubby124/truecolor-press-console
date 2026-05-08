"""Generate calibration test pattern PDFs.

Produces three PDFs in `assets/test-patterns/`:

  - color-blocks-letter.pdf   8.5×11, CMYK process color blocks + tints + ramps
  - registration-target-12x18.pdf 12×18, registration target
  - density-bar-letter.pdf    8.5×11, K density bar + process columns + grayscale ramp

We hand-roll content streams with pikepdf rather than pulling in reportlab
(not in pyproject deps). All strokes/fills use device CMYK so the press driver
treats the channels straight without color-management gymnastics. Total size
across all three PDFs stays under 100KB — these are simple vector shapes, not
imagery.

Run:

    python scripts/generate_test_patterns.py

Outputs to <repo>/assets/test-patterns/. Idempotent — overwrites in place.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf
from pikepdf import Dictionary, Name

PT_PER_INCH = 72.0
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "assets" / "test-patterns"


def inches(x: float) -> float:
    return x * PT_PER_INCH


# ────────────────────────── content stream helpers ──────────────────────────


class CS:
    """Tiny PDF content-stream builder. Outputs bytes to feed pikepdf.Page.contents.

    All coords are PDF points (origin bottom-left). Methods mirror the
    operators we actually need; intentionally minimal.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []

    def push(self, line: str) -> None:
        self.lines.append(line)

    # graphics state ────────────────────────
    def gsave(self) -> None:
        self.push("q")

    def grestore(self) -> None:
        self.push("Q")

    # CMYK fill / stroke ────────────────────
    def cmyk_fill(self, c: float, m: float, y: float, k: float) -> None:
        self.push(f"{c:.4f} {m:.4f} {y:.4f} {k:.4f} k")

    def cmyk_stroke(self, c: float, m: float, y: float, k: float) -> None:
        self.push(f"{c:.4f} {m:.4f} {y:.4f} {k:.4f} K")

    def gray_fill(self, g: float) -> None:
        self.push(f"{g:.4f} g")

    def line_width(self, w: float) -> None:
        self.push(f"{w:.4f} w")

    # paths ─────────────────────────────────
    def rect(self, x: float, y: float, w: float, h: float) -> None:
        self.push(f"{x:.3f} {y:.3f} {w:.3f} {h:.3f} re")

    def fill(self) -> None:
        self.push("f")

    def stroke(self) -> None:
        self.push("S")

    def fill_stroke(self) -> None:
        self.push("B")

    def move(self, x: float, y: float) -> None:
        self.push(f"{x:.3f} {y:.3f} m")

    def line(self, x: float, y: float) -> None:
        self.push(f"{x:.3f} {y:.3f} l")

    # text ──────────────────────────────────
    def text(self, font: str, size: float, x: float, y: float, body: str) -> None:
        # Single-line, ASCII only (we only emit captions / labels).
        escaped = body.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        self.push("BT")
        self.push(f"/{font} {size:.2f} Tf")
        self.push(f"{x:.3f} {y:.3f} Td")
        self.push(f"({escaped}) Tj")
        self.push("ET")

    def to_bytes(self) -> bytes:
        # WinAnsiEncoding ~= latin-1 with a few extra glyphs in the 0x80-0x9F
        # range. Anything outside collapses to '-' so we never blow up at
        # encode time. Captions are pure ASCII so this never fires in practice
        # — defensive only.
        return ("\n".join(self.lines)).encode("latin-1", errors="replace")


def _build_pdf(width_pt: float, height_pt: float, cs: CS) -> bytes:
    """Wrap a content stream into a single-page PDF using pikepdf.

    Always embeds a single Helvetica reference (Type1 standard 14 font) for
    captions; that's roughly 0 bytes overhead — no embedding required.
    """
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(width_pt, height_pt))
    page = pdf.pages[0]

    # Resources: embed Helvetica as /F1 (standard 14 — no font program needed).
    helv = pikepdf.Dictionary(
        Type=Name("/Font"),
        Subtype=Name("/Type1"),
        BaseFont=Name("/Helvetica"),
        Encoding=Name("/WinAnsiEncoding"),
    )
    helv_b = pikepdf.Dictionary(
        Type=Name("/Font"),
        Subtype=Name("/Type1"),
        BaseFont=Name("/Helvetica-Bold"),
        Encoding=Name("/WinAnsiEncoding"),
    )

    fonts = pikepdf.Dictionary(F1=pdf.make_indirect(helv), F2=pdf.make_indirect(helv_b))
    resources = pikepdf.Dictionary(Font=fonts)
    page.obj["/Resources"] = resources

    # Replace contents with our stream.
    stream = pdf.make_stream(cs.to_bytes())
    page.obj["/Contents"] = stream

    out = OUT_DIR / "_tmp.pdf"
    pdf.save(str(out))
    data = out.read_bytes()
    out.unlink()
    return data


# ────────────────────────── pattern: color blocks ──────────────────────────


def color_blocks_letter() -> bytes:
    W, H = inches(8.5), inches(11.0)
    cs = CS()

    # Page background — keep paper white. Just outline a 0.25" margin frame.
    margin = inches(0.25)
    cs.cmyk_stroke(0, 0, 0, 1)
    cs.line_width(0.5)
    cs.rect(margin, margin, W - 2 * margin, H - 2 * margin)
    cs.stroke()

    # Title
    cs.cmyk_fill(0, 0, 0, 1)
    cs.text("F2", 14, inches(0.5), H - inches(0.55), "Color Calibration - Letter")

    # Block grid: 4 cols × 3 rows for solids + tints, plus a 4-row band of ramps below.
    grid_top = H - inches(0.95)
    block_w = inches(1.5)
    block_h = inches(1.5)
    gutter = inches(0.2)
    grid_left = inches(0.6)

    solids = [
        ("Cyan 100%", (1.0, 0, 0, 0)),
        ("Magenta 100%", (0, 1.0, 0, 0)),
        ("Yellow 100%", (0, 0, 1.0, 0)),
        ("Black 100%", (0, 0, 0, 1.0)),
        ("Cyan 50%", (0.5, 0, 0, 0)),
        ("Magenta 50%", (0, 0.5, 0, 0)),
        ("Yellow 50%", (0, 0, 0.5, 0)),
        ("Black 50%", (0, 0, 0, 0.5)),
        ("Cyan 25%", (0.25, 0, 0, 0)),
        ("Magenta 25%", (0, 0.25, 0, 0)),
        ("Yellow 25%", (0, 0, 0.25, 0)),
        ("Black 25%", (0, 0, 0, 0.25)),
    ]
    for i, (label, cmyk) in enumerate(solids):
        col = i % 4
        row = i // 4
        x = grid_left + col * (block_w + gutter)
        y = grid_top - (row + 1) * block_h - row * gutter
        cs.cmyk_fill(*cmyk)
        cs.rect(x, y, block_w, block_h)
        cs.fill()
        # label below
        cs.cmyk_fill(0, 0, 0, 1)
        cs.text("F1", 8, x, y - 10, label)

    # Ramps band — 4 ramps (C, M, Y, K) each 11 steps from 0 to 100%.
    ramp_top = grid_top - 3 * (block_h + gutter) - inches(0.4)
    ramp_h = inches(0.45)
    ramp_w = W - 2 * inches(0.6)
    step_w = ramp_w / 11.0

    channel_meta = [
        ("Cyan ramp", lambda t: (t, 0, 0, 0)),
        ("Magenta ramp", lambda t: (0, t, 0, 0)),
        ("Yellow ramp", lambda t: (0, 0, t, 0)),
        ("Black ramp", lambda t: (0, 0, 0, t)),
    ]
    for ch_idx, (label, fn) in enumerate(channel_meta):
        y = ramp_top - ch_idx * (ramp_h + inches(0.25))
        cs.cmyk_fill(0, 0, 0, 1)
        cs.text("F1", 8, inches(0.6), y + ramp_h + 4, label)
        for step in range(11):
            t = step / 10.0
            cs.cmyk_fill(*fn(t))
            cs.rect(inches(0.6) + step * step_w, y, step_w, ramp_h)
            cs.fill()
        # outline
        cs.cmyk_stroke(0, 0, 0, 1)
        cs.line_width(0.5)
        cs.rect(inches(0.6), y, ramp_w, ramp_h)
        cs.stroke()

    # Bottom caption
    cs.cmyk_fill(0, 0, 0, 1)
    cs.text(
        "F1",
        9,
        inches(0.5),
        inches(0.4),
        "True Color Press Console - Color Calibration - Letter - 100% process colors + tints",
    )

    return _build_pdf(W, H, cs)


# ────────────────────────── pattern: registration target ──────────────────


def registration_target_12x18() -> bytes:
    W, H = inches(12.0), inches(18.0)
    cs = CS()

    # Black ink only — easier to inspect by eye for plate-to-plate registration
    # check we use a small CMY cross at the center too.
    cs.cmyk_stroke(0, 0, 0, 1)
    cs.cmyk_fill(0, 0, 0, 1)
    cs.line_width(0.5)

    # Page outline
    cs.rect(0.5, 0.5, W - 1, H - 1)
    cs.stroke()

    # Trim line: assume 1/8" bleed → trim at 0.125" inset on every side.
    trim_inset = inches(0.125)
    cs.cmyk_stroke(0, 0, 0, 1)
    cs.line_width(0.5)
    cs.rect(trim_inset, trim_inset, W - 2 * trim_inset, H - 2 * trim_inset)
    cs.stroke()

    # Crosshairs at trim minus 0.25" — i.e. inset 0.375" from sheet edge
    cross_inset = inches(0.375)
    cross_arm = inches(0.5)
    cross_centers = [
        (cross_inset, cross_inset),                   # bottom-left
        (W - cross_inset, cross_inset),               # bottom-right
        (cross_inset, H - cross_inset),               # top-left
        (W - cross_inset, H - cross_inset),           # top-right
    ]
    for cx, cy in cross_centers:
        # outer circle
        # approximate circle with 4 bezier-ish cubic? simpler: draw a square + cross
        # crosshair lines
        cs.move(cx - cross_arm, cy)
        cs.line(cx + cross_arm, cy)
        cs.move(cx, cy - cross_arm)
        cs.line(cx, cy + cross_arm)
        cs.stroke()
        # inner ring (square outline)
        cs.rect(cx - inches(0.1), cy - inches(0.1), inches(0.2), inches(0.2))
        cs.stroke()

    # Center crosshair — uses CMYK overprint to expose registration drift
    ccx, ccy = W / 2, H / 2
    arm = inches(0.6)
    # Cyan vertical
    cs.cmyk_stroke(1, 0, 0, 0)
    cs.line_width(1.5)
    cs.move(ccx, ccy - arm)
    cs.line(ccx, ccy + arm)
    cs.stroke()
    # Magenta horizontal
    cs.cmyk_stroke(0, 1, 0, 0)
    cs.move(ccx - arm, ccy)
    cs.line(ccx + arm, ccy)
    cs.stroke()
    # Yellow diagonal /
    cs.cmyk_stroke(0, 0, 1, 0)
    cs.move(ccx - arm * 0.7, ccy - arm * 0.7)
    cs.line(ccx + arm * 0.7, ccy + arm * 0.7)
    cs.stroke()
    # Black diagonal \
    cs.cmyk_stroke(0, 0, 0, 1)
    cs.move(ccx - arm * 0.7, ccy + arm * 0.7)
    cs.line(ccx + arm * 0.7, ccy - arm * 0.7)
    cs.stroke()
    # ring around center
    cs.line_width(0.5)
    cs.rect(ccx - inches(0.5), ccy - inches(0.5), inches(1.0), inches(1.0))
    cs.stroke()

    # Edge ruler ticks every 0.5", labeled every 1"
    cs.cmyk_stroke(0, 0, 0, 1)
    cs.cmyk_fill(0, 0, 0, 1)
    cs.line_width(0.4)

    def horizontal_ruler(y: float, label_above: bool) -> None:
        for n in range(int(W / inches(0.5)) + 1):
            x = n * inches(0.5)
            if x < trim_inset or x > W - trim_inset:
                continue
            tick = inches(0.18) if n % 2 == 0 else inches(0.08)
            cs.move(x, y)
            cs.line(x, y + tick if label_above else y - tick)
            cs.stroke()
            if n % 2 == 0:
                ly = (y + tick + 4) if label_above else (y - tick - 8)
                cs.text("F1", 6, x - 4, ly, str(n // 2))

    def vertical_ruler(x: float, label_right: bool) -> None:
        for n in range(int(H / inches(0.5)) + 1):
            y = n * inches(0.5)
            if y < trim_inset or y > H - trim_inset:
                continue
            tick = inches(0.18) if n % 2 == 0 else inches(0.08)
            cs.move(x, y)
            cs.line(x + tick if label_right else x - tick, y)
            cs.stroke()
            if n % 2 == 0:
                lx = (x + tick + 2) if label_right else (x - tick - 10)
                cs.text("F1", 6, lx, y - 2, str(n // 2))

    horizontal_ruler(trim_inset + inches(0.05), True)
    horizontal_ruler(H - trim_inset - inches(0.05), False)
    vertical_ruler(trim_inset + inches(0.05), True)
    vertical_ruler(W - trim_inset - inches(0.05), False)

    # Skew detection diagonals — 4 thin lines corner to corner, but offset so they
    # don't overlap the center crosshair.
    cs.line_width(0.3)
    cs.cmyk_stroke(0, 0, 0, 0.4)
    cs.move(trim_inset, trim_inset)
    cs.line(W - trim_inset, H - trim_inset)
    cs.stroke()
    cs.move(trim_inset, H - trim_inset)
    cs.line(W - trim_inset, trim_inset)
    cs.stroke()

    # Caption — place near bottom edge but inside trim
    cs.cmyk_fill(0, 0, 0, 1)
    cs.text(
        "F1",
        9,
        inches(0.6),
        inches(0.55),
        "Registration Target - 12x18 - check corners + center align",
    )

    return _build_pdf(W, H, cs)


# ────────────────────────── pattern: density bar ───────────────────────────


def density_bar_letter() -> bytes:
    W, H = inches(8.5), inches(11.0)
    cs = CS()

    margin = inches(0.4)

    # Title
    cs.cmyk_fill(0, 0, 0, 1)
    cs.text("F2", 14, margin, H - inches(0.5), "Density Reference - Letter")

    # 1) 100% K density strip across the top
    strip_y = H - inches(1.4)
    strip_h = inches(0.7)
    cs.cmyk_fill(0, 0, 0, 1)
    cs.rect(margin, strip_y, W - 2 * margin, strip_h)
    cs.fill()
    cs.cmyk_fill(0, 0, 0, 0)  # white text on black
    cs.gray_fill(1.0)
    cs.text("F2", 11, margin + 8, strip_y + strip_h - 16, "100% K solid")

    # 2) Process columns — 4 columns C/M/Y/K, full-bleed-ish at ~1.5" wide each
    col_top = strip_y - inches(0.4)
    col_h = inches(3.5)
    cols_total_w = W - 2 * margin
    col_w = cols_total_w / 4
    columns = [
        ("Cyan", (1, 0, 0, 0)),
        ("Magenta", (0, 1, 0, 0)),
        ("Yellow", (0, 0, 1, 0)),
        ("Black", (0, 0, 0, 1)),
    ]
    for i, (label, cmyk) in enumerate(columns):
        x = margin + i * col_w
        cs.cmyk_fill(*cmyk)
        cs.rect(x, col_top - col_h, col_w - 4, col_h)
        cs.fill()
        cs.cmyk_fill(0, 0, 0, 1) if (label == "Yellow") else cs.gray_fill(1.0)
        cs.text("F2", 10, x + 6, col_top - 16, label)

    # 3) Grayscale ramp (5 step) at the bottom
    ramp_top = col_top - col_h - inches(0.4)
    ramp_h = inches(0.9)
    steps = [0.0, 0.25, 0.5, 0.75, 1.0]
    step_w = (W - 2 * margin) / len(steps)
    for i, t in enumerate(steps):
        x = margin + i * step_w
        cs.cmyk_fill(0, 0, 0, t)
        cs.rect(x, ramp_top - ramp_h, step_w - 4, ramp_h)
        cs.fill()
        cs.cmyk_fill(0, 0, 0, 1) if t < 0.6 else cs.gray_fill(1.0)
        cs.text("F1", 9, x + 6, ramp_top - ramp_h + 8, f"K {int(t * 100)}%")

    # 4) Caption
    cs.cmyk_fill(0, 0, 0, 1)
    cs.text(
        "F1",
        9,
        margin,
        inches(0.45),
        "Density Reference - Letter - K density first, then process columns",
    )

    return _build_pdf(W, H, cs)


# ────────────────────────── main ───────────────────────────


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out: list[tuple[str, bytes]] = [
        ("color-blocks-letter.pdf", color_blocks_letter()),
        ("registration-target-12x18.pdf", registration_target_12x18()),
        ("density-bar-letter.pdf", density_bar_letter()),
    ]
    total = 0
    for name, data in out:
        path = OUT_DIR / name
        path.write_bytes(data)
        total += len(data)
        print(f"wrote {path} ({len(data) / 1024:.1f} KB)")
    print(f"total: {total / 1024:.1f} KB")


if __name__ == "__main__":
    main()
