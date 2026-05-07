"""PDF preflight: color mode, font embedding, resolution, bleed.

v1 covers PDF only. PSD / EPS / AI inputs run through normalize.py first to
become PDF, then come back here. The point is to fail loudly before sending
PDL to the press, not to silently fix problems.
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
        report.findings.append(PreflightFinding("block", "missing-file", f"{pdf_path} does not exist"))
        return report

    try:
        pdf = pikepdf.open(str(pdf_path))
    except pikepdf.PdfError as e:
        report.findings.append(PreflightFinding("block", "corrupt-pdf", str(e)))
        return report

    with pdf:
        report.page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            mb = page.mediabox
            w_pt = float(mb[2]) - float(mb[0])
            h_pt = float(mb[3]) - float(mb[1])
            report.page_sizes.append((w_pt, h_pt))

        unembedded = _has_unembedded_fonts(pdf)
        if unembedded:
            report.findings.append(PreflightFinding(
                "block", "fonts-not-embedded",
                f"Fonts not embedded — would substitute as Courier on press: {', '.join(unembedded)}",
            ))

        if expect_bleed_in > 0:
            bleed_pt = expect_bleed_in * 72
            for i, page in enumerate(pdf.pages, start=1):
                mb = page.mediabox
                trim = page.get("/TrimBox") or page.get("/CropBox")
                if trim is None:
                    report.findings.append(PreflightFinding(
                        "warn", "no-trimbox",
                        f"Page {i}: no /TrimBox set — cannot verify bleed mathematically",
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
                        f"Page {i}: bleed {margin / 72:.3f}\" < required {expect_bleed_in:.3f}\"",
                        page=i,
                    ))

    return report
