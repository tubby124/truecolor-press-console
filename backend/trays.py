"""Tray state — operator-marked record of what's loaded in each press tray.

The C3070's PJL/SNMP doesn't expose paper-type-loaded per tray, so we keep
our own state file at ~/.config/press-console/trays.json. The operator marks
what they loaded; the UI shows it; the print path checks the loaded stock
matches the requested job stock before committing.

There are 5 trays on this press: T1, T2, T3, T4, T5.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

TRAY_FILE = Path.home() / ".config" / "press-console" / "trays.json"
TRAY_FILE.parent.mkdir(parents=True, exist_ok=True)
TRAY_KEYS = ("T1", "T2", "T3", "T4", "T5")


def _default_state() -> dict:
    return {
        tray: {
            "stock_code": None,
            "paper_size": None,
            "level": "unknown",
            "updated_at": None,
            "sheets_used": 0,
        }
        for tray in TRAY_KEYS
    }


_TRAY_FIELDS = ("stock_code", "paper_size", "level", "updated_at", "sheets_used")


def load() -> dict:
    if not TRAY_FILE.exists():
        return _default_state()
    try:
        data = json.loads(TRAY_FILE.read_text())
    except json.JSONDecodeError:
        return _default_state()
    state = _default_state()
    for k in TRAY_KEYS:
        if k in data and isinstance(data[k], dict):
            state[k].update({
                key: data[k].get(key) for key in _TRAY_FIELDS
                if key in data[k]
            })
            # Defensive type coerce — older trays.json may have null sheets_used.
            if not isinstance(state[k].get("sheets_used"), int):
                state[k]["sheets_used"] = 0
    return state


def save(state: dict) -> dict:
    TRAY_FILE.write_text(json.dumps(state, indent=2))
    return state


def update_one(tray: str, *, stock_code: str | None, paper_size: str | None,
               level: str | None) -> dict:
    if tray not in TRAY_KEYS:
        raise ValueError(f"Unknown tray: {tray}. Must be one of {TRAY_KEYS}.")
    state = load()
    prior = state[tray]
    # Reset sheets_used when the tray is refilled or the loaded stock changes.
    # "full" = operator just topped it up; different stock = new reel of paper.
    refill = (level == "full") or (prior.get("stock_code") != stock_code)
    state[tray] = {
        "stock_code": stock_code,
        "paper_size": paper_size,
        "level": level or "unknown",
        "updated_at": datetime.utcnow().isoformat(),
        "sheets_used": 0 if refill else int(prior.get("sheets_used") or 0),
    }
    return save(state)


def record_sheets_used(stock_code: str, sheets: int) -> dict | None:
    """Add `sheets` to the sheets_used counter on the tray currently loaded
    with `stock_code`. No-op if no tray matches. Returns the updated state
    or None if unchanged.
    """
    if sheets <= 0 or not stock_code:
        return None
    state = load()
    matched = False
    for tray, info in state.items():
        if info.get("stock_code") == stock_code:
            info["sheets_used"] = int(info.get("sheets_used") or 0) + int(sheets)
            matched = True
    if not matched:
        return None
    return save(state)


def configured() -> bool:
    """Has the operator ever set up trays? Used for first-run wizard."""
    return TRAY_FILE.exists()


def find_loaded(stock_code: str) -> str | None:
    """Return tray key (T1..T5) currently loaded with the given stock, or None."""
    state = load()
    for tray, info in state.items():
        if info.get("stock_code") == stock_code:
            return tray
    return None
