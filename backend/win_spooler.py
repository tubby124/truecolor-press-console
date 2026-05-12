"""Windows print spooler bridge for Konica finisher workflows.

Why this exists:
  The raw PJL/port-9100 path in printer.py can drive the C3070's print
  engine but cannot engage the BM-660 booklet maker, stapler, or hole
  punch — Konica's finishing controls aren't standard PJL keywords. The
  installed Windows print driver knows all the controller-specific
  commands. Cleanest way to reach them programmatically is to shell out
  to SumatraPDF (a free headless PDF printer) targeting a Windows
  printer queue that has the desired finishing preset baked in via the
  driver UI.

Setup on the Windows machine (one-time, per shop):
  1. Install SumatraPDF (default install path is what `settings.sumatra_exe`
     expects).
  2. Add the C3070 printer to Windows multiple times under different
     names, each with a different finishing preset in the driver UI:
       - "C3070 Plain"    — finisher off
       - "C3070 Booklet"  — saddle-stitch + half-fold
       - "C3070 Stapled"  — corner staple
       - "C3070 Punched"  — 3-hole punch
  3. In the press console Settings panel, save those four queue names.

Then this module just picks the right queue per job and lets SumatraPDF
hand the imposed PDF off to the spooler.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .settings import settings

log = logging.getLogger(__name__)

# Finishing workflow kinds → key in the printer-queues.json mapping.
# The frontend tile.key (e.g. "booklet_5.5x8.5_letter") maps to one of these
# via _workflow_kind() so we don't need a row in queues.json per tile.
FINISHING_KINDS = ("booklet", "stapled", "punched")


@dataclass(frozen=True)
class SpoolResult:
    ok: bool
    queue: str
    pdf: str
    error: str | None = None
    stdout: str | None = None


def load_queues() -> dict[str, str]:
    """Read the workflow-kind → printer-queue-name mapping. Returns {} if
    the file doesn't exist or is malformed (UI will surface that)."""
    p = settings.printer_queues_file
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.warning("printer-queues.json unreadable: %s", e)
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if v}


def save_queues(mapping: dict[str, str]) -> dict[str, str]:
    """Persist the workflow-kind → printer-queue-name mapping. Filters out
    empty values so a blank box in the UI = "not configured" not "use empty
    string"."""
    p = settings.printer_queues_file
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: str(v).strip() for k, v in mapping.items() if v and str(v).strip()}
    p.write_text(json.dumps(clean, indent=2))
    return clean


def workflow_kind(workflow_or_preset: str) -> str | None:
    """Map a tile key or preset key to a finishing kind, or None if the
    workflow doesn't need a finisher (plain print path)."""
    s = (workflow_or_preset or "").lower()
    if "booklet" in s:
        return "booklet"
    if "staple" in s or "stapled" in s:
        return "stapled"
    if "punch" in s:
        return "punched"
    return None


def supported() -> bool:
    """Auto-finish is only available on Windows because that's where the
    installed Konica driver lives. On Mac dev there's no spooler path."""
    return sys.platform == "win32"


def _sumatra_path() -> Path | None:
    """Locate SumatraPDF.exe. Returns None if not found — caller surfaces."""
    p = Path(settings.sumatra_exe)
    if p.exists():
        return p
    # Fallback: portable install in same dir as our .exe
    bundled = Path(sys.executable).resolve().parent / "SumatraPDF.exe"
    if bundled.exists():
        return bundled
    return None


def print_via_spooler(pdf_path: Path, queue_name: str, copies: int = 1) -> SpoolResult:
    """Send a PDF to a Windows printer queue via SumatraPDF, blocking until
    SumatraPDF returns. SumatraPDF handles the spooler handoff; the Konica
    driver attached to the queue handles per-job finishing settings.

    Caller is responsible for picking the right queue_name based on workflow
    (booklet → "C3070 Booklet" queue, etc.)."""
    if not supported():
        return SpoolResult(
            ok=False, queue=queue_name, pdf=str(pdf_path),
            error="Windows print spooler is only available on Windows. "
                  "Plain-print jobs work via PJL on any platform; "
                  "finishing jobs need Windows + Konica driver queues.",
        )
    exe = _sumatra_path()
    if exe is None:
        return SpoolResult(
            ok=False, queue=queue_name, pdf=str(pdf_path),
            error=f"SumatraPDF.exe not found at {settings.sumatra_exe}. "
                  "Install SumatraPDF (https://www.sumatrapdfreader.org/) or "
                  "drop SumatraPDF.exe next to TrueColorPress.exe.",
        )
    if not pdf_path.exists():
        return SpoolResult(ok=False, queue=queue_name, pdf=str(pdf_path),
                           error=f"Imposed PDF missing: {pdf_path}")

    # -print-to <name>           — target a specific Windows queue
    # -print-settings "copies=N" — per-job override of copy count
    # -silent                    — no UI prompts; treat any prompt as error
    # -exit-when-done            — quit SumatraPDF after the job is queued
    args = [
        str(exe),
        "-print-to", queue_name,
        "-print-settings", f"copies={int(copies)}",
        "-silent",
        "-exit-when-done",
        str(pdf_path),
    ]
    log.info("spooling %s -> %s (copies=%d)", pdf_path.name, queue_name, copies)
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return SpoolResult(ok=False, queue=queue_name, pdf=str(pdf_path),
                           error="SumatraPDF didn't return within 120s — job may still spool.")
    except OSError as e:
        return SpoolResult(ok=False, queue=queue_name, pdf=str(pdf_path),
                           error=f"Couldn't run SumatraPDF: {e}")

    if proc.returncode != 0:
        return SpoolResult(
            ok=False, queue=queue_name, pdf=str(pdf_path),
            error=f"SumatraPDF exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:400]}",
            stdout=proc.stdout,
        )
    return SpoolResult(ok=True, queue=queue_name, pdf=str(pdf_path), stdout=proc.stdout)


def purge_all_queues() -> dict:
    """Kill switch: drop all pending jobs from every configured Windows queue
    (booklet / stapled / punched) plus the hardcoded "C3070 Plain" fallback.

    PowerShell ``Remove-PrintJob`` is the only stable cmdline way to clear a
    spool — there's no equivalent on Mac because the spooler bridge itself
    doesn't run there. No-op + ``supported: False`` outside Windows.

    Never raises; collects per-queue results in the returned dict so callers
    can surface partial failures without aborting the broader stop sequence.
    """
    if not supported():
        return {"supported": False, "purged": [], "errors": []}
    queue_names = set(load_queues().values())
    queue_names.add("C3070 Plain")
    purged: list[str] = []
    errors: list[str] = []
    for q in sorted(n for n in queue_names if n):
        cmd = (
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"Get-PrintJob -PrinterName '{q}' -ErrorAction SilentlyContinue | Remove-PrintJob",
        )
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0:
                purged.append(q)
            else:
                errors.append(f"{q}: {(proc.stderr or proc.stdout).strip()[:200]}")
        except (OSError, subprocess.TimeoutExpired) as e:
            errors.append(f"{q}: {e}")
    return {"supported": True, "purged": purged, "errors": errors}
