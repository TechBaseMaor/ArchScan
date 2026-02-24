"""Insights service — builds a client-facing RevisionSummary from extracted facts."""
from __future__ import annotations

import logging
from typing import Any

from src.app.config import settings
from src.app.domain.models import (
    AgreementStatus,
    ExtractedFact,
    ReconciliationEntry,
    RevisionSummary,
    SummaryMetric,
)

logger = logging.getLogger(__name__)

_AREA_CATEGORIES = {"area"}
_HEIGHT_CATEGORIES = {"height"}
_FLOOR_CATEGORIES = {"level", "floor_summary"}
_OPENING_CATEGORIES = {"opening_window", "opening_door"}
_SETBACK_CATEGORIES = {"setback"}


def build_revision_summary(
    project_id: str,
    revision_id: str,
    facts: list[ExtractedFact],
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
