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
    friendly_name: str = ""  # operator-facing label; falls back to `name` if empty


# NOTE on cost_per_unit values:
# These are 2025 ESTIMATED Saskatchewan wholesale per-parent-sheet costs based
# on Spicers / Unisource / pacesetter-grade pricing for production digital
# papers. They ground the cost panel within ±20% pending Hasan's actual
# supplier invoices. Stocks with higher uncertainty carry the
# `_cost_unverified` tag — the cost panel uses that to flag the row.
#
# tray distribution philosophy:
#   T1 = letter / multi-page docs (bond, light text)
#   T2 = 14pt covers (most-printed business card stock)
#   T3 = mid-weight gloss / silk text (flyer / brochure runs)
#   T4 = heavy text / premium covers (poster + premium BC)
#   T5 = uncoated + specialty / synthetic (least-rotated)
#
_DEFAULT_STOCKS: tuple[Stock, ...] = (
    # ── Bond / copy ───────────────────────────────────────────────────────
    Stock(
        code="24lb-bond",
        name="24lb Bond White",
        friendly_name="Plain copy paper",
        finish="matte",
        weight="24lb bond / 90gsm",
        cost_per_unit=0.020,
        parent_sheet="letter",
        tags=("multi-page document", "letterhead", "draft"),
        default_tray="TRAY1",
        default_paper_size="LETTER",
    ),
    Stock(
        code="60lb-offset-text",
        name="60lb Offset Opaque Text White",
        friendly_name="Light multi-page paper (letterheads, manuals)",
        finish="uncoated",
        weight="60lb text / 89gsm",
        cost_per_unit=0.025,
        parent_sheet="letter",
        tags=("letterhead", "multi-page document", "manual", "_cost_unverified"),
        default_tray="TRAY1",
        default_paper_size="LETTER",
    ),
    Stock(
        code="60lb-bw-text",
        name="60lb Bright White Text (Pacesetter)",
        friendly_name="Cheap flyer paper (large runs)",
        finish="uncoated",
        weight="60lb text / 89gsm",
        cost_per_unit=0.075,
        parent_sheet="12x18",
        tags=("flyer", "large run", "budget", "_cost_unverified"),
        default_tray="TRAY3",
        default_paper_size="P12X18",
    ),
    # ── Text stocks (flyers / brochures) ─────────────────────────────────
    Stock(
        code="80lb-gloss-text",
        name="80lb Gloss Text (Pacesetter)",
        friendly_name="Glossy flyer / brochure paper (medium)",
        finish="gloss",
        weight="80lb text / 118gsm",
        cost_per_unit=0.110,
        parent_sheet="12x18",
        tags=("flyer", "brochure", "tri-fold", "bi-fold"),
        default_tray="TRAY3",
        default_paper_size="P12X18",
    ),
    Stock(
        code="80lb-silk-text",
        name="80lb Silk Text (Pacesetter)",
        friendly_name="Soft-matte flyer / brochure paper (medium)",
        finish="silk",
        weight="80lb text / 118gsm",
        cost_per_unit=0.120,
        parent_sheet="12x18",
        tags=("flyer", "brochure", "tri-fold", "soft finish", "_cost_unverified"),
        default_tray="TRAY3",
        default_paper_size="P12X18",
    ),
    Stock(
        code="100lb-gloss-text",
        name="100lb Gloss Text (premium)",
        friendly_name="Premium glossy poster paper (heavy)",
        finish="gloss",
        weight="100lb text / 148gsm",
        cost_per_unit=0.150,
        parent_sheet="12x18",
        tags=("premium brochure", "premium flyer", "poster"),
        default_tray="TRAY4",
        default_paper_size="P12X18",
    ),
    Stock(
        code="100lb-uncoated-text",
        name="100lb Uncoated Text (premium)",
        friendly_name="Premium soft brochure paper (no shine)",
        finish="uncoated",
        weight="100lb text / 148gsm",
        cost_per_unit=0.165,
        parent_sheet="12x18",
        tags=("premium brochure", "uncoated", "soft finish", "_cost_unverified"),
        default_tray="TRAY4",
        default_paper_size="P12X18",
    ),
    # ── Cover stocks (cards / postcards) ─────────────────────────────────
    Stock(
        code="100lb-cover-uncoated",
        name="100lb Cover Uncoated White",
        friendly_name="Soft uncoated card paper",
        finish="uncoated",
        weight="100lb cover / 270gsm",
        cost_per_unit=0.225,
        parent_sheet="12x18",
        tags=("postcard", "card stock", "uncoated", "writable", "_cost_unverified"),
        default_tray="TRAY5",
        default_paper_size="P12X18",
    ),
    Stock(
        code="14pt-cs-gloss",
        name="14pt Gloss Cover (Pacesetter)",
        friendly_name="Thick glossy business card paper",
        finish="gloss",
        weight="14pt / 130# cover / 350gsm",
        cost_per_unit=0.336,
        parent_sheet="18x12",
        tags=("business card", "postcard", "card stock"),
        default_tray="TRAY2",
        default_paper_size="P12X18",
    ),
    Stock(
        code="14pt-cs-silk",
        name="14pt Silk Cover (Pacesetter)",
        friendly_name="Thick soft-matte business card paper",
        finish="silk",
        weight="14pt / 130# cover / 350gsm",
        cost_per_unit=0.340,
        parent_sheet="18x12",
        tags=("business card", "postcard", "card stock", "soft finish", "_cost_unverified"),
        default_tray="TRAY2",
        default_paper_size="P12X18",
    ),
    Stock(
        code="16pt-cs-gloss",
        name="16pt Gloss Cover (premium)",
        friendly_name="Extra-thick glossy business card paper",
        finish="gloss",
        weight="16pt / 150# cover / 400gsm",
        cost_per_unit=0.420,
        parent_sheet="18x12",
        tags=("premium business card", "postcard", "premium card stock", "_cost_unverified"),
        default_tray="TRAY4",
        default_paper_size="P12X18",
    ),
    Stock(
        code="16pt-cs-silk",
        name="16pt Silk Cover (premium)",
        friendly_name="Extra-thick soft-matte business card paper",
        finish="silk",
        weight="16pt / 150# cover / 400gsm",
        cost_per_unit=0.440,
        parent_sheet="18x12",
        tags=("premium business card", "postcard", "premium card stock", "soft finish", "_cost_unverified"),
        default_tray="TRAY4",
        default_paper_size="P12X18",
    ),
    # ── Specialty / outdoor ──────────────────────────────────────────────
    Stock(
        code="synthetic-yupo-8mil",
        name="Yupo Synthetic 8mil White (waterproof)",
        friendly_name="Waterproof tear-proof plastic paper",
        finish="synthetic",
        weight="8mil / ~150gsm equiv",
        cost_per_unit=1.350,
        parent_sheet="12x18",
        tags=("outdoor", "waterproof", "synthetic", "menu", "yard sign", "specialty",
              "_cost_unverified", "_press_setup_required"),
        default_tray="TRAY5",
        default_paper_size="P12X18",
    ),
    Stock(
        code="vellum-translucent",
        name="29lb Translucent Vellum",
        friendly_name="See-through specialty paper",
        finish="uncoated",
        weight="29lb vellum / 110gsm",
        cost_per_unit=0.350,
        parent_sheet="12x18",
        tags=("specialty", "translucent", "overlay", "wedding", "_cost_unverified"),
        default_tray="TRAY5",
        default_paper_size="P12X18",
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
                friendly_name=ov.get("friendly_name", s.friendly_name),
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
                    friendly_name=ov.get("friendly_name", ""),
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
