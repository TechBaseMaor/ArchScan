"""Report service — generates PDF reports from validation findings."""
from __future__ import annotations

import logging
from datetime import datetime

from src.app.domain.models import Finding, Severity, ValidationRun
from src.app.storage.repo import report_path
from src.app.i18n import t

logger = logging.getLogger(__name__)


def generate_pdf_report(
    validation_id: str,
    run: ValidationRun,
    findings: list[Finding],
    locale: str = "en",
) -> str:
    try:
        from fpdf import FPDF
    except ImportError:
        logger.warning("fpdf2 not installed — skipping PDF generation")
        return ""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    _cell_safe(pdf, 0, 10, t("report.title", locale), align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)
    _cell_safe(pdf, 0, 6, f"{t('report.validation_id', locale)}: {validation_id}")
    _cell_safe(pdf, 0, 6, f"{t('report.project_id', locale)}: {run.project_id}")
    _cell_safe(pdf, 0, 6, f"{t('report.revision_id', locale)}: {run.revision_id}")
    _cell_safe(pdf, 0, 6, f"{t('report.ruleset_id', locale)}: {run.ruleset_id}")
    _cell_safe(pdf, 0, 6, f"{t('report.status', locale)}: {run.status.value}")
    _cell_safe(pdf, 0, 6, f"{t('report.generated', locale)}: {datetime.utcnow().isoformat()}")
    pdf.ln(5)

    # ── Summary ────────────────────────────────────────────────────────
    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    infos = sum(1 for f in findings if f.severity == Severity.INFO)

    pdf.set_font("Helvetica", "B", 12)
    _cell_safe(pdf, 0, 8, t("report.summary", locale))
    pdf.set_font("Helvetica", "", 10)
    _cell_safe(pdf, 0, 6, f"{t('report.total_findings', locale)}: {len(findings)}")
    _cell_safe(pdf, 0, 6, f"  {t('report.errors', locale)}: {errors}")
    _cell_safe(pdf, 0, 6, f"  {t('report.warnings', locale)}: {warnings}")
    _cell_safe(pdf, 0, 6, f"  {t('report.info', locale)}: {infos}")
    pdf.ln(5)

    # ── Findings detail ────────────────────────────────────────────────
    if findings:
        pdf.set_font("Helvetica", "B", 12)
        _cell_safe(pdf, 0, 8, t("report.findings_detail", locale))

        for i, finding in enumerate(findings, 1):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            severity_label = finding.severity.value.upper()
            _cell_safe(pdf, 0, 6, f"#{i} [{severity_label}] {finding.rule_ref}")

            pdf.set_font("Helvetica", "", 9)
            _multi_cell_safe(pdf, f"{t('report.message', locale)}: {finding.message}")
            _multi_cell_safe(pdf, f"{t('report.formula', locale)}: {finding.computation_trace.formula}")
            _multi_cell_safe(pdf, f"{t('report.inputs', locale)}: {finding.computation_trace.inputs}")
            _multi_cell_safe(pdf, f"{t('report.result', locale)}: {finding.computation_trace.result}")
            if finding.computation_trace.tolerance_applied:
                _multi_cell_safe(pdf, f"{t('report.tolerance', locale)}: {finding.computation_trace.tolerance_applied}")
            _multi_cell_safe(pdf, f"{t('report.source_hashes', locale)}: {', '.join(finding.source_hashes)}")
            _multi_cell_safe(pdf, f"{t('report.fact_ids', locale)}: {', '.join(finding.input_facts)}")

    else:
        pdf.set_font("Helvetica", "I", 10)
        _cell_safe(pdf, 0, 8, t("report.no_findings", locale))

    out_path = report_path(validation_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    logger.info("PDF report written to %s", out_path)
    return str(out_path)


def _cell_safe(pdf, w, h, text: str, align: str = ""):
    """Write a single-line cell, sanitizing non-latin-1 characters."""
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    if align:
        pdf.cell(w, h, safe, new_x="LMARGIN", new_y="NEXT", align=align)
    else:
        pdf.cell(w, h, safe, new_x="LMARGIN", new_y="NEXT")


def _multi_cell_safe(pdf, text: str):
    """Write multi-cell text, replacing characters that might fail in latin-1."""
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 5, safe)
