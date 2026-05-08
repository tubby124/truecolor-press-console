"""Scanner inbox — passive consumer of files dropped by the C3070's Scan-to-SMB.

The press's touchscreen is dead but its physical scanner buttons + the
PageScope web admin still work. We don't drive the scan; we just watch a
folder on the operator's Mac/PC where the press deposits TIFF/PDF/JPG output.

Inbox lifecycle:
  1. Press scans → file lands in `scanner_inbox_dir()`
  2. Frontend polls /api/scan/inbox every 5s, shows the file as a tile
  3. Operator clicks "Inspect & print" → import_scan() moves it into
     settings.jobs_dir/_inspect/ where the existing /api/inspect pipeline
     picks it up
  4. Operator clicks "Dismiss" → dismiss_scan() moves it to inbox/_dismissed/
     (recoverable for 30 days, then purged like jobs)

Single-user, localhost-only. No network share auth here — that's between the
press and the OS file-sharing layer. We just read the directory.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .settings import settings

# Print-ready file types we know how to inspect. Anything else is shown but
# tagged "trash" so the operator can clear it without confusion.
PRINTABLE_EXTS = {".pdf", ".jpg", ".jpeg", ".tiff", ".tif", ".png"}

# Defensive cap so a runaway scanner can't blow up the UI list.
MAX_INBOX_ENTRIES = 25

# Filename safety: only allow names that look like real scanner output.
# C3070 names are typically SCAN0001.PDF / SKMBT_C3070...pdf — alnum + dot/dash/underscore.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._\- ]+$")


def scanner_inbox_dir() -> Path:
    """Where the press drops scans. Configurable via PRESS_SCANNER_INBOX env var.

    Default: ~/Documents/PressConsole/scans/. Auto-created. The matching SMB
    share on the operator's Mac/PC should expose this same folder; see
    docs/SCANNER-SETUP.md for the OS-side configuration.
    """
    raw = os.environ.get("PRESS_SCANNER_INBOX", "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = Path.home() / "Documents" / "PressConsole" / "scans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dismissed_dir() -> Path:
    d = scanner_inbox_dir() / "_dismissed"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(filename: str) -> str:
    """Reject anything with path traversal or weird chars before touching disk."""
    safe = Path(filename).name  # strips any leading dirs
    if not safe or safe.startswith(".") or safe.startswith("_"):
        raise ValueError(f"Invalid filename: {filename!r}")
    if not _SAFE_NAME_RE.match(safe):
        raise ValueError(f"Filename has unsafe characters: {filename!r}")
    return safe


def _suggested_workflow(ext: str) -> str:
    """One of inspect | print | trash. Today inspect/trash; 'print' reserved
    for future fast-path (e.g. previously-imported files)."""
    if ext.lower() in PRINTABLE_EXTS:
        return "inspect"
    return "trash"


def list_inbox() -> list[dict]:
    """Recently scanned files, newest first. Skips hidden + underscore-prefixed
    dirs (so _dismissed/ doesn't show up). Capped at MAX_INBOX_ENTRIES."""
    inbox = scanner_inbox_dir()
    entries: list[tuple[float, dict]] = []
    for p in inbox.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith(".") or p.name.startswith("_"):
            continue
        try:
            stat = p.stat()
        except OSError:
            continue
        ext = p.suffix.lower()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        entries.append((
            stat.st_mtime,
            {
                "filename": p.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified_at": modified,
                "suggested_workflow": _suggested_workflow(ext),
                "import_url": "/api/scan/import",
            },
        ))
    entries.sort(key=lambda x: x[0], reverse=True)
    return [e[1] for e in entries[:MAX_INBOX_ENTRIES]]


def import_scan(filename: str) -> Path:
    """Move the named file from the inbox to settings.jobs_dir/_inspect/.

    Returns the destination path. Raises FileNotFoundError if the source is
    gone (rare race: operator deleted between poll and click) and ValueError
    on filename-traversal attempts.
    """
    safe = _safe_filename(filename)
    src = scanner_inbox_dir() / safe
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Scan {safe!r} no longer in inbox")

    dest_dir = settings.jobs_dir / "_inspect"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe

    # If a same-named file already exists in _inspect (operator imported the
    # same scan twice, or the press wrote a fresh file with the same name),
    # tag the new one with a timestamp so neither gets clobbered.
    if dest.exists():
        stem = Path(safe).stem
        suffix = Path(safe).suffix
        ts = datetime.now().strftime("%H%M%S")
        dest = dest_dir / f"{stem}__{ts}{suffix}"

    shutil.move(str(src), str(dest))
    return dest


def dismiss_scan(filename: str) -> None:
    """Move to _dismissed/ rather than deleting — operator can recover for 30d."""
    safe = _safe_filename(filename)
    src = scanner_inbox_dir() / safe
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"Scan {safe!r} no longer in inbox")

    dest = _dismissed_dir() / safe
    if dest.exists():
        stem = Path(safe).stem
        suffix = Path(safe).suffix
        ts = datetime.now().strftime("%H%M%S")
        dest = _dismissed_dir() / f"{stem}__{ts}{suffix}"
    shutil.move(str(src), str(dest))


def purge_old_dismissed(days: int | None = None) -> dict[str, int]:
    """Delete dismissed scans older than `days` (default: settings.purge_jobs_after_days).

    Mirrors backend.jobs.purge_old_jobs so we can call from the same lifespan
    hook. days=0 disables. Returns a count summary.
    """
    cutoff_days = settings.purge_jobs_after_days if days is None else days
    if cutoff_days <= 0:
        return {"checked": 0, "purged": 0, "skipped": 0}

    cutoff = datetime.now().timestamp() - cutoff_days * 86400
    d = _dismissed_dir()
    checked = purged = skipped = 0
    for p in d.iterdir():
        if not p.is_file():
            continue
        checked += 1
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                purged += 1
        except OSError:
            skipped += 1
    return {"checked": checked, "purged": purged, "skipped": skipped}


# ───────────────────────── SMB setup helper text ─────────────────────────


def setup_instructions_markdown(
    *,
    laptop_ip: str | None = None,
    share_name: str = "PressConsoleScans",
    share_user: str = "shop-mac",
    share_path_hint: str | None = None,
) -> str:
    """Markdown-formatted, paste-ready instructions for configuring the C3070's
    Scan-to-SMB destination via PageScope (http://172.16.1.149).

    Placeholders are filled in with sane defaults if the caller doesn't supply
    a laptop IP / credentials. Hasan can copy the template into the press's
    web admin and only fill in the password.
    """
    ip = laptop_ip or "<LAPTOP_IP — e.g. 172.16.1.50>"
    inbox = share_path_hint or str(scanner_inbox_dir())
    return f"""# C3070 Scan-to-SMB Setup

The C3070's touchscreen is dead, but the **physical scan button** on top of
the scanner unit still triggers a scan, and **PageScope** (the press's web
admin at http://{settings.printer_host}) still lets us configure where scans
go.

## What you'll do
1. Make sure the operator laptop is sharing the inbox folder over SMB
   (see `docs/SCANNER-SETUP.md` — Mac File Sharing or Windows Sharing).
2. Add the laptop as an "Address Book" SMB destination in PageScope.
3. Press the physical Scan button → pick the destination → file lands in
   the laptop inbox → this app shows it under "New scan from press".

## In PageScope (http://{settings.printer_host})

Sign in as **admin** (default password `12345678` unless your shop changed it).

Navigate:

> **Store Address → Address Book → New Registration → SMB**

Fill in:

| Field          | Value |
| -------------- | ----- |
| Name           | `Press Console (Mac)` |
| Host Address   | `{ip}` |
| File Path      | `{share_name}` |
| User ID        | `{share_user}` |
| Password       | `••••••••` |

Save. Then **press the physical Scan button** on the press's scanner unit
(top right) → choose **Press Console (Mac)** from the destination list → tap
green **Start**.

## Inbox folder on this laptop

Files land here:

```
{inbox}
```

You can override the path by setting `PRESS_SCANNER_INBOX=/some/other/path`
before launching the console.

## Verify

- Place a test page on the scanner glass.
- Press **Scan** → pick "Press Console (Mac)" → **Start**.
- Within 5 seconds, "New scan from press" should appear in the console UI.

## If nothing shows up

- Check the inbox folder exists and is writable: `ls -la "{inbox}"`
- Check the laptop firewall allows **SMB on port 445**.
- Check the press's PageScope log: **Job → Communication Log** — failed SMB
  authentication shows there.
- See `docs/SCANNER-SETUP.md` for OS-specific File Sharing setup.
"""
