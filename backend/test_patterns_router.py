"""Bundled calibration test patterns — for the Konica tech visit + first prints.

Three vector PDFs ship in the repo at `assets/test-patterns/`:

  - color-blocks-letter            8.5x11, CMYK process colors + tints + ramps
  - registration-target-12x18      12x18, registration target + edge rulers
  - density-bar-letter             8.5x11, K density strip + process columns

Why router-only (vs include in main.py):
  Hasan's CLAUDE.md says "Don't modify backend/main.py directly — write
  test_patterns_INTEGRATION.md". So this file ships, integration is the
  user's two-line edit.

Endpoints (all auth-gated):

  GET  /api/test-patterns                 list available patterns
  GET  /api/test-patterns/{id}/file.pdf   serve the PDF
  POST /api/test-patterns/{id}/print-test kick off a print job

The print-test endpoint is the load-bearing one for the tech visit: it skips
the upload step, copies the bundled pattern PDF into the normal job pipeline,
and runs through the existing impose + spool path. In `SAFE_PRINT_MODE=dry`
it produces a PJL bundle in `tmp/` exactly like a real upload would — perfect
for the supervised first print after C-6753 is cleared.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from . import auth, catalog, impose, jobs
from .settings import settings

router = APIRouter(prefix="/api/test-patterns", tags=["test-patterns"])

ASSETS_DIR = settings.repo_root / "assets" / "test-patterns"


# ─────────────── pattern manifest (id → file + metadata) ────────────────
#
# Each entry tells the frontend:
#   - which paper to load before tapping print
#   - which preset to use (1-up posters/flyers — no imposition, just
#     position the page on the parent sheet so the press has a real PDF
#     dimensioned for its tray)
#   - what the pattern is for, so operators don't have to remember
#
# Recommended presets are chosen so each pattern matches a stocked paper:
#   - color-blocks-letter   -> 100lb gloss cover (poster_1up_letter preset @ letter sheet)
#   - registration-target   -> 80lb gloss cover (poster_1up_11x17 preset on 12x18-friendly stock)
#   - density-bar-letter    -> 100lb gloss text (poster_1up_letter preset)
#
# `recommended_stock` is a stock code that exists in catalog.shop_stocks();
# the frontend can show its friendly name alongside the pattern label.

PATTERNS: dict[str, dict] = {
    "color-blocks-letter": {
        "label": "Color Blocks (Letter)",
        "friendly_label": "Color check — letter, 8.5x11",
        "filename": "color-blocks-letter.pdf",
        "description": (
            "100% C / M / Y / K solids, 50% and 25% tints, plus a 11-step ramp "
            "for each channel. Use after a fuser swap, ICC update, or any time "
            "the press has been cold for hours — looks for color drift channel "
            "by channel. Should print with crisp solids and even ramps with no "
            "banding."
        ),
        "recommended_stock": "100lb-gloss-text",
        "recommended_preset": "poster_1up_letter",
        "sheet": "letter",
    },
    "registration-target-12x18": {
        "label": "Registration Target (12x18)",
        "friendly_label": "Registration check — 12x18",
        "filename": "registration-target-12x18.pdf",
        "description": (
            "Four corner crosshairs, a 4-color center crosshair, and edge "
            "rulers ticked every 0.5 inch. Use to verify plate-to-plate "
            "registration after a transport-belt swap, drum reseat, or any "
            "service work that touches the imaging chain. The CMYK center "
            "cross should land inside the surrounding ring with no visible "
            "channel offset."
        ),
        "recommended_stock": "14pt-cs-gloss",
        "recommended_preset": "poster_1up_11x17",
        "sheet": "12x18",
    },
    "density-bar-letter": {
        "label": "Density Bar (Letter)",
        "friendly_label": "Density check — letter, 8.5x11",
        "filename": "density-bar-letter.pdf",
        "description": (
            "100% K density strip, then four full-coverage process columns, "
            "then a 5-step grayscale ramp from 0 to 100%. Use as a quick "
            "sanity check before a long color run — the 100% K should be "
            "deep and even with no streaks; the grayscale steps should show "
            "five clearly distinct values."
        ),
        "recommended_stock": "100lb-gloss-text",
        "recommended_preset": "poster_1up_letter",
        "sheet": "letter",
    },
}


def _resolve_pattern(pattern_id: str) -> dict:
    if pattern_id not in PATTERNS:
        raise HTTPException(404, f"Unknown test pattern: {pattern_id}")
    meta = PATTERNS[pattern_id]
    pdf = ASSETS_DIR / meta["filename"]
    if not pdf.exists():
        raise HTTPException(
            500,
            f"Pattern PDF missing on disk: {pdf}. Run scripts/generate_test_patterns.py.",
        )
    return {**meta, "_path": pdf}


# ─────────────────────────── routes ──────────────────────────────────


@router.get("")
def list_patterns(user: str = Depends(auth.current_user)) -> list[dict]:
    out: list[dict] = []
    for pid, meta in PATTERNS.items():
        pdf = ASSETS_DIR / meta["filename"]
        size_kb = round(pdf.stat().st_size / 1024, 1) if pdf.exists() else None
        out.append(
            {
                "id": pid,
                "label": meta["label"],
                "friendly_label": meta["friendly_label"],
                "file_size_kb": size_kb,
                "description": meta["description"],
                "recommended_stock": meta["recommended_stock"],
                "recommended_preset": meta["recommended_preset"],
                "sheet": meta["sheet"],
                "available": pdf.exists(),
            }
        )
    return out


@router.get("/{pattern_id}/file.pdf")
def serve_pattern(pattern_id: str, user: str = Depends(auth.current_user)) -> FileResponse:
    meta = _resolve_pattern(pattern_id)
    return FileResponse(meta["_path"], media_type="application/pdf")


@router.post("/{pattern_id}/print-test")
def print_pattern(pattern_id: str, user: str = Depends(auth.current_user)) -> JSONResponse:
    """Run the bundled test pattern PDF through the normal job pipeline.

    No upload — we copy the asset into uploads/ so jobs.run_job sees it as a
    normal source file. Preset + stock come from the pattern's recommended
    pair. The job lives in the same `tmp/jobs/<id>/` shape as any other job
    so it shows up in History.
    """
    meta = _resolve_pattern(pattern_id)

    if meta["recommended_preset"] not in impose.PRESETS:
        raise HTTPException(
            500,
            f"Recommended preset '{meta['recommended_preset']}' missing from impose.PRESETS.",
        )
    stock = catalog.by_code(meta["recommended_stock"])
    if stock is None:
        raise HTTPException(
            500,
            f"Recommended stock '{meta['recommended_stock']}' missing from catalog.",
        )

    # Copy the bundled pattern PDF into uploads/ so it lives next to other
    # job sources (and so jobs.run_job's artwork_path is reachable later for
    # reprint).
    upload_dir = settings.jobs_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    src = meta["_path"]
    dst = upload_dir / f"test-pattern-{pattern_id}.pdf"
    shutil.copyfile(src, dst)

    job = jobs.run_job(
        artwork=dst,
        workflow=f"test_pattern_{pattern_id.replace('-', '_')}",
        preset_key=meta["recommended_preset"],
        stock=stock,
        quantity=1,
        sides=1,
        # Patterns include their own marks; preflight-bleed warning would be
        # a false positive here. Pass 0 so the bleed check is satisfied.
        expect_bleed_in=0.0,
        job_name=f"calibration-{pattern_id}",
    )
    return JSONResponse(content=json.loads(json.dumps(asdict(job), default=str)))
