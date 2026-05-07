"""Job orchestration — ties together preflight, imposition, and cost.

A "job" is a unit of work: artwork PDF + workflow + quantity → imposed PDF +
cost breakdown + PJL bundle ready for the press.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from . import impose, preflight, printer
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

    pf = preflight.run(artwork, expect_bleed_in=expect_bleed_in)
    job.findings = [
        {"severity": f.severity, "code": f.code, "message": f.message, "page": f.page}
        for f in pf.findings
    ]
    if not pf.can_send:
        job.status = "blocked"
        _save_job(job)
        return job

    layout = impose.PRESETS[preset_key]
    if not layout.fits():
        job.status = "blocked"
        job.findings.append({"severity": "block", "code": "layout-fit",
                             "message": f"Layout {preset_key} doesn't fit on its sheet"})
        _save_job(job)
        return job

    job.sheets = impose.sheets_needed(quantity, layout)

    out_pdf = job_dir(job_id) / "imposed.pdf"
    impose.impose_grid(artwork, layout=layout, output_pdf=out_pdf, sides=sides)
    job.imposed_path = str(out_pdf)

    breakdown = cost_breakdown(stock, job.sheets, sides)
    job.paper_cost = breakdown["paper"]
    job.click_cost = breakdown["click"]
    job.total_cost = breakdown["total"]

    pdl = out_pdf.read_bytes()
    opts = printer.PrintOptions(
        job_name=job_name or f"{workflow}-{job_id}",
        paper=layout.sheet.name,
        media_source=stock.default_tray,
        duplex=(sides == 2),
        copies=1,
    )
    submit_result = printer.submit(pdl, opts, language="POSTSCRIPT")
    job.spool_path = submit_result.get("spool")
    job.status = "spooled-dry" if submit_result["mode"] == "dry" else "sent-live"

    _save_job(job)
    return job


def _save_job(job: Job) -> None:
    d = job_dir(job.job_id)
    (d / "job.json").write_text(json.dumps(asdict(job), indent=2))
