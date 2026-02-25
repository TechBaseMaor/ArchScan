"""Insights service — builds a client-facing RevisionSummary from extracted facts."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

from src.app.config import settings
from src.app.domain.models import (
    AgreementStatus,
    ComplianceGroup,
    ComplianceReport,
    DocumentCoverage,
    ExtractedFact,
    Finding,
    ReconciliationEntry,
    RevisionSummary,
    RuleSet,
    Severity,
    SourceFile,
    SummaryMetric,
)

logger = logging.getLogger(__name__)

_AREA_CATEGORIES = {"area"}
_HEIGHT_CATEGORIES = {"height"}
_FLOOR_CATEGORIES = {"level", "floor_summary"}
_OPENING_CATEGORIES = {"opening_window", "opening_door"}
_SETBACK_CATEGORIES = {"setback"}
_PARKING_CATEGORIES = {"parking"}
_DWELLING_CATEGORIES = {"dwelling_units"}
_REGULATORY_CATEGORIES = {"regulatory_threshold", "coverage"}


def build_revision_summary(
    project_id: str,
    revision_id: str,
    facts: list[ExtractedFact],
    sources: Optional[list[SourceFile]] = None,
) -> RevisionSummary:
    summary = RevisionSummary(project_id=project_id, revision_id=revision_id)
    summary.total_facts = len(facts)
    summary.sources_used = sorted({f.source_hash for f in facts})

    for fact in facts:
        metric = _fact_to_metric(fact)
        if fact.category in _AREA_CATEGORIES:
            summary.areas.append(metric)
        elif fact.category in _HEIGHT_CATEGORIES:
            summary.heights.append(metric)
        elif fact.category in _FLOOR_CATEGORIES:
            summary.floors.append(metric)
        elif fact.category in _OPENING_CATEGORIES:
            summary.openings.append(metric)
        elif fact.category in _SETBACK_CATEGORIES:
            summary.setbacks.append(metric)
        elif fact.category in _PARKING_CATEGORIES:
            summary.parking.append(metric)
        elif fact.category in _DWELLING_CATEGORIES:
            summary.dwelling_units.append(metric)
        elif fact.category in _REGULATORY_CATEGORIES:
            summary.regulatory_thresholds.append(metric)

    if sources:
        present_types = {s.document_type for s in sources}
        for expected in _EXPECTED_DOC_TYPES:
            if expected not in present_types:
                summary.missing_documents.append(expected)

    summary.reconciliation = _reconcile(facts)
    return summary


def _fact_to_metric(fact: ExtractedFact) -> SummaryMetric:
    source = "ifc" if fact.fact_type.value == "geometric" else "pdf"
    return SummaryMetric(
        label=fact.label,
        value=fact.value,
        unit=fact.unit,
        confidence=fact.confidence,
        source=source,
        raw_source_ref=fact.raw_source_ref,
        fact_ids=[fact.fact_id],
        metadata=fact.metadata,
    )


def _reconcile(facts: list[ExtractedFact]) -> list[ReconciliationEntry]:
    """Compare IFC vs PDF facts for the same category and produce agreement entries."""
    ifc_by_cat: dict[str, list[ExtractedFact]] = {}
    pdf_by_cat: dict[str, list[ExtractedFact]] = {}

    for f in facts:
        bucket = ifc_by_cat if f.fact_type.value == "geometric" else pdf_by_cat
        bucket.setdefault(f.category, []).append(f)

    entries: list[ReconciliationEntry] = []
    all_cats = set(ifc_by_cat) | set(pdf_by_cat)

    for cat in sorted(all_cats):
        ifc_facts = ifc_by_cat.get(cat, [])
        pdf_facts = pdf_by_cat.get(cat, [])

        if ifc_facts and pdf_facts:
            ifc_val = _representative_value(ifc_facts)
            pdf_val = _representative_value(pdf_facts)
            if isinstance(ifc_val, (int, float)) and isinstance(pdf_val, (int, float)):
                agreement, deviation = _compute_agreement(ifc_val, pdf_val, cat)
                entries.append(ReconciliationEntry(
                    category=cat,
                    label=f"{cat} (IFC vs PDF)",
                    ifc_value=ifc_val,
                    pdf_value=pdf_val,
                    chosen_value=ifc_val,
                    unit=ifc_facts[0].unit,
                    agreement=agreement,
                    deviation_pct=deviation,
                ))
            else:
                entries.append(ReconciliationEntry(
                    category=cat,
                    label=f"{cat} (IFC vs PDF)",
                    ifc_value=ifc_val,
                    pdf_value=pdf_val,
                    chosen_value=ifc_val,
                    unit=ifc_facts[0].unit,
                    agreement=AgreementStatus.SINGLE_SOURCE,
                ))
        elif ifc_facts:
            entries.append(ReconciliationEntry(
                category=cat,
                label=f"{cat} (IFC only)",
                ifc_value=_representative_value(ifc_facts),
                chosen_value=_representative_value(ifc_facts),
                unit=ifc_facts[0].unit,
                agreement=AgreementStatus.SINGLE_SOURCE,
            ))
        elif pdf_facts:
            entries.append(ReconciliationEntry(
                category=cat,
                label=f"{cat} (PDF only)",
                pdf_value=_representative_value(pdf_facts),
                chosen_value=_representative_value(pdf_facts),
                unit=pdf_facts[0].unit,
                agreement=AgreementStatus.SINGLE_SOURCE,
            ))

    return entries


def _representative_value(facts: list[ExtractedFact]) -> Any:
    """Pick the highest-confidence numeric value, or first value if non-numeric."""
    numeric = [(f.value, f.confidence) for f in facts if isinstance(f.value, (int, float))]
    if numeric:
        numeric.sort(key=lambda x: x[1], reverse=True)
        return numeric[0][0]
    return facts[0].value


def _compute_agreement(
    ifc_val: float, pdf_val: float, category: str
) -> tuple[AgreementStatus, float]:
    if pdf_val == 0 and ifc_val == 0:
        return AgreementStatus.MATCHED, 0.0
    base = max(abs(ifc_val), abs(pdf_val), 1e-9)
    deviation_pct = abs(ifc_val - pdf_val) / base * 100

    tol = settings.tolerance
    threshold = tol.area_pct if category in _AREA_CATEGORIES else tol.distance_cm

    if deviation_pct <= threshold:
        return AgreementStatus.MATCHED, round(deviation_pct, 2)
    if deviation_pct <= threshold * 5:
        return AgreementStatus.MINOR_DEVIATION, round(deviation_pct, 2)
    return AgreementStatus.MAJOR_DEVIATION, round(deviation_pct, 2)


# ── Grouped compliance reporting ──────────────────────────────────────────

_DISCIPLINE_MAP: dict[str, str] = {
    "setback": "design",
    "height": "design",
    "area": "design",
    "coverage": "design",
    "fence_height": "design",
    "parking": "parking",
    "dwelling_units": "general",
    "floor_summary": "design",
    "text_clause": "general",
    "regulatory_threshold": "general",
    "sheet_info": "general",
    "sheet_dimensions": "general",
}

_EXPECTED_DOC_TYPES = {
    "statutory_plan",
    "spatial_guidelines",
    "building_plan",
    "area_calculation",
    "site_survey",
}


def build_compliance_report(
    validation_id: str,
    project_id: str,
    revision_id: str,
    findings: list[Finding],
    ruleset: Optional[RuleSet] = None,
    sources: Optional[list[SourceFile]] = None,
    facts: Optional[list[ExtractedFact]] = None,
) -> ComplianceReport:
    """Build a grouped compliance report from validation findings."""
    groups_map: dict[tuple[str, str], list[Finding]] = defaultdict(list)

    rule_meta: dict[str, dict[str, Any]] = {}
    if ruleset:
        for rule in ruleset.rules:
            rule_meta[f"{rule.rule_id}:{rule.version}"] = rule.metadata

    for finding in findings:
        meta = rule_meta.get(finding.rule_ref, {})
        layer = meta.get("layer", "general")
        cat = finding.computation_trace.inputs.get("category", "")
        if not cat and finding.input_facts:
            cat = "general"
        discipline = _DISCIPLINE_MAP.get(cat, "general")
        groups_map[(layer, discipline)].append(finding)

    groups: list[ComplianceGroup] = []
    for (layer, discipline), group_findings in sorted(groups_map.items()):
        g = ComplianceGroup(
            layer=layer,
            discipline=discipline,
            findings=group_findings,
            fail_count=sum(1 for f in group_findings if f.severity == Severity.ERROR),
            warning_count=sum(1 for f in group_findings if f.severity == Severity.WARNING),
            pass_count=0,
        )
        groups.append(g)

    doc_coverage: list[DocumentCoverage] = []
    if sources:
        for src in sources:
            src_facts = [f for f in (facts or []) if f.source_hash == src.source_hash]
            doc_coverage.append(DocumentCoverage(
                file_name=src.file_name,
                document_role=src.document_role.value if hasattr(src.document_role, 'value') else str(src.document_role),
                document_type=src.document_type,
                facts_extracted=len(src_facts),
            ))

    missing_docs: list[str] = []
    if sources:
        present_types = {src.document_type for src in sources}
        for expected in _EXPECTED_DOC_TYPES:
            if expected not in present_types:
                missing_docs.append(expected)

    report = ComplianceReport(
        validation_id=validation_id,
        project_id=project_id,
        revision_id=revision_id,
        groups=groups,
        document_coverage=doc_coverage,
        missing_documents=missing_docs,
        total_findings=len(findings),
        total_errors=sum(1 for f in findings if f.severity == Severity.ERROR),
        total_warnings=sum(1 for f in findings if f.severity == Severity.WARNING),
        total_info=sum(1 for f in findings if f.severity == Severity.INFO),
    )

    logger.info(
        "Compliance report: %d findings (%d errors, %d warnings) in %d groups",
        report.total_findings, report.total_errors, report.total_warnings, len(groups),
    )
    return report
