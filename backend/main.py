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

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (
    auth,
    catalog,
    impose,
    inspect as inspector,
    jobs,
    normalize,
    printer,
    saved_presets,
    settings as settings_mod,
    thumbs,
    trays,
)
from .settings import settings

app = FastAPI(title="True Color Press Console", version="0.2.0")

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


@app.get("/api/presets")
def list_presets(user: str = Depends(auth.current_user)):
    return [
        {
            "key": k,
            "sheet": l.sheet.name,
            "sheet_in": [l.sheet.width_in, l.sheet.height_in],
            "piece": l.piece.name,
            "piece_in": [l.piece.width_in, l.piece.height_in],
            "cols": l.cols,
            "rows": l.rows,
            "total": l.total_pieces,
            "bleed_in": l.piece.bleed_in,
            "fits": l.fits(),
        }
        for k, l in impose.PRESETS.items()
    ]


@app.get("/api/stocks")
def list_stocks(user: str = Depends(auth.current_user)):
    # call shop_stocks() each time — picks up edits to ~/.config/press-console/stocks.json
    return [
        {
            "code": s.code,
            "name": s.name,
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
    if preset_key not in impose.PRESETS:
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
    if body.preset_key not in impose.PRESETS:
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
    if preset_key not in impose.PRESETS:
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
