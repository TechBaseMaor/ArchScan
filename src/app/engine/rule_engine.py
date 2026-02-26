"""Declarative rule engine — evaluates versioned rules against extracted facts."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from src.app.config import settings
from src.app.domain.models import (
    ComputationTrace,
    ExtractedFact,
    Finding,
    Rule,
    RuleSet,
    Severity,
)
from src.app.engine.geometry_engine import (
    check_maximum,
    check_minimum,
    compare_area,
    compare_distance,
)
from src.app.i18n import t as i18n_t

logger = logging.getLogger(__name__)


def evaluate_ruleset(
    ruleset: RuleSet,
    facts: list[ExtractedFact],
    project_id: str,
    revision_id: str,
    validation_id: str,
    reference_date: date | None = None,
    locale: str = "en",
) -> list[Finding]:
    """Run all applicable rules in a ruleset against the extracted facts."""
    ref_date = reference_date or date.today()
    findings: list[Finding] = []

    for rule in ruleset.rules:
        if not _rule_effective(rule, ref_date):
            logger.debug("Skipping rule %s:%s — not effective on %s", rule.rule_id, rule.version, ref_date)
            continue

        matching_facts = _filter_facts_by_preconditions(rule, facts)
        if matching_facts is None:
            continue

        rule_findings = _execute_computation(rule, matching_facts, facts, project_id, revision_id, validation_id, locale)
        findings.extend(rule_findings)

    return findings


def _rule_effective(rule: Rule, ref_date: date) -> bool:
    if rule.effective_from and ref_date < rule.effective_from:
        return False
    if rule.effective_to and ref_date > rule.effective_to:
        return False
    return True


def _filter_facts_by_preconditions(rule: Rule, facts: list[ExtractedFact]) -> list[ExtractedFact] | None:
    """Return facts matching all preconditions, or None if preconditions are not satisfied."""
    if not rule.preconditions:
        return facts

    candidate_facts = facts
    for pre in rule.preconditions:
        matched = [f for f in candidate_facts if f.category == pre.fact_category]
        if pre.operator == "exists":
            if not matched:
                return None
        elif pre.operator in ("gt", "lt", "eq", "gte", "lte"):
            matched = [f for f in matched if _compare(f.value, pre.operator, pre.value)]
            if not matched:
                return None
        elif pre.operator == "between":
            matched = [
                f for f in matched
                if isinstance(f.value, (int, float)) and pre.value <= f.value <= pre.value_max
            ]
            if not matched:
                return None
        candidate_facts = matched

    return candidate_facts


def _compare(value: Any, operator: str, reference: Any) -> bool:
    try:
        v = float(value)
        r = float(reference)
    except (TypeError, ValueError):
        return False
    if operator == "gt":
        return v > r
    if operator == "lt":
        return v < r
    if operator == "eq":
        return v == r
    if operator == "gte":
        return v >= r
    if operator == "lte":
        return v <= r
    return False


def _execute_computation(
    rule: Rule,
    matched_facts: list[ExtractedFact],
    all_facts: list[ExtractedFact],
    project_id: str,
    revision_id: str,
    validation_id: str,
    locale: str = "en",
) -> list[Finding]:
    formula = rule.computation.formula
    params = rule.computation.parameters
    findings: list[Finding] = []

    if formula == "area_max_check":
        findings.extend(_area_max_check(rule, matched_facts, all_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "area_min_check":
        findings.extend(_area_min_check(rule, matched_facts, all_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "height_max_check":
        findings.extend(_height_max_check(rule, matched_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "height_min_check":
        findings.extend(_height_min_check(rule, matched_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "setback_min_check":
        findings.extend(_setback_min_check(rule, matched_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "cross_document_area_consistency":
        findings.extend(_cross_doc_area_consistency(rule, all_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "intersection_count_max":
        findings.extend(_intersection_count_max(rule, matched_facts, params, project_id, revision_id, validation_id, locale))
    elif formula == "submission_vs_regulation_check":
        findings.extend(_submission_vs_regulation_check(rule, all_facts, params, project_id, revision_id, validation_id, locale))
    else:
        logger.warning("Unknown formula '%s' in rule %s:%s", formula, rule.rule_id, rule.version)

    return findings


# ── Built-in formulas ────────────────────────────────────────────────────

def _area_max_check(rule, facts, all_facts, params, pid, rid, vid, locale) -> list[Finding]:
    max_area = float(params.get("max_area", 0))
    area_facts = [f for f in facts if f.category == "area"]
    results = []
    for fact in area_facts:
        tr = check_maximum(float(fact.value), max_area)
        if not tr.within_tolerance:
            msg_params = {"measured": fact.value, "max_allowed": max_area, "diff": f"{tr.difference:+.4f}"}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.area_exceeds_max", locale, **msg_params),
                [fact],
                "area_max_check",
                {"measured": fact.value, "max_allowed": max_area, "message_key": "finding.area_exceeds_max"},
                tr.difference,
                {"distance_m": tr.tolerance_applied},
            ))
    return results


def _area_min_check(rule, facts, all_facts, params, pid, rid, vid, locale) -> list[Finding]:
    min_area = float(params.get("min_area", 0))
    area_facts = [f for f in facts if f.category == "area"]
    results = []
    for fact in area_facts:
        tr = check_minimum(float(fact.value), min_area)
        if not tr.within_tolerance:
            msg_params = {"measured": fact.value, "min_required": min_area, "diff": f"{tr.difference:+.4f}"}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.area_below_min", locale, **msg_params),
                [fact],
                "area_min_check",
                {"measured": fact.value, "min_required": min_area, "message_key": "finding.area_below_min"},
                tr.difference,
                {"distance_m": tr.tolerance_applied},
            ))
    return results


def _height_max_check(rule, facts, params, pid, rid, vid, locale) -> list[Finding]:
    max_h = float(params.get("max_height", 0))
    results = []
    for fact in [f for f in facts if f.category == "height"]:
        tr = check_maximum(float(fact.value), max_h)
        if not tr.within_tolerance:
            msg_params = {"measured": fact.value, "max_allowed": max_h, "diff": f"{tr.difference:+.4f}"}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.height_exceeds_max", locale, **msg_params),
                [fact],
                "height_max_check",
                {"measured": fact.value, "max_allowed": max_h, "message_key": "finding.height_exceeds_max"},
                tr.difference,
                {"distance_m": tr.tolerance_applied},
            ))
    return results


def _height_min_check(rule, facts, params, pid, rid, vid, locale) -> list[Finding]:
    min_h = float(params.get("min_height", 0))
    results = []
    for fact in [f for f in facts if f.category == "height"]:
        tr = check_minimum(float(fact.value), min_h)
        if not tr.within_tolerance:
            msg_params = {"measured": fact.value, "min_required": min_h, "diff": f"{tr.difference:+.4f}"}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.height_below_min", locale, **msg_params),
                [fact],
                "height_min_check",
                {"measured": fact.value, "min_required": min_h, "message_key": "finding.height_below_min"},
                tr.difference,
                {"distance_m": tr.tolerance_applied},
            ))
    return results


def _setback_min_check(rule, facts, params, pid, rid, vid, locale) -> list[Finding]:
    min_setback = float(params.get("min_setback", 0))
    results = []
    for fact in [f for f in facts if f.category == "setback"]:
        tr = check_minimum(float(fact.value), min_setback)
        if not tr.within_tolerance:
            msg_params = {"measured": fact.value, "min_required": min_setback, "diff": f"{tr.difference:+.4f}"}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.setback_below_min", locale, **msg_params),
                [fact],
                "setback_min_check",
                {"measured": fact.value, "min_required": min_setback, "message_key": "finding.setback_below_min"},
                tr.difference,
                {"distance_m": tr.tolerance_applied},
            ))
    return results


def _cross_doc_area_consistency(rule, all_facts, params, pid, rid, vid, locale) -> list[Finding]:
    """Compare geometric area facts vs textual area facts for consistency."""
    max_deviation_pct = float(params.get("max_deviation_pct", 0.5))
    geom_areas = [f for f in all_facts if f.category == "area" and f.fact_type.value == "geometric"]
    text_areas = [f for f in all_facts if f.category == "area" and f.fact_type.value == "textual"]
    results = []

    for ga in geom_areas:
        for ta in text_areas:
            tr = compare_area(float(ga.value), float(ta.value))
            if not tr.within_tolerance:
                msg_params = {"geometric_value": ga.value, "textual_value": ta.value, "diff": f"{tr.difference:+.4f}"}
                results.append(_make_finding(
                    rule, vid, pid, rid,
                    i18n_t("finding.cross_doc_area_mismatch", locale, **msg_params),
                    [ga, ta],
                    "cross_document_area_consistency",
                    {"geometric_value": ga.value, "textual_value": ta.value, "deviation_pct": abs(tr.difference) / max(float(ta.value), 0.001) * 100, "message_key": "finding.cross_doc_area_mismatch"},
                    tr.difference,
                    {"area_pct": max_deviation_pct},
                ))
    return results


def _intersection_count_max(rule, facts, params, pid, rid, vid, locale) -> list[Finding]:
    max_count = int(params.get("max_intersections", 0))
    results = []
    for fact in [f for f in facts if f.category == "intersection"]:
        count = int(fact.value)
        if count > max_count:
            msg_params = {"detected": count, "max_allowed": max_count}
            results.append(_make_finding(
                rule, vid, pid, rid,
                i18n_t("finding.intersection_exceeds_max", locale, **msg_params),
                [fact],
                "intersection_count_max",
                {"detected": count, "max_allowed": max_count, "message_key": "finding.intersection_exceeds_max"},
                count - max_count,
                {},
            ))
    return results


def _submission_vs_regulation_check(rule, all_facts, params, pid, rid, vid, locale) -> list[Finding]:
    """Compare submission facts vs regulation facts for the same category."""
    category = params.get("fact_category", "")
    comparison = params.get("comparison", "gte")
    if not category:
        return []

    submission_facts = [
        f for f in all_facts
        if f.category == category and f.metadata.get("profile") == "submission"
    ]
    regulation_facts = [
        f for f in all_facts
        if f.category == category and f.metadata.get("profile") == "regulation"
    ]

    if not submission_facts or not regulation_facts:
        return []

    results: list[Finding] = []
    for sf in submission_facts:
        for rf in regulation_facts:
            try:
                sv = float(sf.value)
                rv = float(rf.value)
            except (TypeError, ValueError):
                continue

            violation = False
            if comparison == "gte" and sv < rv:
                violation = True
            elif comparison == "lte" and sv > rv:
                violation = True
            elif comparison == "eq" and sv != rv:
                violation = True

            if violation:
                diff = sv - rv
                msg = (
                    f"Cross-document mismatch ({category}): "
                    f"submission={sv}, regulation={rv}, diff={diff:+.2f}"
                )
                results.append(_make_finding(
                    rule, vid, pid, rid,
                    msg,
                    [sf, rf],
                    "submission_vs_regulation_check",
                    {"submission_value": sv, "regulation_value": rv, "comparison": comparison},
                    diff,
                    {},
                ))
    return results


# ── Finding factory ──────────────────────────────────────────────────────

def _make_finding(
    rule: Rule,
    validation_id: str,
    project_id: str,
    revision_id: str,
    message: str,
    used_facts: list[ExtractedFact],
    formula: str,
    inputs: dict,
    result: Any,
    tolerance: dict,
) -> Finding:
    expected = inputs.get("max_allowed") or inputs.get("min_required") or inputs.get("regulation_value")
    observed = inputs.get("measured") or inputs.get("submission_value") or inputs.get("detected")
    deviation = float(result) if isinstance(result, (int, float)) else None

    section_ref = rule.metadata.get("section_ref", "")
    regulation_basis = rule.metadata.get("source_doc", "")

    explanation = ""
    if expected is not None and observed is not None:
        explanation = f"Expected: {expected}, Observed: {observed}"
        if deviation is not None:
            explanation += f", Deviation: {deviation:+.2f}"

    return Finding(
        validation_id=validation_id,
        rule_ref=f"{rule.rule_id}:{rule.version}",
        severity=rule.severity,
        message=message,
        input_facts=[f.fact_id for f in used_facts],
        computation_trace=ComputationTrace(
            formula=formula,
            inputs=inputs,
            result=result,
            tolerance_applied=tolerance,
        ),
        project_id=project_id,
        revision_id=revision_id,
        source_hashes=list({f.source_hash for f in used_facts}),
        section_ref=section_ref,
        regulation_basis=regulation_basis,
        expected_value=expected,
        observed_value=observed,
        deviation=deviation,
        explanation=explanation,
    )