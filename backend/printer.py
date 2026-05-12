"""PJL / raw 9100 driver for the AccurioPress C3070.

We bypass CUPS and LPR entirely and speak PJL directly over a TCP socket to
port 9100. PJL gives us status queries, named jobs, language switch, tray
selection, duplex, finishing, and output bin in a single header — all
deterministic and inspectable.

`SAFE_PRINT_MODE=dry` is the kill switch. While the printer is in stored
fault state from the voltage event, every send writes the PJL bundle to
disk and never opens the printer socket. See docs/HARDWARE-GATES.md.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .settings import settings

UEL = b"\x1B%-12345X"
DEFAULT_TIMEOUT = 8.0


@dataclass
class PrintOptions:
    job_name: str = "press-console-job"
    paper: str = "LETTER"
    media_source: str = "AUTO"
    duplex: bool = False
    binding: str = "LEFT"
    copies: int = 1
    color_mode: str = "color"
    finish: str = "NONE"
    out_bin: str = "DEFAULT"
    orientation: str = "PORTRAIT"
    extra_pjl: list[str] = field(default_factory=list)


def build_pjl_header(opts: PrintOptions, language: str = "POSTSCRIPT") -> bytes:
    lines = [
        UEL,
        f'@PJL JOB NAME="{opts.job_name}"\r\n'.encode(),
        f"@PJL SET PAPER={opts.paper}\r\n".encode(),
        f"@PJL SET MEDIASOURCE={opts.media_source}\r\n".encode(),
        f"@PJL SET DUPLEX={'ON' if opts.duplex else 'OFF'}\r\n".encode(),
        f"@PJL SET BINDING={opts.binding}\r\n".encode(),
        f"@PJL SET COPIES={opts.copies}\r\n".encode(),
        f"@PJL SET FINISH={opts.finish}\r\n".encode(),
        f"@PJL SET OUTBIN={opts.out_bin}\r\n".encode(),
        f"@PJL SET ORIENTATION={opts.orientation}\r\n".encode(),
    ]
    for extra in opts.extra_pjl:
        lines.append(f"@PJL {extra}\r\n".encode())
    lines.append(f"@PJL ENTER LANGUAGE={language}\r\n".encode())
    return b"".join(lines)


def build_pjl_footer() -> bytes:
    return UEL + b"@PJL EOJ\r\n" + UEL


def assemble_job(pdl_body: bytes, opts: PrintOptions, language: str = "POSTSCRIPT") -> bytes:
    return build_pjl_header(opts, language) + pdl_body + build_pjl_footer()


def write_spool(bundle: bytes, opts: PrintOptions) -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    day_dir = settings.jobs_dir / today
    day_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    out = day_dir / f"{stamp}-{opts.job_name}.spool"
    out.write_bytes(bundle)
    return out


def send_raw_9100(bundle: bytes, host: str | None = None, port: int | None = None,
                  timeout: float = DEFAULT_TIMEOUT) -> None:
    h = host or settings.printer_host
    p = port or settings.printer_raw_port
    with socket.create_connection((h, p), timeout=timeout) as s:
        s.sendall(bundle)
        s.shutdown(socket.SHUT_WR)
        try:
            s.recv(4096)
        except socket.timeout:
            pass


def submit(pdl_body: bytes, opts: PrintOptions, language: str = "POSTSCRIPT") -> dict:
    bundle = assemble_job(pdl_body, opts, language)
    spool = write_spool(bundle, opts)
    if settings.safe_print_mode != "live":
        return {"mode": "dry", "spool": str(spool), "bytes": len(bundle), "sent": False}
    send_raw_9100(bundle)
    return {"mode": "live", "spool": str(spool), "bytes": len(bundle), "sent": True}


def cancel_active_job(host: str | None = None, timeout: float = 5.0) -> dict:
    """Best-effort abort of whatever the press is currently printing.

    Sends ``@PJL JOB CANCEL`` wrapped in UEL escapes. The C3070 may or may not
    honour the cancel on a job that's already half-way through the engine —
    sheets already past the imaging unit will still come out — but the
    pending pages get dropped and the press returns to ready. Always returns
    a dict; never raises (this is a kill switch, callers can't afford it to
    blow up). In dry mode we don't open the socket at all.
    """
    h = host or settings.printer_host
    if settings.safe_print_mode != "live":
        return {"sent": False, "reason": "dry mode — no socket opened"}
    payload = UEL + b"@PJL JOB CANCEL\r\n" + UEL
    try:
        with socket.create_connection((h, settings.printer_raw_port), timeout=timeout) as s:
            s.sendall(payload)
            s.shutdown(socket.SHUT_WR)
        return {"sent": True, "host": h}
    except OSError as e:
        return {"sent": False, "error": str(e), "host": h}


def probe_status(host: str | None = None, timeout: float = 6.0) -> dict:
    """Send a PJL INFO STATUS query and return parsed response. Read-only."""
    h = host or settings.printer_host
    query = UEL + b"@PJL INFO STATUS\r\n@PJL INFO ID\r\n" + UEL
    try:
        with socket.create_connection((h, settings.printer_raw_port), timeout=timeout) as s:
            s.sendall(query)
            s.settimeout(timeout)
            chunks = []
            while True:
                try:
                    data = s.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
                if b"@PJL" in data and len(b"".join(chunks)) > 100:
                    break
        raw = b"".join(chunks).decode("ascii", errors="replace")
    except (OSError, socket.error) as e:
        return {"reachable": False, "error": str(e)}

    parsed: dict[str, str] = {"reachable": True, "raw": raw}
    for line in raw.splitlines():
        line = line.strip()
        if "=" in line:
            key, val = line.split("=", 1)
            parsed[key.strip().lower()] = val.strip().strip('"')
    return parsed
