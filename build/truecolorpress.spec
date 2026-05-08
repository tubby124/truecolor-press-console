# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for True Color Press Console — Windows onedir build.

Inputs the build-windows.ps1 script stages before running pyinstaller:
  build/vendored/config.v1.csv     — copy of estimator's config.v1.csv
  build/gs-portable/               — Ghostscript Windows install copy
  frontend/dist/                   — output of `npm run build`

Run via:  pyinstaller build/truecolorpress.spec
Output:   dist/TrueColorPress/TrueColorPress.exe (+ supporting files)
"""

import os
from pathlib import Path

# spec files are exec()'d, no __file__. SPECPATH is provided by PyInstaller.
SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821
REPO_ROOT = SPEC_DIR.parent

block_cipher = None


def _opt_tree(src: Path, dst: str):
    """Tree() if src exists else nothing — keeps the spec runnable on a
    half-prepared build machine for early smoke-testing."""
    return [(str(src), dst)] if src.exists() else []


datas = []
datas += _opt_tree(REPO_ROOT / "frontend" / "dist", "frontend/dist")
datas += _opt_tree(REPO_ROOT / "icc", "icc")
datas += _opt_tree(REPO_ROOT / "assets" / "test-patterns", "assets/test-patterns")
datas += _opt_tree(SPEC_DIR / "vendored" / "config.v1.csv", "data")
datas += _opt_tree(SPEC_DIR / "gs-portable", "gs")


a = Analysis(
    [str(SPEC_DIR / "launch.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # uvicorn lazy-loads these; PyInstaller's static analysis misses them.
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # pydantic-settings env_file loader uses these.
        "dotenv",
        # FastAPI uses these for form/multipart parsing.
        "multipart",
        "python_multipart",
        # pysnmp (live press state) — its plugin discovery system uses lazy
        # imports that PyInstaller can miss. List the protocol layers explicitly.
        "pysnmp.entity.engine",
        "pysnmp.entity.rfc3413",
        "pysnmp.entity.rfc3413.cmdgen",
        "pysnmp.hlapi",
        "pysnmp.hlapi.v3arch",
        "pysnmp.hlapi.v3arch.asyncio",
        "pysnmp.smi.builder",
        "pysnmp.smi.compiler",
        "pyasn1.codec.ber",
        "pyasn1.codec.cer",
        "pyasn1.codec.der",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(SPEC_DIR / "runtime_hook.py")],
    excludes=[
        # Trim the bundle: backend has no use for these heavy tk/test bits.
        "tkinter",
        "test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TrueColorPress",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep console visible — uvicorn logs go there for first-run debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # add a .ico later if branding lands
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TrueColorPress",
)
