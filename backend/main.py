"""FastAPI app — single-page drag-drop press console.

Public:
  GET  /                       login or app shell
  POST /login                  password gate (default qwerty123)
  POST /logout                 clear session

Auth-gated /api/* surface used by the React frontend:
  GET  /api/health             public-ish health + safe_print_mode
  GET  /api/me                 current user
  GET  /api/presets            imposition layouts
  GET  /api/stocks             paper catalog
  GET  /api/rates              click rates from estimator CSV
  GET  /api/printer            PJL probe of the press
  GET  /api/trays              tray-loaded state ({T1..T5})
  PUT  /api/trays/{tray}       set tray contents
  POST /api/inspect            upload PDF, return preflight + auto-detect + cost preview
  POST /api/job                upload PDF, run preflight + impose + spool
  GET  /api/jobs               last 50 jobs (newest first)
  GET  /api/job/{id}           job detail
  GET  /api/job/{id}/imposed.pdf
  GET  /api/job/{id}/thumb.png
  POST /api/job/{id}/reprint   clone a job
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pikepdf
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (
    auth,
    bleed_fix,
    catalog,
    impose,
    inspect as inspector,
    jobs,
    normalize,
    press_state_router,
    printer,
    saved_presets,
    scanner,
    scanner_router,
    settings as settings_mod,
    test_patterns_router,
    thumbs,
    trays,
    updater,
    win_spooler,
)
from .version import __version__
from .settings import settings

logger = logging.getLogger("press-console")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # On startup: purge job dirs older than settings.purge_jobs_after_days.
    # 0 disables; misconfig should not crash boot.
    try:
        result = jobs.purge_old_jobs()
        if result["purged"]:
            logger.info(
                "Purged %d job dir(s) older than %d days (%d checked)",
                result["purged"],
                settings.purge_jobs_after_days,
                result["checked"],
            )
    except Exception as e:  # noqa: BLE001 — never let purge crash boot
        logger.warning("Job purge failed at startup: %s", e)
    # Same boundary for dismissed scans — accumulate slowly, purge alongside jobs.
    try:
        scanner.purge_old_dismissed()
    except Exception as e:  # noqa: BLE001
        logger.warning("Scanner dismissed-purge failed at startup: %s", e)
    yield


app = FastAPI(title="True Color Press Console", version=__version__, lifespan=lifespan)

# Sub-routers — shipped as separate modules so each capability owns its own
# endpoints, types, and integration notes. Mount BEFORE the static-asset mount
# below so /api/* always wins over the SPA shell.
app.include_router(press_state_router.router)
app.include_router(scanner_router.router)
app.include_router(test_patterns_router.router)

STATIC_DIR = settings.repo_root / "frontend" / "dist"
LOGIN_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Press Console — Login</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; background: #0e0e10; color: #f5f5f5;
    display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
  .card { background: #1a1a1d; padding: 40px; border-radius: 12px; min-width: 320px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.4); }
  h1 { margin: 0 0 8px; font-size: 22px; }
  p { color: #888; margin: 0 0 24px; font-size: 13px; }
  input[type=password] { width: 100%; padding: 12px; font-size: 16px; border-radius: 6px;
    border: 1px solid #333; background: #0e0e10; color: #f5f5f5; box-sizing: border-box; }
  button { width: 100%; padding: 12px; margin-top: 12px; font-size: 16px; border-radius: 6px;
    border: 0; background: #4a8cff; color: #fff; cursor: pointer; }
  .err { color: #ff5555; font-size: 13px; margin-top: 8px; min-height: 20px; }
</style></head>
<body><div class="card">
  <h1>True Color Press Console</h1>
  <p>Internal shop access — admin password required.</p>
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="Password" autofocus required />
    <button type="submit">Sign in</button>
  </form>
  <div class="err">{{ERROR}}</div>
</div></body></html>"""


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    try:
        auth.current_user(request)
    except HTTPException:
        return HTMLResponse(LOGIN_HTML.replace("{{ERROR}}", ""))
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>Press Console — frontend not built yet.</h1>"
        "<p>Run <code>cd frontend && npm install && npm run build</code>.</p>"
        "<p>Or use the CLI: <code>python -m backend.cli probe</code></p>"
    )


@app.post("/login")
def do_login(password: str = Form(...)):
    if auth._hash(password) != auth.expected_hash():
        return HTMLResponse(LOGIN_HTML.replace("{{ERROR}}", "Wrong password."), status_code=401)
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    auth.login(password, response)
    return response


@app.post("/logout")
def do_logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    auth.logout(request, response)
    return response


@app.get("/api/health")
def health():
    return {"ok": True, "safe_print_mode": settings.safe_print_mode, "version": app.version}


@app.get("/api/me")
def me(user: str = Depends(auth.current_user)):
    return {"user": user}


@app.get("/api/update/check")
def update_check(user: str = Depends(auth.current_user)):
    """Returns current/latest version + whether an update is available.

    GitHub API is rate-limited (60 req/hr unauthenticated) but we cache for
    5 min, so a polling frontend won't hit it.
    """
    return updater.check()


@app.post("/api/update/apply")
def update_apply(user: str = Depends(auth.current_user)):
    """Download the latest release and trigger the swap-and-relaunch script.

    On success, the server **terminates within ~1.5 seconds**. The response
    flushes first, then a background thread calls os._exit(0). The bundled
    apply-update.cmd waits for the exe to exit, copies the new bundle on top,
    and relaunches.

    Only works in the frozen Windows .exe build. On dev / Mac, returns an
    error and stays running.
    """
    return updater.apply_update()


@app.get("/api/presets")
def list_presets(user: str = Depends(auth.current_user)):
    grid = [
        {
            "key": k,
            "kind": "grid",
            "sheet": l.sheet.name,
            "sheet_in": [l.sheet.width_in, l.sheet.height_in],
            "piece": l.piece.name,
            "piece_in": [l.piece.width_in, l.piece.height_in],
            "cols": l.cols,
            "rows": l.rows,
            "total": l.total_pieces,
            "bleed_in": l.piece.bleed_in,
            "fits": l.fits(),
            "friendly_label": impose.FRIENDLY_PRESET_LABELS.get(k, ""),
        }
        for k, l in impose.PRESETS.items()
    ]
    booklet = [
        {
            "key": k,
            "kind": "booklet",
            "sheet": b.sheet.name,
            "sheet_in": [b.sheet.width_in, b.sheet.height_in],
            "page_in": [b.page_w_in, b.page_h_in],
            "bleed_in": b.bleed_in,
            "trim_after": b.trim_after,
            "fits": b.fits(),
            "friendly_label": b.label,
        }
        for k, b in impose.BOOKLET_PRESETS.items()
    ]
    return grid + booklet


@app.get("/api/stocks")
def list_stocks(user: str = Depends(auth.current_user)):
    # call shop_stocks() each time — picks up edits to ~/.config/press-console/stocks.json
    return [
        {
            "code": s.code,
            "name": s.name,
            "friendly_name": s.friendly_name or s.name,
            "finish": s.finish,
            "weight": s.weight,
            "cost_per_unit": s.cost_per_unit,
            "parent_sheet": s.parent_sheet,
            "default_tray": s.default_tray,
            "tags": list(s.tags),
        }
        for s in catalog.shop_stocks()
    ]


@app.get("/api/rates")
def rates(user: str = Depends(auth.current_user)):
    return settings_mod.click_rates()


@app.get("/api/printer")
def printer_status(user: str = Depends(auth.current_user)):
    return printer.probe_status()


# ───────────────────────── Trays ─────────────────────────


@app.get("/api/trays")
def get_trays(user: str = Depends(auth.current_user)):
    return {"configured": trays.configured(), "trays": trays.load()}


class TrayUpdate(BaseModel):
    stock_code: Optional[str] = None
    paper_size: Optional[str] = None
    level: Optional[str] = None  # "full" | "low" | "empty" | "unknown"


@app.put("/api/trays/{tray}")
def update_tray(tray: str, body: TrayUpdate, user: str = Depends(auth.current_user)):
    try:
        state = trays.update_one(
            tray.upper(),
            stock_code=body.stock_code,
            paper_size=body.paper_size,
            level=body.level,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"configured": True, "trays": state}


# ───────────────────────── Printer queues (Windows finishing) ──────────────


class PrinterQueuesUpdate(BaseModel):
    booklet: Optional[str] = None
    stapled: Optional[str] = None
    punched: Optional[str] = None


@app.get("/api/printer-queues")
def get_printer_queues(user: str = Depends(auth.current_user)):
    return {
        "supported": win_spooler.supported(),
        "kinds": list(win_spooler.FINISHING_KINDS),
        "queues": win_spooler.load_queues(),
        "sumatra_exe": settings.sumatra_exe,
    }


@app.put("/api/printer-queues")
def put_printer_queues(body: PrinterQueuesUpdate, user: str = Depends(auth.current_user)):
    incoming = body.model_dump(exclude_none=False)
    # Merge: only overwrite keys explicitly sent; blank string clears.
    current = win_spooler.load_queues()
    for k, v in incoming.items():
        if v is None:
            continue
        if v == "":
            current.pop(k, None)
        else:
            current[k] = v
    saved = win_spooler.save_queues(current)
    return {"queues": saved, "supported": win_spooler.supported()}


# ───────────────────────── Inspect (the magic moment) ─────────────────────────


@app.post("/api/inspect")
async def inspect_file(
    file: UploadFile = File(...),
    quantity_guess: int = Form(100),
    user: str = Depends(auth.current_user),
):
    upload_dir = settings.jobs_dir / "_inspect"
    upload_dir.mkdir(parents=True, exist_ok=True)
    artwork = upload_dir / file.filename
    with artwork.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result, _notes = inspector.inspect_any(artwork, quantity_guess=quantity_guess)
    except normalize.UnsupportedInput as e:
        raise HTTPException(415, e.friendly)
    except normalize.NormalizeError as e:
        raise HTTPException(400, str(e))

    payload = inspector.to_dict(result)
    payload["upload_path"] = str(artwork)
    return payload


# ───────────────────────── Bleed auto-fix ─────────────────────────


class BleedFixBody(BaseModel):
    inspect_filename: str
    target_bleed_in: float = 0.125


@app.post("/api/bleed-fix")
def bleed_fix_endpoint(body: BleedFixBody, user: str = Depends(auth.current_user)):
    """Trim-extend the inspected PDF to reach `target_bleed_in` and re-run preflight.

    The fixed PDF is written next to the inspected one as `<stem>__bleedfix.pdf`
    and replaces the original on disk so the existing /api/preview + /api/job
    pipeline picks it up automatically. Returns the new preflight findings so
    the frontend can refresh the InspectCard without a re-upload.
    """
    src_pdf = _resolve_inspected_pdf(body.inspect_filename)
    try:
        fixed_path, grew_in = bleed_fix.fix_bleed(src_pdf, target_bleed_in=body.target_bleed_in)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except bleed_fix.BleedNoContentError as e:
        # 422: the design ends at the trim line — extending MediaBox would just
        # hide white slivers. Frontend shows a "re-export with bleed" toast.
        raise HTTPException(
            status_code=422,
            detail={"error": "design-ends-at-cut-line", "message": str(e)},
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Couldn't extend the bleed: {e}")

    # Replace the inspected PDF in place so downstream calls (preview, job)
    # use the fixed version with no extra plumbing.
    if fixed_path != src_pdf:
        shutil.copyfile(fixed_path, src_pdf)
        try:
            fixed_path.unlink()
        except OSError:
            pass

    after = bleed_fix.report_after_fix(src_pdf, body.target_bleed_in)
    after["bleed_added_in"] = grew_in
    return after


# ───────────────────────── Pre-commit preview ─────────────────────────


_PREVIEW_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def _resolve_inspected_pdf(filename: str) -> Path:
    """Map an inspect filename back to the PDF on disk for re-imposition.

    The /api/inspect route writes the original to settings.jobs_dir/_inspect/
    and the normalized PDF to .../_inspect/normalized/<stem>.pdf. Prefer the
    normalized PDF (so PSD/PNG/etc inputs work); fall back to the original if
    it's already a PDF.
    """
    safe = Path(filename).name  # strip any path traversal
    if not safe or safe.startswith("."):
        raise HTTPException(400, "Invalid filename")
    base = settings.jobs_dir / "_inspect"
    candidates = [
        base / "normalized" / (Path(safe).stem + ".pdf"),
        base / safe,
    ]
    for c in candidates:
        if c.exists() and c.suffix.lower() == ".pdf":
            return c
    raise HTTPException(404, f"Inspected PDF not found for '{safe}'. Re-drop the file.")


@app.post("/api/preview")
async def preview_imposed(
    inspect_filename: str = Form(...),
    preset_key: str = Form(...),
    stock_code: str = Form(...),
    quantity: int = Form(...),
    sides: int = Form(1),
    user: str = Depends(auth.current_user),
):
    """Render the imposed sheet PDF + cost preview without creating a job.

    Same imposition path as /api/job (crop marks, reg marks, fold guides), so
    what you see here is exactly what spools. Cached on disk by hash of
    (filename, preset, sides) — qty/stock affect cost, not the imposed PDF.
    """
    is_booklet = impose.is_booklet_preset(preset_key)
    if not is_booklet and preset_key not in impose.PRESETS:
        raise HTTPException(400, f"Unknown preset: {preset_key}")
    stock = catalog.by_code(stock_code)
    if stock is None:
        raise HTTPException(400, f"Unknown stock: {stock_code}")

    src_pdf = _resolve_inspected_pdf(inspect_filename)

    preview_dir = settings.jobs_dir / "_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_id = hashlib.sha1(f"{src_pdf.name}-{preset_key}-{sides}-{quantity}".encode()).hexdigest()[:12]
    out_pdf = preview_dir / f"{preview_id}.pdf"

    if is_booklet:
        booklet_preset = impose.BOOKLET_PRESETS[preset_key]
        if not booklet_preset.fits():
            raise HTTPException(400, f"Booklet preset {preset_key} doesn't fit on its parent sheet")
        with pikepdf.open(str(src_pdf)) as p:
            page_count = len(p.pages)
        sheets = impose.booklet_sheets_needed(page_count, quantity)
        breakdown = jobs.cost_breakdown(stock, sheets, 2)  # booklets are always duplex

        if not out_pdf.exists() or out_pdf.stat().st_mtime < src_pdf.stat().st_mtime:
            impose.impose_booklet(
                src_pdf,
                preset=booklet_preset,
                output_pdf=out_pdf,
                quantity=quantity,
            )
            thumb = preview_dir / f"{preview_id}.png"
            if thumb.exists():
                try:
                    thumb.unlink()
                except OSError:
                    pass
    else:
        layout = impose.PRESETS[preset_key]
        if not layout.fits():
            raise HTTPException(400, f"Layout {preset_key} doesn't fit on its parent sheet")
        sheets = impose.sheets_needed(quantity, layout)
        breakdown = jobs.cost_breakdown(stock, sheets, sides)

        if not out_pdf.exists() or out_pdf.stat().st_mtime < src_pdf.stat().st_mtime:
            fold_piece_key = impose.FOLD_PRESET_MAP.get(preset_key)
            fold_guides = impose.FOLD_GUIDES.get(fold_piece_key) if fold_piece_key else None
            impose.impose_grid(
                src_pdf,
                layout=layout,
                output_pdf=out_pdf,
                sides=sides,
                add_crop_marks=fold_piece_key is None,
                add_reg_marks=fold_piece_key is None,
                fold_guides=fold_guides,
            )
            thumb = preview_dir / f"{preview_id}.png"
            if thumb.exists():
                try:
                    thumb.unlink()
                except OSError:
                    pass

    return {
        "preview_id": preview_id,
        "preview_url": f"/api/preview/{preview_id}.pdf",
        "thumb_url": f"/api/preview/{preview_id}/thumb.png",
        "sheets": sheets,
        "paper_cost": breakdown["paper"],
        "click_cost": breakdown["click"],
        "total_cost": breakdown["total"],
    }


@app.get("/api/preview/{preview_id}.pdf")
def get_preview_pdf(preview_id: str, user: str = Depends(auth.current_user)):
    if not _PREVIEW_ID_RE.match(preview_id):
        raise HTTPException(400, "Invalid preview id")
    pdf = settings.jobs_dir / "_preview" / f"{preview_id}.pdf"
    if not pdf.exists():
        raise HTTPException(404, "preview not found")
    return FileResponse(pdf, media_type="application/pdf")


@app.get("/api/preview/{preview_id}/thumb.png")
def get_preview_thumb(preview_id: str, user: str = Depends(auth.current_user)):
    if not _PREVIEW_ID_RE.match(preview_id):
        raise HTTPException(400, "Invalid preview id")
    pdf = settings.jobs_dir / "_preview" / f"{preview_id}.pdf"
    if not pdf.exists():
        raise HTTPException(404, "preview not found")
    out = settings.jobs_dir / "_preview" / f"{preview_id}.png"
    try:
        thumbs.render_thumb(pdf, out)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"thumbnail render failed: {e}")
    return FileResponse(out, media_type="image/png")


# ───────────────────────── Jobs ─────────────────────────


@app.post("/api/job")
async def submit_job(
    file: UploadFile = File(...),
    workflow: str = Form(...),
    preset_key: str = Form(...),
    stock_code: str = Form(...),
    quantity: int = Form(...),
    sides: int = Form(1),
    user: str = Depends(auth.current_user),
):
    stock = catalog.by_code(stock_code)
    if stock is None:
        raise HTTPException(400, f"Unknown stock code: {stock_code}")
    if preset_key not in impose.PRESETS and not impose.is_booklet_preset(preset_key):
        raise HTTPException(400, f"Unknown preset: {preset_key}")

    # Tray-vs-stock guard: if the operator marked tray contents and none
    # match the requested stock, block the submission with a clear message.
    if trays.configured():
        loaded_tray = trays.find_loaded(stock_code)
        if loaded_tray is None:
            state = trays.load()
            loaded_summary = ", ".join(
                f"{k}={v.get('stock_code') or 'unknown'}"
                for k, v in state.items()
            )
            raise HTTPException(
                409,
                f"No tray currently has '{stock.name}' loaded ({loaded_summary}). "
                "Load it and update the tray status before printing."
            )

    upload_dir = settings.jobs_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    artwork = upload_dir / file.filename
    with artwork.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        norm = normalize.normalize(artwork, out_dir=upload_dir / "normalized")
    except normalize.UnsupportedInput as e:
        raise HTTPException(415, e.friendly)
    except normalize.NormalizeError as e:
        raise HTTPException(400, str(e))

    job = jobs.run_job(
        artwork=norm.pdf_path,
        workflow=workflow,
        preset_key=preset_key,
        stock=stock,
        quantity=quantity,
        sides=sides,
    )
    return JSONResponse(content=json.loads(json.dumps(asdict(job), default=str)))


@app.get("/api/jobs")
def list_jobs(limit: int = 50, user: str = Depends(auth.current_user)):
    if not settings.jobs_dir.exists():
        return []
    rows: list[dict] = []
    for d in settings.jobs_dir.iterdir():
        if not d.is_dir() or d.name.startswith("_") or d.name == "uploads":
            continue
        job_file = d / "job.json"
        if not job_file.exists():
            continue
        try:
            data = json.loads(job_file.read_text())
        except json.JSONDecodeError:
            continue
        rows.append({
            "job_id": data.get("job_id", d.name),
            "workflow": data.get("workflow"),
            "quantity": data.get("quantity"),
            "stock_code": data.get("stock_code"),
            "preset_key": data.get("preset_key"),
            "sheets": data.get("sheets"),
            "total_cost": data.get("total_cost"),
            "status": data.get("status"),
            "created_at": data.get("created_at"),
            "has_thumb": (d / "thumb.png").exists(),
            "has_imposed": (d / "imposed.pdf").exists(),
        })
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]


@app.get("/api/job/{job_id}")
def get_job(job_id: str, user: str = Depends(auth.current_user)):
    job_file = settings.jobs_dir / job_id / "job.json"
    if not job_file.exists():
        raise HTTPException(404, "job not found")
    return json.loads(job_file.read_text())


@app.get("/api/job/{job_id}/imposed.pdf")
def get_imposed_pdf(job_id: str, user: str = Depends(auth.current_user)):
    pdf = settings.jobs_dir / job_id / "imposed.pdf"
    if not pdf.exists():
        raise HTTPException(404, "imposed PDF not yet produced")
    return FileResponse(pdf, media_type="application/pdf")


@app.get("/api/job/{job_id}/thumb.png")
def get_thumb(job_id: str, user: str = Depends(auth.current_user)):
    pdf = settings.jobs_dir / job_id / "imposed.pdf"
    if not pdf.exists():
        raise HTTPException(404, "no imposed PDF for this job")
    out = settings.jobs_dir / job_id / "thumb.png"
    try:
        thumbs.render_thumb(pdf, out)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"thumbnail render failed: {e}")
    return FileResponse(out, media_type="image/png")


@app.get("/api/jobs/audit.csv")
def export_audit_csv(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user: str = Depends(auth.current_user),
):
    """CSV download of every job in the range. Inclusive YYYY-MM-DD bounds.
    Empty params = full history. Sorted oldest -> newest for accounting use.
    """
    csv_text = jobs.export_audit_csv(start=start, end=end)
    fname_parts = ["press-audit"]
    if start:
        fname_parts.append(start)
    if end:
        fname_parts.append(end)
    fname = "-".join(fname_parts) + ".csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/api/admin/purge-old-jobs")
def admin_purge_jobs(
    days: Optional[int] = None,
    user: str = Depends(auth.current_user),
):
    """Manual purge trigger. Defaults to settings.purge_jobs_after_days."""
    return jobs.purge_old_jobs(days=days)


@app.post("/api/job/{job_id}/cancel-spool")
def cancel_spool(job_id: str, user: str = Depends(auth.current_user)):
    """Cancel a just-submitted job within the 5-second post-submit window.

    Cancellable statuses: ``pending``, ``spooled-dry``. Once a job is
    ``sent-live`` we leave the dir in place — the PJL bundle has already been
    pushed and the operator must clear the press's queue at the panel /
    PageScope. Anything else returns 409. Frontend hides the cancel button
    on its own after 5s OR when the status string changes; the 409 is the
    last-line guard.
    """
    job_path = settings.jobs_dir / job_id
    job_file = job_path / "job.json"
    if not job_file.exists():
        raise HTTPException(404, "job not found")
    try:
        data = json.loads(job_file.read_text())
    except (json.JSONDecodeError, OSError):
        raise HTTPException(409, "job state unreadable; cannot cancel safely")

    status = (data.get("status") or "").lower()
    cancellable = {"pending", "spooled-dry"}
    if status not in cancellable:
        raise HTTPException(409, f"job is '{status}'; not cancellable from here")

    try:
        shutil.rmtree(job_path)
    except OSError as e:
        raise HTTPException(500, f"could not remove job dir: {e}")
    return {"job_id": job_id, "cancelled": True, "previous_status": status}


@app.post("/api/job/{job_id}/reprint")
def reprint_job(job_id: str, user: str = Depends(auth.current_user)):
    src = settings.jobs_dir / job_id / "job.json"
    if not src.exists():
        raise HTTPException(404, "original job not found")
    src_data = json.loads(src.read_text())
    artwork = Path(src_data.get("artwork_path", ""))
    if not artwork.exists():
        raise HTTPException(410, "original artwork file no longer on disk")
    stock = catalog.by_code(src_data["stock_code"])
    if stock is None:
        raise HTTPException(400, f"Stock {src_data['stock_code']} no longer in catalog")
    job = jobs.run_job(
        artwork=artwork,
        workflow=src_data["workflow"],
        preset_key=src_data["preset_key"],
        stock=stock,
        quantity=src_data["quantity"],
        sides=src_data.get("sides", 1),
    )
    return JSONResponse(content=json.loads(json.dumps(asdict(job), default=str)))


# ───────────────────────── Saved presets ─────────────────────────


class SavedPresetBody(BaseModel):
    name: str
    workflow: str
    preset_key: str
    stock_code: str
    quantity: int
    sides: int = 1


@app.get("/api/saved-presets")
def list_saved_presets(user: str = Depends(auth.current_user)):
    return saved_presets.load()


@app.post("/api/saved-presets")
def upsert_saved_preset(body: SavedPresetBody, user: str = Depends(auth.current_user)):
    if body.preset_key not in impose.PRESETS and not impose.is_booklet_preset(body.preset_key):
        raise HTTPException(400, f"Unknown preset_key: {body.preset_key}")
    if catalog.by_code(body.stock_code) is None:
        raise HTTPException(400, f"Unknown stock_code: {body.stock_code}")
    try:
        sp = saved_presets.upsert(
            body.name,
            workflow=body.workflow,
            preset_key=body.preset_key,
            stock_code=body.stock_code,
            quantity=body.quantity,
            sides=body.sides,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return asdict(sp)


@app.delete("/api/saved-presets/{name}")
def delete_saved_preset(name: str, user: str = Depends(auth.current_user)):
    ok = saved_presets.delete(name)
    if not ok:
        raise HTTPException(404, f"No saved preset named '{name}'")
    return {"deleted": name}


# ───────────────────────── Multi-file batch ─────────────────────────


@app.post("/api/batch")
async def submit_batch(
    files: list[UploadFile] = File(...),
    workflow: str = Form(...),
    preset_key: str = Form(...),
    stock_code: str = Form(...),
    quantity: int = Form(...),
    sides: int = Form(1),
    user: str = Depends(auth.current_user),
):
    """Apply the same workflow + paper to every file. Returns a list of jobs."""
    stock = catalog.by_code(stock_code)
    if stock is None:
        raise HTTPException(400, f"Unknown stock code: {stock_code}")
    if preset_key not in impose.PRESETS and not impose.is_booklet_preset(preset_key):
        raise HTTPException(400, f"Unknown preset: {preset_key}")

    upload_dir = settings.jobs_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for file in files:
        target = upload_dir / file.filename
        with target.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            norm = normalize.normalize(target, out_dir=upload_dir / "normalized")
        except (normalize.UnsupportedInput, normalize.NormalizeError) as e:
            out.append({"file": file.filename, "error": str(e)})
            continue
        job = jobs.run_job(
            artwork=norm.pdf_path,
            workflow=workflow,
            preset_key=preset_key,
            stock=stock,
            quantity=quantity,
            sides=sides,
        )
        out.append({"file": file.filename, "job": json.loads(json.dumps(asdict(job), default=str))})
    return out


# Static assets: mount LAST so /api/* takes priority.
if STATIC_DIR.exists() and (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.bind_host,
        port=settings.bind_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
