"""OTA updater for the Windows .exe build.

Flow:
  1. App polls GitHub Releases for `tubby124/truecolor-press-console`.
  2. If `latest > current`, frontend shows a banner.
  3. User clicks "Download & install".
  4. Backend downloads the zip asset to `data/update_staging/`, extracts.
  5. Backend writes `data/apply-update.cmd` and spawns it detached.
  6. The .cmd waits for the running .exe to exit (TASKLIST poll), xcopies
     the new bundle on top of the install directory, relaunches the .exe,
     and deletes itself.
  7. Backend calls `os._exit(0)` so the .cmd can take over.

Dev mode (running launch.py directly, not frozen) refuses to apply — there's
no .exe to swap and the source tree is the source of truth. The check
endpoint still works for testing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .version import __github_repo__, __version__

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
RELEASE_CACHE_TTL_S = 300  # 5 min — we don't need to hammer GitHub
UPDATE_USER_AGENT = f"truecolor-press-console/{__version__}"

_release_cache: dict[str, tuple[float, dict]] = {}


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str            # "v0.3.1"
    version: str        # "0.3.1" (tag minus leading v)
    name: str
    notes: str
    zip_url: str        # asset download URL
    zip_size: int
    published_at: str


# ───────────────────────── Version comparison ─────────────────────────


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse `vX.Y.Z` or `X.Y.Z` into a tuple. Pre-release suffixes ignored."""
    s = v.lstrip("vV").split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []
    for piece in s.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    return _parse_version(remote) > _parse_version(local)


# ───────────────────────── GitHub Releases query ─────────────────────────


def _fetch_latest_release_raw() -> dict | None:
    """Hit the GitHub Releases API. Returns raw response dict or None on error."""
    url = f"{GITHUB_API}/repos/{__github_repo__}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": UPDATE_USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            if r.status != 200:
                log.warning("GitHub releases API returned status %s", r.status)
                return None
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        log.info("update check failed: %s", e)
        return None


def _release_from_raw(raw: dict) -> ReleaseInfo | None:
    """Pull the Windows zip asset out of the release payload."""
    tag = raw.get("tag_name") or ""
    if not tag:
        return None
    assets = raw.get("assets") or []
    zip_asset = next(
        (a for a in assets if isinstance(a, dict)
         and (a.get("name") or "").lower().endswith(".zip")),
        None,
    )
    if zip_asset is None:
        return None
    return ReleaseInfo(
        tag=tag,
        version=tag.lstrip("vV"),
        name=raw.get("name") or tag,
        notes=raw.get("body") or "",
        zip_url=zip_asset.get("browser_download_url", ""),
        zip_size=int(zip_asset.get("size") or 0),
        published_at=raw.get("published_at") or "",
    )


def latest_release(force: bool = False) -> ReleaseInfo | None:
    """Cached fetch — repeated /api/update/check calls share the result."""
    cache_key = __github_repo__
    now = time.time()
    if not force:
        hit = _release_cache.get(cache_key)
        if hit and (now - hit[0]) < RELEASE_CACHE_TTL_S:
            cached_release = _release_from_raw(hit[1])
            if cached_release is not None:
                return cached_release

    raw = _fetch_latest_release_raw()
    if raw is None:
        return None
    _release_cache[cache_key] = (now, raw)
    return _release_from_raw(raw)


def check() -> dict:
    """Public payload for /api/update/check.

    Returns current version, latest version (or None on network error), and
    whether an update is available. Frontend gates the banner on
    `update_available && supports_apply`.
    """
    rel = latest_release()
    return {
        "current": __version__,
        "latest": rel.version if rel else None,
        "tag": rel.tag if rel else None,
        "name": rel.name if rel else None,
        "notes": rel.notes if rel else None,
        "zip_url": rel.zip_url if rel else None,
        "zip_size": rel.zip_size if rel else 0,
        "published_at": rel.published_at if rel else None,
        "update_available": bool(rel and is_newer(rel.version, __version__)),
        "supports_apply": _supports_apply(),
        "platform": sys.platform,
        "frozen": bool(getattr(sys, "frozen", False)),
    }


# ───────────────────────── Apply path (Windows-only) ─────────────────────────


def _supports_apply() -> bool:
    """Auto-apply only works on Windows + frozen .exe build.

    On Mac dev or unfrozen Python, there's no `.exe` to swap and the source
    tree is authoritative — pulling git is the right update path there.
    """
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    """Folder containing TrueColorPress.exe at runtime.

    Mirrors `build/launch.py:bundle_root` — duplicated here so backend code
    doesn't depend on the launcher.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _staging_root() -> Path:
    """data/update_staging/ next to the .exe — survives the running process."""
    p = _bundle_root() / "data" / "update_staging"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _download(url: str, dest: Path, expected_size: int = 0) -> int:
    """Stream-download `url` to `dest`. Returns bytes written. Cleans up on error."""
    req = urllib.request.Request(url, headers={"User-Agent": UPDATE_USER_AGENT})
    written = 0
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(req, timeout=60) as r, tmp.open("wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
        if expected_size and written != expected_size:
            log.warning("download size mismatch: got %d, expected %d", written, expected_size)
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return written


def _extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    """Extract the bundle zip. Returns the inner `TrueColorPress/` folder."""
    if dest_dir.exists():
        # Clean previous staged extract — partial leftovers would confuse xcopy
        import shutil
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    # The zip contains TrueColorPress/ at the top level (dist/ root).
    inner = dest_dir / "TrueColorPress"
    if not inner.is_dir():
        # Fallback: pick the first directory in the extracted root
        candidates = [p for p in dest_dir.iterdir() if p.is_dir()]
        if not candidates:
            raise RuntimeError("Update zip didn't contain a top-level folder")
        inner = candidates[0]
    return inner


def _write_apply_script(staged_bundle: Path, install_dir: Path) -> Path:
    """Write apply-update.cmd. Waits for TrueColorPress.exe to exit, xcopies
    the staged bundle onto the install dir, relaunches, deletes itself.
    """
    script = _bundle_root() / "data" / "apply-update.cmd"
    log_path = _bundle_root() / "data" / "logs" / "update.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    body = f"""@echo off
setlocal enableextensions
set "STAGED={staged_bundle}"
set "INSTALL={install_dir}"
set "LOG={log_path}"

echo ============================================================ >> "%LOG%"
echo %DATE% %TIME% apply-update starting                          >> "%LOG%"
echo staged=%STAGED%                                               >> "%LOG%"
echo install=%INSTALL%                                             >> "%LOG%"

echo Waiting for TrueColorPress.exe to exit...
:wait
tasklist /FI "IMAGENAME eq TrueColorPress.exe" 2>nul | find /I "TrueColorPress.exe" >nul
if not errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait
)

echo %DATE% %TIME% process exited; copying files                   >> "%LOG%"
xcopy /E /Y /I /Q "%STAGED%\\*" "%INSTALL%\\" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo %DATE% %TIME% xcopy failed errorlevel %ERRORLEVEL%          >> "%LOG%"
  echo Update failed. See %LOG% for details.
  pause
  exit /b 1
)

echo %DATE% %TIME% relaunching TrueColorPress.exe                  >> "%LOG%"
start "" "%INSTALL%\\TrueColorPress.exe"

echo %DATE% %TIME% apply-update complete                           >> "%LOG%"
del "%~f0"
"""
    script.write_text(body, encoding="ascii")
    return script


def apply_update() -> dict:
    """Download the latest release, stage it, spawn the apply script, exit.

    This call **terminates the server** on success. The caller must return
    the response BEFORE we exit, so we do the heavy lifting first then
    schedule the exit on a short timer.
    """
    if not _supports_apply():
        return {
            "ok": False,
            "error": (
                "Auto-apply only works in the packaged Windows .exe build. "
                "On dev / Mac, pull from git instead."
            ),
        }

    rel = latest_release(force=True)
    if rel is None:
        return {"ok": False, "error": "Couldn't reach GitHub Releases."}

    if not is_newer(rel.version, __version__):
        return {"ok": False, "error": f"Already on the latest version ({__version__})."}

    if not rel.zip_url:
        return {"ok": False, "error": f"Release {rel.tag} doesn't have a Windows zip asset."}

    staging = _staging_root()
    zip_path = staging / f"TrueColorPress-{rel.tag}.zip"
    extract_dir = staging / "extracted"

    log.info("downloading update %s -> %s", rel.zip_url, zip_path)
    try:
        _download(rel.zip_url, zip_path, expected_size=rel.zip_size)
    except Exception as e:
        log.exception("update download failed")
        return {"ok": False, "error": f"Download failed: {e}"}

    log.info("extracting %s -> %s", zip_path, extract_dir)
    try:
        staged_bundle = _extract_zip(zip_path, extract_dir)
    except Exception as e:
        log.exception("update extract failed")
        return {"ok": False, "error": f"Extract failed: {e}"}

    install_dir = _bundle_root()
    script = _write_apply_script(staged_bundle, install_dir)
    log.info("wrote apply script %s", script)

    # Spawn detached so it survives our exit. CREATE_NEW_PROCESS_GROUP +
    # DETACHED_PROCESS keeps it alive after we die. We need the .cmd to keep
    # running long enough to outlive the parent — that's why it loops on
    # tasklist before doing the swap.
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(script)],
            creationflags=flags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        log.exception("failed to spawn apply script")
        return {"ok": False, "error": f"Couldn't start update script: {e}"}

    # Schedule a short delay before exiting so the HTTP response can flush
    # back to the frontend. Fire-and-forget thread.
    import threading
    def _exit_after_delay() -> None:
        time.sleep(1.5)
        log.info("update: exiting to let apply-update.cmd take over")
        os._exit(0)
    threading.Thread(target=_exit_after_delay, daemon=True, name="updater-exit").start()

    return {
        "ok": True,
        "tag": rel.tag,
        "version": rel.version,
        "staged_bundle": str(staged_bundle),
        "install_dir": str(install_dir),
        "message": (
            f"Update to {rel.tag} downloaded. The app will close in a moment, "
            "swap the new files in, and relaunch automatically."
        ),
    }
