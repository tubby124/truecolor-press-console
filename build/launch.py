"""PyInstaller entry point for the True Color Press Console Windows build.

Responsibilities:
  1. Resolve the bundle root (works in dev AND under PyInstaller's _MEIPASS).
  2. Wire bundled Ghostscript into PATH so backend/normalize.py + backend/thumbs.py
     find it via shutil.which("gs").
  3. Point PRESS_ESTIMATOR_CONFIG_CSV at the vendored CSV inside the bundle.
  4. Redirect logs to a rotating file in data/logs/ (console is hidden in
     the frozen Windows build, so stdout/stderr go nowhere).
  5. Start uvicorn in a background thread.
  6. On Windows + frozen, run a pystray system-tray icon in the foreground:
     Open dashboard / Open log folder / Start with Windows / Quit.
  7. On first launch, silently install a Startup-folder shortcut so the
     console boots with the PC. Removable from the tray menu.

Stays Mac-runnable for dev — tray + autostart paths are Windows-only and
no-op elsewhere.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

# PyInstaller --windowed (console=False) leaves sys.stdout = sys.stderr = None
# because there's no console attached. Anything that calls .write() or .isatty()
# on these crashes with AttributeError. Critically, uvicorn.config.LOGGING_CONFIG
# instantiates uvicorn.logging.DefaultFormatter which calls sys.stderr.isatty()
# at config-dict load time — that error blew up the v0.2.1 build's server
# thread before any of our own logging could capture it. Patch stdio at module
# import time, before any third-party module gets a chance to touch it.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", buffering=1)
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", buffering=1)

log = logging.getLogger("truecolorpress.launcher")


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


def is_frozen_windows() -> bool:
    return sys.platform == "win32" and getattr(sys, "frozen", False)


def setup_file_logging() -> Path:
    """Route root + uvicorn logs to data/logs/server.log next to the exe.

    Frozen Windows build runs as a GUI subsystem (console=False) — stdout
    and stderr point at nothing, so without a file handler all uvicorn /
    backend log output is lost. Always write to file; in dev we still get
    console too because the root logger keeps its default StreamHandler.
    """
    log_dir = bundle_root() / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "server.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    # uvicorn configures its own loggers on startup — propagate so they
    # reach our file handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).propagate = True
    return log_dir


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


def open_browser_when_ready(url: str, timeout_s: int = 15) -> None:
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


# ───────────────────────── Autostart (Windows) ─────────────────────────

def _startup_shortcut() -> Path | None:
    """Per-user Startup-folder .lnk path, or None on non-Windows."""
    if sys.platform != "win32":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "TrueColorPress.lnk"


def autostart_enabled() -> bool:
    p = _startup_shortcut()
    return p is not None and p.exists()


def set_autostart(enable: bool) -> None:
    """Create or remove the Startup-folder shortcut. PowerShell handles the
    .lnk so we don't need pywin32 in the bundle.
    """
    p = _startup_shortcut()
    if p is None:
        return
    try:
        if enable:
            if p.exists():
                return
            exe = Path(sys.executable).resolve()
            ps = (
                f"$ws = New-Object -ComObject WScript.Shell; "
                f"$s = $ws.CreateShortcut('{p}'); "
                f"$s.TargetPath = '{exe}'; "
                f"$s.WorkingDirectory = '{exe.parent}'; "
                f"$s.WindowStyle = 7; "  # minimized
                f"$s.Save()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                check=False,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            log.info("autostart: created shortcut %s", p)
        else:
            p.unlink(missing_ok=True)
            log.info("autostart: removed shortcut %s", p)
    except Exception:
        log.exception("autostart: failed to %s", "enable" if enable else "disable")


def _first_run_autostart_init() -> None:
    """Silent autostart opt-in on first frozen-Windows launch. Tray menu
    can flip it off afterwards. Marker file means we only do this once;
    if the user disables it later, we won't re-enable.
    """
    if not is_frozen_windows():
        return
    marker_dir = bundle_root() / "data"
    marker = marker_dir / ".autostart_initialized"
    if marker.exists():
        return
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        set_autostart(True)
        marker.touch()
    except Exception:
        log.exception("first-run autostart init failed")


# ───────────────────────── Tray icon (Windows) ─────────────────────────

def _tray_image():
    """Build the tray icon in-memory so we don't need to ship a .ico file.
    True Color blue square with white 'TC' centered.
    """
    from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded blue square
    d.rounded_rectangle(
        [(2, 2), (size - 2, size - 2)],
        radius=12,
        fill=(40, 95, 155, 255),
        outline=(255, 255, 255, 255),
        width=2,
    )
    text = "TC"
    try:
        font = ImageFont.truetype("arialbd.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - 2),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )
    return img


def run_tray_blocking(browser_url: str, log_dir: Path) -> None:
    """Foreground tray loop. Returns when the user picks Quit."""
    import pystray
    from pystray import Menu, MenuItem as Item

    icon = pystray.Icon("truecolor_press", _tray_image(), "True Color Press Console")

    def _open(_icon=None, _item=None) -> None:
        webbrowser.open(browser_url)

    def _open_logs(_icon=None, _item=None) -> None:
        try:
            os.startfile(str(log_dir))  # type: ignore[attr-defined]  # Windows-only
        except Exception:
            webbrowser.open(log_dir.as_uri())

    def _toggle_autostart(_icon=None, _item=None) -> None:
        set_autostart(not autostart_enabled())

    def _quit(_icon=None, _item=None) -> None:
        log.info("tray: quit requested")
        icon.stop()
        # uvicorn lives in a daemon thread — _exit kills it cleanly.
        os._exit(0)

    icon.menu = Menu(
        Item("Open dashboard", _open, default=True),
        Item("Open log folder", _open_logs),
        Item(
            "Start with Windows",
            _toggle_autostart,
            checked=lambda _i: autostart_enabled(),
        ),
        Menu.SEPARATOR,
        Item("Quit", _quit),
    )
    icon.run()


# ───────────────────────── Main ─────────────────────────

def main() -> None:
    wire_bundled_ghostscript()
    wire_vendored_config()
    wire_settings_paths()
    log_dir = setup_file_logging()
    log.info(
        "starting True Color Press Console (frozen=%s, platform=%s)",
        getattr(sys, "frozen", False),
        sys.platform,
    )

    # Import AFTER env vars are set so settings.py picks them up.
    import uvicorn

    from backend.settings import settings

    # Single-user, single-machine. CLAUDE.md rule 4: localhost only.
    # Override with PRESS_BIND_HOST=0.0.0.0 in a .env next to the exe if you
    # ever need LAN access from other shop computers.
    host = os.environ.get("PRESS_BIND_HOST", "127.0.0.1")
    port = int(os.environ.get("PRESS_BIND_PORT", str(settings.bind_port)))
    browser_url = f"http://localhost:{port}"

    def _run_uvicorn() -> None:
        # Catch + log everything. Without this an import error inside
        # backend.main (eg a missing PyInstaller hidden import) kills the
        # daemon thread silently, the browser opens at the 15s health-check
        # timeout, and the user sees a dead port with no visible error.
        try:
            uvicorn.run(
                "backend.main:app",
                host=host,
                port=port,
                reload=False,
                log_level="info",
                # No console attached in the frozen Windows build; ANSI color
                # codes would just clutter the file log.
                use_colors=False,
            )
        except Exception:
            log.exception("uvicorn server thread crashed")
            raise

    server_thread = threading.Thread(
        target=_run_uvicorn,
        daemon=True,
        name="uvicorn",
    )
    server_thread.start()

    # First-run silent autostart opt-in (Windows + frozen only).
    _first_run_autostart_init()

    # Open browser once server's up.
    threading.Thread(
        target=open_browser_when_ready,
        args=(browser_url,),
        daemon=True,
        name="browser-opener",
    ).start()

    # Foreground: tray on Windows-frozen, otherwise just block on the server.
    # PRESS_NO_TRAY=1 forces the headless server-blocking path. Used by the CI
    # boot smoke-test, which runs the frozen .exe on a runner with no
    # interactive desktop / system tray and just needs the server alive to poll.
    no_tray = os.environ.get("PRESS_NO_TRAY") == "1"
    if is_frozen_windows() and not no_tray:
        try:
            run_tray_blocking(browser_url, log_dir)
            return  # Quit picked from tray
        except Exception:
            log.exception("tray init failed; falling back to blocking on server")

    try:
        server_thread.join()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
