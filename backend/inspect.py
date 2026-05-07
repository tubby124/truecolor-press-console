"""File inspection — preflight + dimension extract + auto-detect workflow.

Used by POST /api/inspect to power the magic moment: drop file, see what we
think it is + cost preview without committing a job. Imposition is NOT run
here. The frontend takes the recommendation, the operator confirms, then we
hit POST /api/job for the real commit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pikepdf

from . import catalog, impose, normalize, preflight
from .settings import click_rates, settings


@dataclass(frozen=True)
class WorkflowRule:
    workflow: str
    label: str
    preset_key: str
    stock_code: str
    expect_bleed_in: float
    notes: str


@dataclass
class InspectResult:
    filename: str
    page_count: int
    width_in: float
    height_in: float
    detected: WorkflowRule | None
    findings: list[dict]
    cost_preview: dict
    sheets_estimate: int
    can_send: bool
    suggested_quantity: int


def _approx(actual: float, target: float, tol: float = 0.05) -> bool:
    return abs(actual - target) <= tol


def auto_detect(width_in: float, height_in: float, page_count: int) -> WorkflowRule | None:
    w, h = sorted([width_in, height_in])  # orient-agnostic
    if _approx(w, 2.0, 0.1) and _approx(h, 3.5, 0.1):
        return WorkflowRule("business_card", "Business Card", "bc_21up_12x18",
                            "14pt-cs-gloss", 0.125,
                            "21-up on 12×18 cardstock, crop marks for Graphic Wizard cutter")
    if _approx(w, 3.0, 0.15) and _approx(h, 4.0, 0.15):
        return WorkflowRule("postcard_3x4", "Postcard 3×4", "pc_3x4_12up_18x12",
                            "14pt-cs-gloss", 0.125, "12-up on 12×18 cardstock")
    if _approx(w, 4.0, 0.15) and _approx(h, 6.0, 0.15):
        return WorkflowRule("postcard_4x6", "Postcard 4×6", "pc_4x6_4up_18x12",
                            "14pt-cs-gloss", 0.125, "4-up on 12×18 cardstock")
    if _approx(w, 5.0, 0.15) and _approx(h, 7.0, 0.15):
        return WorkflowRule("postcard_5x7", "Postcard 5×7", "pc_5x7_4up_18x12",
                            "14pt-cs-gloss", 0.125, "4-up on 12×18 cardstock")
    if _approx(w, 8.5, 0.15) and _approx(h, 11.0, 0.15):
        if page_count == 2:
            return WorkflowRule("halffold_card", "Half-fold Greeting Card", "halffold_1up_letter",
                                "100lb-gloss-text", 0.0,
                                "Print on letter sideways, fold once → 5.5×8.5 card. "
                                "Fold guides drawn as ghost line.")
        return WorkflowRule("flyer_letter", "Letter Flyer", "flyer_1up_letter",
                            "100lb-gloss-text", 0.0,
                            "1-up letter, 100lb gloss premium" if page_count == 1
                            else "Multi-page document, plain print")
    if _approx(w, 11.0, 0.15) and _approx(h, 17.0, 0.15):
        # 11×17 is ambiguous: bi-fold brochure or large poster. Default to
        # bi-fold (more common request); operator switches via tile if poster.
        return WorkflowRule("bifold_brochure", "Bi-fold Brochure (11×17)", "bifold_1up_11x17",
                            "80lb-gloss-text", 0.0,
                            "11×17 sheet, fold once → 8.5×11 4-page brochure. "
                            "Fold guide drawn as ghost line at center. Switch to poster if needed.")
    return None


def inspect_any(src: Path, *, quantity_guess: int = 100) -> tuple[InspectResult, list[str]]:
    """Normalize any supported input (PSD/PNG/JPG/EPS/AI/PDF) to PDF and inspect it.

    Returns (InspectResult, normalize_notes). Raises normalize.UnsupportedInput
    for blocked types (DOCX/PPTX/HTML) so the route can return a 415 with the
    friendly message.
    """
    norm = normalize.normalize(src, out_dir=settings.jobs_dir / "_inspect" / "normalized")
    result = inspect_pdf(norm.pdf_path, quantity_guess=quantity_guess)
    # Surface normalization notes as informational findings so the operator sees them.
    for note in norm.notes:
        result.findings.insert(0, {"severity": "info", "code": "normalize-note",
                                   "message": note, "page": None})
    return result, norm.notes


def inspect_pdf(pdf_path: Path, *, quantity_guess: int = 100) -> InspectResult:
    if not pdf_path.exists():
        return InspectResult(
            filename=pdf_path.name, page_count=0, width_in=0, height_in=0,
            detected=None,
            findings=[{"severity": "block", "code": "missing-file",
                       "message": f"{pdf_path.name} could not be read"}],
            cost_preview={"paper": 0, "click": 0, "total": 0},
            sheets_estimate=0, can_send=False, suggested_quantity=quantity_guess,
        )

    try:
        pdf = pikepdf.open(str(pdf_path))
    except pikepdf.PdfError as e:
        return InspectResult(
            filename=pdf_path.name, page_count=0, width_in=0, height_in=0,
            detected=None,
            findings=[{"severity": "block", "code": "corrupt-pdf",
                       "message": f"PDF could not be parsed: {e}"}],
            cost_preview={"paper": 0, "click": 0, "total": 0},
            sheets_estimate=0, can_send=False, suggested_quantity=quantity_guess,
        )

    with pdf:
        page_count = len(pdf.pages)
        first = pdf.pages[0]
        mb = first.mediabox
        w_pt = float(mb[2]) - float(mb[0])
        h_pt = float(mb[3]) - float(mb[1])
        width_in = round(w_pt / 72.0, 4)
        height_in = round(h_pt / 72.0, 4)

    detected = auto_detect(width_in, height_in, page_count)

    expect_bleed = detected.expect_bleed_in if detected else 0.0
    pf = preflight.run(pdf_path, expect_bleed_in=expect_bleed)
    findings = [
        {"severity": f.severity, "code": f.code, "message": f.message, "page": f.page}
        for f in pf.findings
    ]

    cost_preview = {"paper": 0.0, "click": 0.0, "total": 0.0}
    sheets_estimate = 0
    suggested_quantity = quantity_guess

    if detected:
        layout = impose.PRESETS.get(detected.preset_key)
        stock = catalog.by_code(detected.stock_code)
        if layout and stock:
            if detected.workflow.startswith(("business_card", "postcard")):
                suggested_quantity = max(quantity_guess, 100)
            elif detected.workflow == "flyer_letter":
                suggested_quantity = max(min(quantity_guess, page_count), 1)
            sheets_estimate = impose.sheets_needed(suggested_quantity, layout)
            sides = 2 if page_count >= 2 and detected.workflow == "business_card" else 1
            paper = round(sheets_estimate * stock.cost_per_unit, 4)
            click = round(sheets_estimate * sides * click_rates()["color"], 4)
            cost_preview = {"paper": paper, "click": click,
                            "total": round(paper + click, 4)}

    return InspectResult(
        filename=pdf_path.name,
        page_count=page_count,
        width_in=width_in,
        height_in=height_in,
        detected=detected,
        findings=findings,
        cost_preview=cost_preview,
        sheets_estimate=sheets_estimate,
        can_send=pf.can_send,
        suggested_quantity=suggested_quantity,
    )


def to_dict(result: InspectResult) -> dict:
    d = asdict(result)
    if result.detected is None:
        d["detected"] = None
    return d
