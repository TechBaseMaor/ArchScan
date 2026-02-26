"""KPI gates — baseline-vs-enriched evaluation for pilot rollout decisions.

Compares extraction quality before and after AI enrichment, enforcing
minimum thresholds on key metrics before enabling wider rollout.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.app.config import settings
from src.app.domain.models import AiProposal, ExtractedFact, ProposalStatus

logger = logging.getLogger(__name__)


class KpiResult(BaseModel):
    name: str
    description: str
    value: float
    threshold: float
    passed: bool
    unit: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class KpiReport(BaseModel):
    report_version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    overall_pass: bool = False
    results: list[KpiResult] = Field(default_factory=list)
    baseline_summary: dict[str, Any] = Field(default_factory=dict)
    enriched_summary: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""


def evaluate_kpis(
    baseline_facts: list[ExtractedFact],
    enriched_facts: list[ExtractedFact],
    proposals: list[AiProposal],
) -> KpiReport:
    """Evaluate KPI gates comparing baseline extraction vs AI-enriched results."""
    thresholds = settings.kpi_thresholds
    results: list[KpiResult] = []

    unknown_rate = _compute_unknown_field_rate(baseline_facts, enriched_facts)
    results.append(KpiResult(
        name="unknown_field_rate",
        description="Rate of fields that remain unidentified after enrichment",
        value=unknown_rate,
        threshold=thresholds.unknown_field_rate_max,
        passed=unknown_rate <= thresholds.unknown_field_rate_max,
        unit="%",
    ))

    recall = _compute_extraction_recall(baseline_facts, enriched_facts)
    results.append(KpiResult(
        name="extraction_recall",
        description="Proportion of mandatory parameters successfully extracted",
        value=recall,
        threshold=thresholds.recall_min,
        passed=recall >= thresholds.recall_min,
        unit="%",
    ))

    acceptance_rate = _compute_proposal_acceptance_rate(proposals)
    results.append(KpiResult(
        name="proposal_acceptance_rate",
        description="Rate of AI proposals accepted by users",
        value=acceptance_rate,
        threshold=thresholds.proposal_acceptance_min,
        passed=acceptance_rate >= thresholds.proposal_acceptance_min,
        unit="%",
    ))

    false_positive_rate = _compute_false_positive_rate(proposals)
    results.append(KpiResult(
        name="false_positive_rate",
        description="Rate of AI proposals rejected by users",
        value=false_positive_rate,
        threshold=thresholds.false_positive_rate_max,
        passed=false_positive_rate <= thresholds.false_positive_rate_max,
        unit="%",
    ))

    confidence_improvement = _compute_confidence_improvement(baseline_facts, enriched_facts)
    results.append(KpiResult(
        name="confidence_improvement",
        description="Average confidence improvement from AI enrichment",
        value=confidence_improvement,
        threshold=0.0,
        passed=confidence_improvement >= 0.0,
        unit="delta",
    ))

    category_coverage = _compute_category_coverage(enriched_facts)
    results.append(KpiResult(
        name="category_coverage",
        description="Proportion of expected categories with at least one extracted fact",
        value=category_coverage,
        threshold=thresholds.recall_min,
        passed=category_coverage >= thresholds.recall_min,
        unit="%",
    ))

    overall = all(r.passed for r in results)

    baseline_cats = {f.category for f in baseline_facts}
    enriched_cats = {f.category for f in enriched_facts}

    recommendation = _generate_recommendation(results, overall)

    report = KpiReport(
        overall_pass=overall,
        results=results,
        baseline_summary={
            "total_facts": len(baseline_facts),
            "categories": sorted(baseline_cats),
            "category_count": len(baseline_cats),
        },
        enriched_summary={
            "total_facts": len(enriched_facts),
            "categories": sorted(enriched_cats),
            "category_count": len(enriched_cats),
            "new_categories": sorted(enriched_cats - baseline_cats),
            "proposals_total": len(proposals),
            "proposals_accepted": sum(1 for p in proposals if p.status == ProposalStatus.ACCEPTED),
            "proposals_rejected": sum(1 for p in proposals if p.status == ProposalStatus.REJECTED),
        },
        recommendation=recommendation,
    )

    logger.info(
        "KPI evaluation: %s (%d/%d gates passed)",
        "PASS" if overall else "FAIL",
        sum(1 for r in results if r.passed),
        len(results),
    )
    return report


def _compute_unknown_field_rate(
    baseline: list[ExtractedFact],
    enriched: list[ExtractedFact],
) -> float:
    """Rate of facts with unknown/unrecognized categories."""
    expected = {"area", "height", "setback", "parking", "dwelling_units",
                "coverage", "floor_summary", "regulatory_threshold"}
    total = len(enriched) if enriched else len(baseline) if baseline else 1
    unknown = sum(1 for f in (enriched or baseline) if f.category not in expected)
    return unknown / total if total > 0 else 0.0


def _compute_extraction_recall(
    baseline: list[ExtractedFact],
    enriched: list[ExtractedFact],
) -> float:
    """Proportion of mandatory categories that have at least one fact."""
    mandatory = {"area", "height", "setback", "parking", "dwelling_units"}
    all_facts = enriched if enriched else baseline
    covered = {f.category for f in all_facts} & mandatory
    return len(covered) / len(mandatory) if mandatory else 1.0


def _compute_proposal_acceptance_rate(proposals: list[AiProposal]) -> float:
    decided = [p for p in proposals if p.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.EDITED)]
    if not decided:
        return 1.0
    accepted = sum(1 for p in decided if p.status in (ProposalStatus.ACCEPTED, ProposalStatus.EDITED))
    return accepted / len(decided)


def _compute_false_positive_rate(proposals: list[AiProposal]) -> float:
    decided = [p for p in proposals if p.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.EDITED)]
    if not decided:
        return 0.0
    rejected = sum(1 for p in decided if p.status == ProposalStatus.REJECTED)
    return rejected / len(decided)


def _compute_confidence_improvement(
    baseline: list[ExtractedFact],
    enriched: list[ExtractedFact],
) -> float:
    """Average confidence delta between enriched and baseline."""
    if not baseline or not enriched:
        return 0.0
    baseline_avg = sum(f.confidence for f in baseline) / len(baseline)
    enriched_avg = sum(f.confidence for f in enriched) / len(enriched)
    return enriched_avg - baseline_avg


def _compute_category_coverage(facts: list[ExtractedFact]) -> float:
    expected = {"area", "height", "setback", "parking", "dwelling_units",
                "coverage", "floor_summary", "regulatory_threshold"}
    if not expected:
        return 1.0
    covered = {f.category for f in facts} & expected
    return len(covered) / len(expected)


def _generate_recommendation(results: list[KpiResult], overall: bool) -> str:
    if overall:
        return (
            "All KPI gates passed. The AI enrichment module is performing within "
            "acceptable thresholds. Ready for Phase B (limited real projects with monitoring)."
        )

    failed = [r for r in results if not r.passed]
    names = ", ".join(r.name for r in failed)
    return (
        f"KPI gates failed: {names}. "
        "Do not enable auto-apply. Review extraction patterns and learned mappings. "
        "Continue with Phase A (internal pilot only) until thresholds are met."
    )


def save_kpi_report(report: KpiReport, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("KPI report saved to %s (overall=%s)", out, "PASS" if report.overall_pass else "FAIL")
    return out
