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
    ExtractedMetricSummary,
    Finding,
    MissingEvidence,
    OfficialityStatus,
    ReconciliationEntry,
    ReviewStatus,
    RevisionSummary,
    RuleSet,
    SectionComparison,
    Severity,
    SourceFile,
    SummaryMetric,
)
from src.app.engine.section_comparator import compare_sections

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

_EXPECTED_PILOT_CATEGORIES: dict[str, tuple[str, str, str]] = {
    "area": ("Building areas (gross/net/service)", "m²", "area_calculation or building_plan"),
    "height": ("Building and floor heights", "m", "building_plan or statutory_plan"),
    "setback": ("Setbacks from lot boundaries", "m", "building_plan or site_survey"),
    "parking": ("Parking space count", "spaces", "traffic_appendix or parking_guidelines"),
    "dwelling_units": ("Dwelling unit count", "units", "building_plan or area_calculation"),
}


def _build_extracted_metrics(
    facts: list[ExtractedFact],
    sources: Optional[list[SourceFile]],
) -> tuple[list[ExtractedMetricSummary], list[MissingEvidence]]:
    """Build per-category metric summaries and explicit missing evidence entries."""
    source_map: dict[str, SourceFile] = {}
    if sources:
        for src in sources:
            source_map[src.source_hash] = src

    facts_by_cat: dict[str, list[ExtractedFact]] = defaultdict(list)
    for f in facts:
        facts_by_cat[f.category].append(f)

    metrics: list[ExtractedMetricSummary] = []
    missing: list[MissingEvidence] = []

    for cat, (label, unit, expected_src) in sorted(_EXPECTED_PILOT_CATEGORIES.items()):
        cat_facts = facts_by_cat.get(cat, [])
        if not cat_facts:
            metrics.append(ExtractedMetricSummary(
                category=cat,
                label=label,
                value=None,
                unit=unit,
                is_missing=True,
                missing_reason=f"No {cat} data extracted from any source document.",
            ))
            missing.append(MissingEvidence(
                category=cat,
                expected_source=expected_src,
                reason=f"No {cat} facts were extracted. Expected from: {expected_src}.",
            ))
        else:
            for fact in cat_facts:
                src = source_map.get(fact.source_hash)
                metrics.append(ExtractedMetricSummary(
                    category=cat,
                    label=fact.label,
                    value=fact.value,
                    unit=fact.unit or unit,
                    source_file=src.file_name if src else "",
                    source_role=src.document_role.value if src and hasattr(src.document_role, "value") else "",
                    confidence=fact.confidence,
                ))

    extra_cats = set(facts_by_cat.keys()) - set(_EXPECTED_PILOT_CATEGORIES.keys())
    for cat in sorted(extra_cats):
        for fact in facts_by_cat[cat]:
            src = source_map.get(fact.source_hash)
            metrics.append(ExtractedMetricSummary(
                category=cat,
                label=fact.label,
                value=fact.value,
                unit=fact.unit,
                source_file=src.file_name if src else "",
                source_role=src.document_role.value if src and hasattr(src.document_role, "value") else "",
                confidence=fact.confidence,
            ))

    return metrics, missing


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
            off_status = (
                src.officiality_status.value
                if hasattr(src, "officiality_status") and hasattr(src.officiality_status, "value")
                else "pending"
            )
            off_conf = getattr(src, "officiality_confidence", 0.0)
            read_grade = (
                src.readability_grade.value
                if hasattr(src, "readability_grade") and hasattr(src.readability_grade, "value")
                else "high"
            )
            legal = (
                src.legal_status.value
                if hasattr(src, "legal_status") and hasattr(src.legal_status, "value")
                else "unknown"
            )
            doc_coverage.append(DocumentCoverage(
                file_name=src.file_name,
                document_role=src.document_role.value if hasattr(src.document_role, 'value') else str(src.document_role),
                document_type=src.document_type,
                facts_extracted=len(src_facts),
                officiality_status=off_status,
                officiality_confidence=off_conf,
                readability_grade=read_grade,
                legal_status=legal,
            ))

    missing_docs: list[str] = []
    if sources:
        present_types = {src.document_type for src in sources}
        for expected in _EXPECTED_DOC_TYPES:
            if expected not in present_types:
                missing_docs.append(expected)

    extracted_metrics: list[ExtractedMetricSummary] = []
    missing_evidence: list[MissingEvidence] = []
    if facts is not None:
        extracted_metrics, missing_evidence = _build_extracted_metrics(facts, sources)

    section_comparisons: list[SectionComparison] = []
    if facts is not None:
        section_comparisons = compare_sections(facts, ruleset, sources)

    has_pending = False
    if sources:
        has_pending = any(
            getattr(s, "officiality_status", None) in (
                OfficialityStatus.LIKELY_OFFICIAL,
                OfficialityStatus.UNVERIFIED,
                OfficialityStatus.PENDING,
            )
            for s in sources
            if getattr(s, "document_role", None) and s.document_role.value == "regulation"
        )

    report = ComplianceReport(
        validation_id=validation_id,
        project_id=project_id,
        revision_id=revision_id,
        groups=groups,
        document_coverage=doc_coverage,
        missing_documents=missing_docs,
        missing_evidence=missing_evidence,
        extracted_metrics=extracted_metrics,
        section_comparisons=section_comparisons,
        total_findings=len(findings),
        total_errors=sum(1 for f in findings if f.severity == Severity.ERROR),
        total_warnings=sum(1 for f in findings if f.severity == Severity.WARNING),
        total_info=sum(1 for f in findings if f.severity == Severity.INFO),
        has_pending_reviews=has_pending,
    )

    logger.info(
        "Compliance report: %d findings (%d errors, %d warnings) in %d groups, "
        "%d metrics, %d missing evidence, %d section comparisons",
        report.total_findings, report.total_errors, report.total_warnings,
        len(groups), len(extracted_metrics), len(missing_evidence),
        len(section_comparisons),
    )
    return report
