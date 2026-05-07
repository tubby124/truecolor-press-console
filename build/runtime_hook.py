"""PyInstaller runtime hook — runs BEFORE any user code in the frozen exe.

Purpose: prepend bundled tooling onto PATH so libraries that resolve binaries
via shutil.which() (Ghostscript today, possibly LibreOffice / qpdf later)
find the bundled copies instead of erroring.

This duplicates wire_bundled_ghostscript() in launch.py because PyInstaller
imports backend.* during bootstrap (collect-all sweep), and at that point
launch.main() hasn't run yet. The hook makes the PATH change happen earlier.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _internal() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


def _prepend_path(p: Path) -> None:
    if p.is_dir():
        os.environ["PATH"] = f"{p}{os.pathsep}{os.environ.get('PATH', '')}"


_prepend_path(_internal() / "gs" / "bin")
# Future: _prepend_path(_internal() / "libreoffice" / "program")
# Future: _prepend_path(_internal() / "qpdf" / "bin")
