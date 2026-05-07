"""Operator-saved job presets.

Persistent record of "click here to set up Hasan business cards 14pt matte"
or "True Color tri-fold brochure". Stored as a flat JSON list at
~/.config/press-console/presets.json. Names are unique (last save wins on
collision).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

PRESETS_FILE = Path.home() / ".config" / "press-console" / "presets.json"
PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class SavedPreset:
    name: str
    workflow: str
    preset_key: str
    stock_code: str
    quantity: int
    sides: int
    created_at: str
    updated_at: str


def load() -> list[dict]:
    if not PRESETS_FILE.exists():
        return []
    try:
        data = json.loads(PRESETS_FILE.read_text())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_all(items: list[dict]) -> None:
    PRESETS_FILE.write_text(json.dumps(items, indent=2))


def upsert(name: str, *, workflow: str, preset_key: str, stock_code: str,
           quantity: int, sides: int) -> SavedPreset:
    if not name.strip():
        raise ValueError("Preset name cannot be empty")
    items = load()
    now = datetime.utcnow().isoformat()
    existing = next((i for i, p in enumerate(items) if p.get("name") == name), None)
    new_entry = SavedPreset(
        name=name.strip(),
        workflow=workflow,
        preset_key=preset_key,
        stock_code=stock_code,
        quantity=quantity,
        sides=sides,
        created_at=items[existing]["created_at"] if existing is not None else now,
        updated_at=now,
    )
    payload = asdict(new_entry)
    if existing is not None:
        items[existing] = payload
    else:
        items.append(payload)
    _save_all(items)
    return new_entry


def delete(name: str) -> bool:
    items = load()
    new = [p for p in items if p.get("name") != name]
    if len(new) == len(items):
        return False
    _save_all(new)
    return True


def get(name: str) -> dict | None:
    return next((p for p in load() if p.get("name") == name), None)
