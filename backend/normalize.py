"""Multi-format input → PDF normalization.

Designers ship PSDs, exports as PNG/JPG, occasionally EPS or AI. We unify
everything to PDF before preflight + imposition. Native PDF is pass-through.

| Input       | Pipeline                                                   |
| .pdf        | pass-through                                               |
| .ai         | pass-through (AI files are PDF-compatible since CS2)       |
| .psd        | psd-tools flatten → composite PIL image → PDF              |
| .png/.jpg/.jpeg/.tif/.tiff | Pillow → wrap in single-page PDF             |
| .eps        | Ghostscript ps2pdf                                         |
| .docx/.pptx | block with friendly message (save as PDF first)            |
| .html       | block (browser save-as-PDF first)                          |
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PDF_PASSTHROUGH = {".pdf", ".ai"}
RASTER = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PSD = {".psd"}
EPS = {".eps", ".ps"}
BLOCKED = {".docx", ".pptx", ".doc", ".ppt", ".html", ".htm", ".xls", ".xlsx"}


class NormalizeError(Exception):
    """Raised for unrecoverable normalization failures (corrupt input, missing tool)."""


class UnsupportedInput(Exception):
    """Raised when the input type is intentionally blocked with a friendly message."""

    def __init__(self, ext: str, friendly: str):
        self.ext = ext
        self.friendly = friendly
        super().__init__(friendly)


@dataclass
class NormalizeResult:
    pdf_path: Path
    source_kind: str  # "pdf" | "ai" | "psd" | "raster" | "eps"
    notes: list[str]


def normalize(src: Path, *, out_dir: Path) -> NormalizeResult:
    """Convert any supported input to PDF. Returns the PDF path + source kind."""
    if not src.exists():
        raise NormalizeError(f"Input file not found: {src}")
    ext = src.suffix.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    if ext in BLOCKED:
        raise UnsupportedInput(ext, _block_message(ext))

    if ext in PDF_PASSTHROUGH:
        return NormalizeResult(pdf_path=src, source_kind=ext.lstrip("."), notes=notes)

    if ext in RASTER:
        out = out_dir / (src.stem + ".pdf")
        _raster_to_pdf(src, out, notes)
        return NormalizeResult(pdf_path=out, source_kind="raster", notes=notes)

    if ext in PSD:
        out = out_dir / (src.stem + ".pdf")
        _psd_to_pdf(src, out, notes)
        return NormalizeResult(pdf_path=out, source_kind="psd", notes=notes)

    if ext in EPS:
        out = out_dir / (src.stem + ".pdf")
        _eps_to_pdf(src, out)
        return NormalizeResult(pdf_path=out, source_kind="eps", notes=notes)

    raise UnsupportedInput(
        ext, f"File type {ext} isn't supported. Save as PDF and drop again."
    )


def _block_message(ext: str) -> str:
    if ext in (".docx", ".doc"):
        return ("We can't print Word docs directly — they render differently on every machine. "
                "In Word: File → Save As → PDF, then drop the PDF here.")
    if ext in (".pptx", ".ppt"):
        return ("We can't print PowerPoint files directly. In PowerPoint: File → Export → "
                "Create PDF/XPS Document, then drop the PDF here.")
    if ext in (".xls", ".xlsx"):
        return ("Excel files don't render reliably for print. Save as PDF first.")
    if ext in (".html", ".htm"):
        return ("HTML can't go straight to the press. In your browser: File → Print → Save as PDF, "
                "then drop the PDF here.")
    return f"File type {ext} isn't supported. Save as PDF and drop again."


def _raster_to_pdf(src: Path, dst: Path, notes: list[str]) -> None:
    """PNG / JPG / TIFF → single-page PDF at native pixel size, 300 DPI assumption."""
    from PIL import Image

    with Image.open(src) as img:
        # Convert to RGB (PDFs need RGB or CMYK; handle alpha by flattening on white).
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
            notes.append("Transparent background flattened on white.")
        elif img.mode != "RGB" and img.mode != "CMYK":
            img = img.convert("RGB")

        dpi = img.info.get("dpi") or (300, 300)
        if isinstance(dpi, tuple):
            dpi_x = dpi[0] or 300
        else:
            dpi_x = dpi or 300
        if dpi_x < 150:
            notes.append(
                f"Image was {int(dpi_x)} DPI — that's print-low. Will look soft."
            )

        img.save(dst, "PDF", resolution=float(dpi_x))


def _psd_to_pdf(src: Path, dst: Path, notes: list[str]) -> None:
    """Flatten PSD via psd-tools → PIL → PDF."""
    try:
        from psd_tools import PSDImage
    except ImportError as e:
        raise NormalizeError(f"psd-tools not installed: {e}")

    psd = PSDImage.open(str(src))
    composite = psd.composite()
    if composite is None:
        raise NormalizeError("PSD has no composite image — try saving as a flattened TIFF or PDF.")
    if composite.mode in ("RGBA", "LA"):
        from PIL import Image as _Img
        bg = _Img.new("RGB", composite.size, (255, 255, 255))
        bg.paste(composite, mask=composite.split()[-1])
        composite = bg
        notes.append("PSD transparency flattened on white.")
    elif composite.mode not in ("RGB", "CMYK"):
        composite = composite.convert("RGB")

    notes.append(f"PSD flattened from {len(psd)} layer(s).")
    composite.save(dst, "PDF", resolution=300.0)


def _eps_to_pdf(src: Path, dst: Path) -> None:
    gs = shutil.which("gs")
    if gs is None:
        raise NormalizeError("Ghostscript (`gs`) not on PATH — required for EPS conversion.")
    subprocess.run(
        [gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER", "-sDEVICE=pdfwrite",
         f"-sOutputFile={dst}", str(src)],
        check=True, capture_output=True, timeout=60,
    )
