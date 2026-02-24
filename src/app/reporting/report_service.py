"""Report service — generates PDF reports from validation findings."""
from __future__ import annotations

import logging
from datetime import datetime

from src.app.domain.models import Finding, Severity, ValidationRun
from src.app.storage.file_repo import report_path

logger = logging.getLogger(__name__)


def generate_pdf_report(validation_id: str, run: ValidationRun, findings: list[Finding]) -> str:
    try:
        from fpdf import FPDF
    except ImportError:
        logger.warning("fpdf2 not installed — skipping PDF generation")
        return ""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ArchScan Validation Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Validation ID: {validation_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Project ID: {run.project_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Revision ID: {run.revision_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"RuleSet ID: {run.ruleset_id}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Status: {run.status.value}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Generated: {datetime.utcnow().isoformat()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Summary ────────────────────────────────────────────────────────
    errors = sum(1 for f in findings if f.severity == Severity.ERROR)
    warnings = sum(1 for f in findings if f.severity == Severity.WARNING)
    infos = sum(1 for f in findings if f.severity == Severity.INFO)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total findings: {len(findings)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  Errors: {errors}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  Warnings: {warnings}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"  Info: {infos}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Findings detail ────────────────────────────────────────────────
    if findings:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Findings Detail", new_x="LMARGIN", new_y="NEXT")

        for i, finding in enumerate(findings, 1):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            severity_label = finding.severity.value.upper()
            pdf.cell(0, 6, f"#{i} [{severity_label}] {finding.rule_ref}", new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 9)
            _multi_cell_safe(pdf, f"Message: {finding.message}")
            _multi_cell_safe(pdf, f"Formula: {finding.computation_trace.formula}")
            _multi_cell_safe(pdf, f"Inputs: {finding.computation_trace.inputs}")
            _multi_cell_safe(pdf, f"Result: {finding.computation_trace.result}")
            if finding.computation_trace.tolerance_applied:
                _multi_cell_safe(pdf, f"Tolerance: {finding.computation_trace.tolerance_applied}")
            _multi_cell_safe(pdf, f"Source hashes: {', '.join(finding.source_hashes)}")
            _multi_cell_safe(pdf, f"Fact IDs: {', '.join(finding.input_facts)}")

    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 8, "No findings - all checks passed.", new_x="LMARGIN", new_y="NEXT")

    out_path = report_path(validation_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    logger.info("PDF report written to %s", out_path)
    return str(out_path)


def _multi_cell_safe(pdf, text: str):
    """Write multi-cell text, replacing characters that might fail in latin-1."""
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 5, safe)
