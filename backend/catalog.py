"""Stock catalog — source-of-truth is `truecolor-estimator/data/tables/materials.v1.csv`.

We don't duplicate the catalog here. We read it at runtime so the press console
stays in sync with the estimator's pricing data (single source of truth for the
shop's actual paper costs and SKU mappings).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .settings import settings


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


SHOP_STOCKS: tuple[Stock, ...] = (
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


def by_code(code: str) -> Stock | None:
    return next((s for s in SHOP_STOCKS if s.code == code), None)


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
