"""PDF thumbnail rendering via Ghostscript.

We render page 1 of an imposed PDF to a 200px-wide PNG for the job history
panel. Cached on disk next to the imposed.pdf so repeat hits are free.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_thumb(pdf_path: Path, out_png: Path, *, width_px: int = 240) -> Path:
    """Render page 1 of pdf_path to out_png. Returns out_png on success.

    Uses Ghostscript. Cached: returns immediately if out_png exists and is
    newer than the source PDF.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    if out_png.exists() and out_png.stat().st_mtime >= pdf_path.stat().st_mtime:
        return out_png

    gs = shutil.which("gs")
    if gs is None:
        raise RuntimeError("Ghostscript (`gs`) not found on PATH")

    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        gs, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
        "-sDEVICE=png16m",
        f"-dFirstPage=1", f"-dLastPage=1",
        f"-r{max(72, min(150, width_px // 4))}",
        f"-sOutputFile={out_png}",
        str(pdf_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    return out_png
