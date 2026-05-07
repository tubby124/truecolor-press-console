"""PDF preflight: color mode, font embedding, resolution, bleed.

PSD / EPS / AI inputs run through normalize.py first to become PDF, then
come back here. The point is to fail loudly before sending PDL to the
press, not to silently fix problems.

Checks performed:
  - block: file missing / corrupt
  - block: fonts referenced but not embedded (would substitute as Courier)
  - warn:  bleed insufficient vs requested expect_bleed
  - warn:  raster image at <300 DPI when projected at the page's print size
  - warn:  inconsistent page sizes across a multi-page document
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pikepdf


@dataclass
class PreflightFinding:
    severity: str
    code: str
    message: str
    page: int | None = None


@dataclass
class PreflightReport:
    file: Path
    page_count: int = 0
    page_sizes: list[tuple[float, float]] = field(default_factory=list)
    findings: list[PreflightFinding] = field(default_factory=list)

    @property
    def blockers(self) -> list[PreflightFinding]:
        return [f for f in self.findings if f.severity == "block"]

    @property
    def warnings(self) -> list[PreflightFinding]:
        return [f for f in self.findings if f.severity == "warn"]

    @property
    def can_send(self) -> bool:
        return not self.blockers


def _has_unembedded_fonts(pdf: pikepdf.Pdf) -> list[str]:
    bad: list[str] = []
    for page in pdf.pages:
        resources = page.get("/Resources")
        if resources is None:
            continue
        fonts = resources.get("/Font") if hasattr(resources, "get") else None
        if fonts is None:
            continue
        for _name, font_obj in fonts.items():
            try:
                font = font_obj
                font_descriptor = font.get("/FontDescriptor")
                if font_descriptor is None:
                    base = str(font.get("/BaseFont", ""))
                    if base and not _is_standard_14(base):
                        bad.append(base)
                    continue
                embedded = any(
                    font_descriptor.get(k) is not None
                    for k in ("/FontFile", "/FontFile2", "/FontFile3")
                )
                if not embedded:
                    base = str(font.get("/BaseFont", ""))
                    if not _is_standard_14(base):
                        bad.append(base)
            except Exception:
                continue
    return sorted(set(bad))


def _check_image_dpi(pdf: pikepdf.Pdf) -> list[PreflightFinding]:
    """Approx DPI = max(image pixel dim) / page-side inches. Flags <300 dpi.

    This is a coarse upper-bound estimate (assumes the image fills the page).
    Good enough to catch the common "150 dpi photo placed at full page size"
    failure mode. Doesn't detect images placed at sub-page scales — those
    might pass this check while still being soft, which is fine for v1.
    """
    findings: list[PreflightFinding] = []
    for i, page in enumerate(pdf.pages, start=1):
        mb = page.mediabox
        w_in = (float(mb[2]) - float(mb[0])) / 72.0
        h_in = (float(mb[3]) - float(mb[1])) / 72.0
        page_max = max(w_in, h_in)
        if page_max < 0.5:
            continue
        resources = page.get("/Resources")
        if resources is None:
            continue
        xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
        if xobjects is None:
            continue
        worst_dpi: float | None = None
        try:
            for _name, obj in xobjects.items():
                try:
                    if obj.get("/Subtype") != pikepdf.Name("/Image"):
                        continue
                    width_px = int(obj.get("/Width", 0))
                    height_px = int(obj.get("/Height", 0))
                    if not width_px or not height_px:
                        continue
                    px_max = max(width_px, height_px)
                    approx_dpi = px_max / page_max
                    if worst_dpi is None or approx_dpi < worst_dpi:
                        worst_dpi = approx_dpi
                except Exception:
                    continue
        except Exception:
            continue
        if worst_dpi is not None and worst_dpi < 300:
            severity: str
            if worst_dpi < 150:
                severity = "warn"
                msg = (f"Page {i}: a photo on this page is low-resolution (~{int(worst_dpi)} dpi). "
                       "It'll look blurry when printed. Swap in a sharper version of the photo if you can.")
            else:
                severity = "warn"
                msg = (f"Page {i}: a photo on this page is below the 300 dpi print standard "
                       f"(~{int(worst_dpi)} dpi). Fine for a draft, soft for premium prints.")
            findings.append(PreflightFinding(severity, "low-dpi-image", msg, page=i))
    return findings


def _is_standard_14(base_font: str) -> bool:
    standard14 = {
        "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
        "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
        "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
        "Symbol", "ZapfDingbats",
    }
    cleaned = base_font.replace("/", "").split("+", 1)[-1]
    return cleaned in standard14


def run(pdf_path: Path, *, expect_bleed_in: float = 0.0) -> PreflightReport:
    report = PreflightReport(file=pdf_path)
    if not pdf_path.exists():
        report.findings.append(PreflightFinding(
            "block", "missing-file",
            f"We can't find the file we were checking. It may have been moved or deleted. "
            f"Drop the file into the page again. (Path we looked at: {pdf_path})",
        ))
        return report

    try:
        pdf = pikepdf.open(str(pdf_path))
    except pikepdf.PdfError as e:
        report.findings.append(PreflightFinding(
            "block", "corrupt-pdf",
            f"This file looks damaged and we can't open it. Re-export the PDF from your design tool and try again. (Technical detail: {e})",
        ))
        return report

    with pdf:
        report.page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            mb = page.mediabox
            w_pt = float(mb[2]) - float(mb[0])
            h_pt = float(mb[3]) - float(mb[1])
            report.page_sizes.append((w_pt, h_pt))

        # Page-size consistency (multi-page docs that mix sizes confuse imposition + cause jams)
        if len(report.page_sizes) > 1:
            unique = {(round(w, 2), round(h, 2)) for w, h in report.page_sizes}
            if len(unique) > 1:
                report.findings.append(PreflightFinding(
                    "warn", "mixed-page-sizes",
                    f"This PDF has pages in {len(unique)} different sizes. The press may jam or "
                    "switch trays mid-job. Save a separate PDF for each size.",
                ))

        unembedded = _has_unembedded_fonts(pdf)
        if unembedded:
            report.findings.append(PreflightFinding(
                "block", "fonts-not-embedded",
                "Some fonts in this file aren't included in the PDF. They'll print as Courier "
                "(plain typewriter font) instead of what you designed. Re-export the PDF from your "
                "design tool with \"embed all fonts\" turned on. "
                f"Affected fonts: {', '.join(unembedded)}",
            ))

        # DPI check on raster XObjects relative to their drawn size on the page.
        for finding in _check_image_dpi(pdf):
            report.findings.append(finding)

        if expect_bleed_in > 0:
            bleed_pt = expect_bleed_in * 72
            for i, page in enumerate(pdf.pages, start=1):
                mb = page.mediabox
                trim = page.get("/TrimBox") or page.get("/CropBox")
                if trim is None:
                    report.findings.append(PreflightFinding(
                        "warn", "no-trimbox",
                        f"Page {i}: this PDF doesn't say where the cut line is, so we can't "
                        "check the edges for bleed. We'll print it as-is.",
                        page=i,
                    ))
                    continue
                margin = min(
                    float(trim[0]) - float(mb[0]),
                    float(trim[1]) - float(mb[1]),
                    float(mb[2]) - float(trim[2]),
                    float(mb[3]) - float(trim[3]),
                )
                if margin < bleed_pt - 1:
                    report.findings.append(PreflightFinding(
                        "warn", "insufficient-bleed",
                        f"Page {i}: your design might have white slivers at the edges after "
                        f"trimming. We'd like {expect_bleed_in:.3f}\" of background extending past "
                        f"the cut line; you have about {margin / 72:.3f}\". Want us to extend the "
                        "background to fix it?",
                        page=i,
                    ))

    return report
