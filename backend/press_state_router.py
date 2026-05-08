"""FastAPI router for live press-state polling.

Two endpoints, both auth-gated:

  GET /api/press/state           — composite state, served from the 15s cache
                                   when fresh.
  GET /api/press/state/refresh   — bypasses the cache (still writes a fresh
                                   entry back into it).

Wiring is intentionally external to ``backend/main.py`` — see
``backend/press_state_INTEGRATION.md`` for the two-line edit.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from . import auth, press_state
from .settings import settings

router = APIRouter(prefix="/api/press", tags=["press"])


@router.get("/state")
def get_press_state(user: str = Depends(auth.current_user)) -> dict:
    return press_state.composite_state(settings.printer_host)


@router.get("/state/refresh")
def get_press_state_fresh(user: str = Depends(auth.current_user)) -> dict:
    press_state.invalidate_cache()
    return press_state.composite_state(settings.printer_host, force=True)
