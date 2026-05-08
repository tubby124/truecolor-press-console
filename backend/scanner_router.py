"""Scanner inbox router — exposes the scanner.py module to the React frontend.

Mounted at /api/scan/* by main.py. Auth-gated (auth.current_user) like the
rest of the /api surface.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import auth, inspect as inspector, normalize, scanner
from .settings import settings

router = APIRouter(prefix="/api/scan", tags=["scan"])


class ScanFileBody(BaseModel):
    filename: str


@router.get("/inbox")
def get_inbox(user: str = Depends(auth.current_user)):
    """Newest-first list of files currently in the scanner inbox.

    Returns up to scanner.MAX_INBOX_ENTRIES items. Frontend polls this every
    5s; result is cheap (one stat per file) so polling is fine.
    """
    return {
        "inbox_dir": str(scanner.scanner_inbox_dir()),
        "items": scanner.list_inbox(),
    }


@router.post("/import")
def post_import(body: ScanFileBody, user: str = Depends(auth.current_user)):
    """Move a scan into the _inspect/ pipeline, then return the same shape
    /api/inspect returns so the frontend can drop straight into InspectCard.

    The scan file is moved (not copied) — once imported, it's gone from the
    inbox so the operator doesn't import it twice.
    """
    try:
        dest = scanner.import_scan(body.filename)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Run the same pipeline /api/inspect uses. inspect_any() handles both PDFs
    # and raster scans (TIFF/JPG/PNG) via normalize.normalize.
    try:
        result, _notes = inspector.inspect_any(dest, quantity_guess=100)
    except normalize.UnsupportedInput as e:
        raise HTTPException(415, e.friendly)
    except normalize.NormalizeError as e:
        raise HTTPException(400, str(e))

    payload = inspector.to_dict(result)
    payload["upload_path"] = str(dest)
    payload["source"] = "scanner"
    payload["filename"] = dest.name  # may differ from inbox name on collision
    return payload


@router.post("/dismiss")
def post_dismiss(body: ScanFileBody, user: str = Depends(auth.current_user)):
    """Move a scan to the _dismissed/ subfolder. Auto-purged after 30 days."""
    try:
        scanner.dismiss_scan(body.filename)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"dismissed": body.filename}


@router.get("/file/{filename}")
def get_imported_file(filename: str, user: str = Depends(auth.current_user)):
    """Serve a scan that was just imported into _inspect/.

    The frontend uses this to reconstruct a `File` object for the existing
    InspectCard / submitJob flow (which re-uploads via multipart). Path-
    traversal is blocked by treating filename as a basename only and
    requiring the file to live directly under settings.jobs_dir/_inspect/.
    """
    safe = Path(filename).name
    if not safe or safe.startswith(".") or safe.startswith("_"):
        raise HTTPException(400, "Invalid filename")
    target = settings.jobs_dir / "_inspect" / safe
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"Imported scan {safe!r} not found")
    return FileResponse(target, filename=safe)


@router.get("/setup-instructions")
def get_setup_instructions(user: str = Depends(auth.current_user)):
    """Markdown text the operator can paste into PageScope to wire up
    Scan-to-SMB. Filled with sane defaults; operator only needs to add IP +
    password to make it work."""
    return {
        "markdown": scanner.setup_instructions_markdown(),
        "inbox_dir": str(scanner.scanner_inbox_dir()),
    }
