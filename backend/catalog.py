"""Stock catalog — paper stocks the C3070 can run.

Press paper costs are NOT in `materials.v1.csv` (that's signage materials —
vinyl / coroplast / ACP — priced per square foot). Press parent-sheet costs
come from supplier invoices and are tracked here. To let the shop adjust
without redeploying, we overlay an optional JSON at
`~/.config/press-console/stocks.json` on top of the hardcoded defaults below.

Click rates (color/b&w) ARE sourced from `config.v1.csv` — see settings.py.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from pathlib import Path

from .settings import settings

CATALOG_OVERRIDE = Path.home() / ".config" / "press-console" / "stocks.json"
CATALOG_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Stock:
    code: str
    name: str
    finish: str
    weight: str
    cost_per_unit: float
    parent_sheet: str
    tags: tuple[str, ...]
    default_tray: str = "AUTO"
    default_paper_size: str = "P12X18"


_DEFAULT_STOCKS: tuple[Stock, ...] = (
    Stock(
        code="14pt-cs-gloss",
        name="14pt Gloss Cover (Pacesetter)",
        finish="gloss",
        weight="14pt / 130# cover",
        cost_per_unit=0.336,
        parent_sheet="18x12",
        tags=("business card", "postcard", "card stock"),
        default_tray="TRAY2",
        default_paper_size="P12X18",
    ),
    Stock(
        code="80lb-gloss-text",
        name="80lb Gloss Text (Pacesetter)",
        finish="gloss",
        weight="80lb text / 118gsm",
        cost_per_unit=0.110,
        parent_sheet="12x18",
        tags=("flyer", "brochure", "tri-fold", "bi-fold"),
        default_tray="TRAY3",
        default_paper_size="P12X18",
    ),
    Stock(
        code="100lb-gloss-text",
        name="100lb Gloss Text (premium)",
        finish="gloss",
        weight="100lb text / 148gsm",
        cost_per_unit=0.150,
        parent_sheet="12x18",
        tags=("premium brochure", "premium flyer", "poster"),
        default_tray="TRAY4",
        default_paper_size="P12X18",
    ),
    Stock(
        code="24lb-bond",
        name="24lb Bond White",
        finish="matte",
        weight="24lb bond / 90gsm",
        cost_per_unit=0.020,
        parent_sheet="letter",
        tags=("multi-page document", "letterhead", "draft"),
        default_tray="TRAY1",
        default_paper_size="LETTER",
    ),
)


def _load_overrides() -> dict[str, dict]:
    if not CATALOG_OVERRIDE.exists():
        return {}
    try:
        data = json.loads(CATALOG_OVERRIDE.read_text())
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, list):
        return {}
    return {row["code"]: row for row in data if isinstance(row, dict) and "code" in row}


def shop_stocks() -> tuple[Stock, ...]:
    """Return active stock catalog: defaults overlaid with any operator overrides."""
    overrides = _load_overrides()
    out: list[Stock] = []
    for s in _DEFAULT_STOCKS:
        ov = overrides.get(s.code)
        if ov:
            out.append(replace(
                s,
                name=ov.get("name", s.name),
                finish=ov.get("finish", s.finish),
                weight=ov.get("weight", s.weight),
                cost_per_unit=float(ov.get("cost_per_unit", s.cost_per_unit)),
                parent_sheet=ov.get("parent_sheet", s.parent_sheet),
                default_tray=ov.get("default_tray", s.default_tray),
                default_paper_size=ov.get("default_paper_size", s.default_paper_size),
                tags=tuple(ov.get("tags", list(s.tags))),
            ))
        else:
            out.append(s)
    # Allow new stocks added via override that aren't in defaults
    for code, ov in overrides.items():
        if not any(s.code == code for s in out):
            try:
                out.append(Stock(
                    code=ov["code"],
                    name=ov["name"],
                    finish=ov.get("finish", "matte"),
                    weight=ov.get("weight", ""),
                    cost_per_unit=float(ov.get("cost_per_unit", 0.0)),
                    parent_sheet=ov.get("parent_sheet", "letter"),
                    tags=tuple(ov.get("tags", [])),
                    default_tray=ov.get("default_tray", "AUTO"),
                    default_paper_size=ov.get("default_paper_size", "LETTER"),
                ))
            except (KeyError, ValueError, TypeError):
                continue
    return tuple(out)


# Backwards-compat alias used by main.py and tests.
SHOP_STOCKS = shop_stocks()


def by_code(code: str) -> Stock | None:
    return next((s for s in shop_stocks() if s.code == code), None)


def materials_loaded() -> bool:
    return settings.estimator_config_csv.exists()


def estimator_paper_costs() -> dict[str, float]:
    """Read live per-sheet costs from truecolor-estimator/data/tables/materials.v1.csv."""
    materials = settings.estimator_config_csv.parent / "materials.v1.csv"
    out: dict[str, float] = {}
    if not materials.exists():
        return out
    with materials.open() as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith(("#", "//")):
                continue
            if len(row) < 8:
                continue
            code = row[0].strip()
            try:
                cost = float(row[6])
            except (ValueError, IndexError):
                continue
            out[code] = cost
    return out


def click_cost(sheets: int, color: bool = True) -> float:
    from .settings import click_rates

    rate_key = "color" if color else "bw"
    return round(sheets * click_rates()[rate_key], 4)


def paper_cost(stock: Stock, sheets: int) -> float:
    return round(sheets * stock.cost_per_unit, 4)
