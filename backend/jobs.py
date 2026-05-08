"""Job orchestration — ties together preflight, imposition, and cost.

A "job" is a unit of work: artwork PDF + workflow + quantity → imposed PDF +
cost breakdown + PJL bundle ready for the press.
"""

from __future__ import annotations

import csv
import io
import json
import secrets
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import impose, preflight, printer, trays
from .catalog import Stock, click_cost, paper_cost
from .settings import settings


@dataclass
class Job:
    job_id: str
    workflow: str
    quantity: int
    sides: int
    stock_code: str
    preset_key: str
    artwork_path: str
    imposed_path: str | None = None
    spool_path: str | None = None
    sheets: int = 0
    paper_cost: float = 0.0
    click_cost: float = 0.0
    total_cost: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"
    findings: list[dict] = field(default_factory=list)


def new_job_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def job_dir(job_id: str) -> Path:
    d = settings.jobs_dir / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def cost_breakdown(stock: Stock, sheets: int, sides: int) -> dict[str, float]:
    pc = paper_cost(stock, sheets)
    cc = click_cost(sheets * sides, color=True)
    return {"paper": pc, "click": cc, "total": round(pc + cc, 4)}


def _pdf_page_count(pdf_path: Path) -> int:
    """Count pages in an already-normalized PDF. Used for booklet sheet math."""
    import pikepdf  # local import keeps jobs.py boot lean
    with pikepdf.open(str(pdf_path)) as p:
        return len(p.pages)


def run_job(
    *,
    artwork: Path,
    workflow: str,
    preset_key: str,
    stock: Stock,
    quantity: int,
    sides: int = 1,
    expect_bleed_in: float = 0.125,
    job_name: str | None = None,
) -> Job:
    job_id = new_job_id()
    job = Job(
        job_id=job_id,
        workflow=workflow,
        quantity=quantity,
        sides=sides,
        stock_code=stock.code,
        preset_key=preset_key,
        artwork_path=str(artwork),
    )

    is_booklet = impose.is_booklet_preset(preset_key)
    # Booklet expectation: trimmed-from-12x18 needs 0.125" bleed; folded
    # variants don't trim, so the preset declares bleed_in=0 and we don't
    # warn on missing bleed (the design IS sheet-edge-to-sheet-edge).
    if is_booklet:
        booklet_preset = impose.BOOKLET_PRESETS[preset_key]
        expect_bleed_in = booklet_preset.bleed_in

    pf = preflight.run(artwork, expect_bleed_in=expect_bleed_in)
    job.findings = [
        {"severity": f.severity, "code": f.code, "message": f.message, "page": f.page}
        for f in pf.findings
    ]
    if not pf.can_send:
        job.status = "blocked"
        _save_job(job)
        return job

    out_pdf = job_dir(job_id) / "imposed.pdf"

    if is_booklet:
        booklet_preset = impose.BOOKLET_PRESETS[preset_key]
        if not booklet_preset.fits():
            job.status = "blocked"
            job.findings.append({"severity": "block", "code": "layout-fit",
                                 "message": f"Booklet preset {preset_key} doesn't fit on its sheet"})
            _save_job(job)
            return job
        page_count = _pdf_page_count(artwork)
        result = impose.impose_booklet(
            artwork,
            preset=booklet_preset,
            output_pdf=out_pdf,
            quantity=quantity,
        )
        job.sheets = result["total_sheets"]
        sheet_name = booklet_preset.sheet.name
        # Booklets always print duplex regardless of `sides` arg
        duplex = True
        # Side count for cost: 2 (front + back of every sheet)
        sides_for_cost = 2
        # Add a non-blocking note so the operator sees the booklet plan
        job.findings.append({
            "severity": "info",
            "code": "booklet-plan",
            "message": (
                f"Booklet plan: {page_count} source pages → "
                f"{result['sheets_per_copy']} sheet(s) per copy × "
                f"{result['copies']} copies = {result['total_sheets']} sheets. "
                + ("Trim head/foot/face after fold." if booklet_preset.trim_after
                   else "Fold only — no trim.")
            ),
            "page": None,
        })
    else:
        layout = impose.PRESETS[preset_key]
        if not layout.fits():
            job.status = "blocked"
            job.findings.append({"severity": "block", "code": "layout-fit",
                                 "message": f"Layout {preset_key} doesn't fit on its sheet"})
            _save_job(job)
            return job

        job.sheets = impose.sheets_needed(quantity, layout)
        fold_piece_key = impose.FOLD_PRESET_MAP.get(preset_key)
        fold_guides = impose.FOLD_GUIDES.get(fold_piece_key) if fold_piece_key else None
        impose.impose_grid(
            artwork,
            layout=layout,
            output_pdf=out_pdf,
            sides=sides,
            add_crop_marks=fold_piece_key is None,
            add_reg_marks=fold_piece_key is None,
            fold_guides=fold_guides,
        )
        sheet_name = layout.sheet.name
        duplex = (sides == 2)
        sides_for_cost = sides

    job.imposed_path = str(out_pdf)

    breakdown = cost_breakdown(stock, job.sheets, sides_for_cost)
    job.paper_cost = breakdown["paper"]
    job.click_cost = breakdown["click"]
    job.total_cost = breakdown["total"]

    pdl = out_pdf.read_bytes()
    opts = printer.PrintOptions(
        job_name=job_name or f"{workflow}-{job_id}",
        paper=sheet_name,
        media_source=stock.default_tray,
        duplex=duplex,
        copies=1,
    )
    submit_result = printer.submit(pdl, opts, language="POSTSCRIPT")
    job.spool_path = submit_result.get("spool")
    job.status = "spooled-dry" if submit_result["mode"] == "dry" else "sent-live"

    # Tick the sheets-used counter on whichever tray currently holds this stock.
    # Silent no-op if no tray matches (e.g. dry mode without configured trays).
    try:
        trays.record_sheets_used(stock.code, job.sheets)
    except Exception:  # noqa: BLE001 — counter must never block a job
        pass

    _save_job(job)
    return job


def _save_job(job: Job) -> None:
    d = job_dir(job.job_id)
    (d / "job.json").write_text(json.dumps(asdict(job), indent=2))


# ───────────────────────── Retention + audit ─────────────────────────


def _iter_job_dirs() -> list[Path]:
    """All real job directories under settings.jobs_dir.

    Skips uploads/ and any underscore-prefixed scratch dirs.
    """
    if not settings.jobs_dir.exists():
        return []
    out: list[Path] = []
    for d in settings.jobs_dir.iterdir():
        if not d.is_dir() or d.name.startswith("_") or d.name == "uploads":
            continue
        if (d / "job.json").exists():
            out.append(d)
    return out


def purge_old_jobs(days: int | None = None) -> dict[str, int]:
    """Delete job directories older than `days` based on job.json created_at.

    Falls back to filesystem mtime if created_at is missing/malformed. Returns
    a count summary; safe to call on app startup. days=0 disables.
    """
    cutoff_days = settings.purge_jobs_after_days if days is None else days
    if cutoff_days <= 0:
        return {"checked": 0, "purged": 0, "skipped": 0}

    cutoff = datetime.utcnow() - timedelta(days=cutoff_days)
    checked = purged = skipped = 0
    for d in _iter_job_dirs():
        checked += 1
        try:
            data = json.loads((d / "job.json").read_text())
            created = datetime.fromisoformat(data.get("created_at", ""))
        except (json.JSONDecodeError, ValueError, OSError):
            try:
                created = datetime.utcfromtimestamp(d.stat().st_mtime)
            except OSError:
                skipped += 1
                continue
        if created < cutoff:
            try:
                shutil.rmtree(d)
                purged += 1
            except OSError:
                skipped += 1
    return {"checked": checked, "purged": purged, "skipped": skipped}


AUDIT_FIELDS = (
    "created_at",
    "job_id",
    "workflow",
    "preset_key",
    "stock_code",
    "quantity",
    "sides",
    "sheets",
    "paper_cost",
    "click_cost",
    "total_cost",
    "status",
)


def export_audit_csv(start: str | None = None, end: str | None = None) -> str:
    """CSV of every job in the date range. ISO date strings (YYYY-MM-DD)
    inclusive. Empty range = all jobs. Sorted oldest -> newest for accounting.
    """
    rows: list[dict] = []
    for d in _iter_job_dirs():
        try:
            data = json.loads((d / "job.json").read_text())
        except (json.JSONDecodeError, OSError):
            continue
        created = data.get("created_at") or ""
        if start and created and created[:10] < start:
            continue
        if end and created and created[:10] > end:
            continue
        rows.append(data)
    rows.sort(key=lambda r: r.get("created_at") or "")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in AUDIT_FIELDS})
    return buf.getvalue()
