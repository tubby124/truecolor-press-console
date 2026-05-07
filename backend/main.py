"""FastAPI app — single-page drag-drop press console.

Exposes:
  GET  /              login or app shell
  POST /login         password gate (default qwerty123)
  POST /logout        clear session
  GET  /api/health    public health check
  GET  /api/me        current user
  GET  /api/presets   list of imposition presets
  GET  /api/stocks    list of paper stocks
  GET  /api/rates     current click rates
  GET  /api/printer   printer status (PJL probe)
  POST /api/job       upload artwork + run a job
  GET  /api/job/{id}  job detail
  GET  /api/job/{id}/imposed.pdf   download imposed PDF
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, catalog, impose, jobs, printer, settings as settings_mod
from .settings import settings

app = FastAPI(title="True Color Press Console", version="0.1.0")

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
    return {"ok": True, "safe_print_mode": settings.safe_print_mode}


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
        for s in catalog.SHOP_STOCKS
    ]


@app.get("/api/rates")
def rates(user: str = Depends(auth.current_user)):
    return settings_mod.click_rates()


@app.get("/api/printer")
def printer_status(user: str = Depends(auth.current_user)):
    return printer.probe_status()


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

    upload_dir = settings.jobs_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    artwork = upload_dir / file.filename
    with artwork.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    job = jobs.run_job(
        artwork=artwork,
        workflow=workflow,
        preset_key=preset_key,
        stock=stock,
        quantity=quantity,
        sides=sides,
    )
    return JSONResponse(content=json.loads(json.dumps(job.__dict__, default=str)))


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


if STATIC_DIR.exists():
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
