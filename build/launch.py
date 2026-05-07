"""PyInstaller entry point for the True Color Press Console Windows build.

Responsibilities:
  1. Resolve the bundle root (works in dev AND under PyInstaller's _MEIPASS).
  2. Wire bundled Ghostscript into PATH so backend/normalize.py + backend/thumbs.py
     find it via shutil.which("gs").
  3. Point PRESS_ESTIMATOR_CONFIG_CSV at the vendored CSV inside the bundle.
  4. Start uvicorn in a background thread.
  5. Open the default browser to http://localhost:<port> once the server is up.
  6. Block on the server thread so closing the console window kills uvicorn.

Stays Mac-runnable for local smoke-testing — the shim is a no-op when the
bundled gs/ folder isn't present.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def bundle_root() -> Path:
    """Folder that contains _internal/ at runtime.

    Under PyInstaller onedir, sys._MEIPASS points at the _internal directory
    itself; sys.executable is in the parent. In dev (running launch.py
    directly) we fall back to the repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def internal_dir() -> Path:
    """Where bundled data files live."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def wire_bundled_ghostscript() -> None:
    """Prepend bundled gs to PATH and alias gswin64c -> gs if needed."""
    gs_bin = internal_dir() / "gs" / "bin"
    if not gs_bin.is_dir():
        return  # dev mode or no bundled gs — fall through to system PATH

    os.environ["PATH"] = f"{gs_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    # Windows ghostscript installer ships gswin64c.exe; backend code looks for
    # `gs`. If only the windows binary is present, drop a sibling alias.
    gs_alias = gs_bin / "gs.exe"
    gs_win = gs_bin / "gswin64c.exe"
    if gs_win.exists() and not gs_alias.exists():
        try:
            import shutil

            shutil.copyfile(gs_win, gs_alias)
        except OSError:
            pass  # non-fatal; shutil.which("gs") will still miss but we tried


def wire_vendored_config() -> None:
    """Point settings at the vendored estimator CSV inside the bundle."""
    csv = internal_dir() / "data" / "config.v1.csv"
    if csv.exists():
        os.environ.setdefault("PRESS_ESTIMATOR_CONFIG_CSV", str(csv))


def wire_settings_paths() -> None:
    """Override path-shaped settings so they land on the bundle, not the
    PyInstaller temp dir or a sibling-repo path that doesn't exist on Windows.

    settings.py reads each field from PRESS_<UPPERCASE_NAME> via pydantic-
    settings, so these env vars override the class-level defaults.
    """
    if not getattr(sys, "frozen", False):
        return

    inside = internal_dir()
    outside = bundle_root()

    # repo_root drives STATIC_DIR in main.py — point at the bundle so
    # frontend/dist resolves correctly.
    os.environ.setdefault("PRESS_REPO_ROOT", str(inside))
    os.environ.setdefault("PRESS_ICC_DIR", str(inside / "icc"))

    # Job history must live OUTSIDE _internal so it survives bundle updates.
    # Default lands next to the exe in a writable data/ folder.
    jobs_dir = outside / "data" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PRESS_JOBS_DIR", str(jobs_dir))


def open_browser_when_ready(url: str, timeout_s: int = 10) -> None:
    """Poll /api/health, open the browser once it answers."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as r:
                if r.status == 200:
                    webbrowser.open(url)
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.3)
    # Timed out — open anyway so the user sees a connection error and can debug.
    webbrowser.open(url)


def main() -> None:
    wire_bundled_ghostscript()
    wire_vendored_config()
    wire_settings_paths()

    # Import AFTER env vars are set so settings.py picks them up.
    import uvicorn

    from backend.settings import settings

    # Single-user, single-machine. CLAUDE.md rule 4: localhost only.
    # Override with PRESS_BIND_HOST=0.0.0.0 in a .env next to the exe if you
    # ever need LAN access from other shop computers.
    host = os.environ.get("PRESS_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("PRESS_BIND_PORT", str(settings.bind_port)))
    browser_url = f"http://localhost:{port}"

    server_thread = threading.Thread(
        target=lambda: uvicorn.run(
            "backend.main:app",
            host=host,
            port=port,
            reload=False,
            log_level="info",
        ),
        daemon=True,
    )
    server_thread.start()

    open_browser_when_ready(browser_url)

    # Keep the foreground alive — closing the console window terminates uvicorn.
    try:
        server_thread.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
