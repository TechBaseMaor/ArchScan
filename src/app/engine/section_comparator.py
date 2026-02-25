"""Section-by-section comparator: requirement vs submission.

Takes extracted facts from regulation and submission corpora, organises them by
category, and produces SectionComparison entries with expected/observed values,
pass/fail/warn/missing status, deviation, and human-readable explanations.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from src.app.domain.models import (
    ExtractedFact,
    Rule,
    RuleSet,
    SectionComparison,
    SourceFile,
)

logger = logging.getLogger(__name__)

_CATEGORY_TITLES: Dict[str, str] = {
    "area": "Building Areas",
    "height": "Building / Floor Heights",
    "setback": "Setback Distances",
    "parking": "Parking Requirements",
    "dwelling_units": "Dwelling Units",
    "fence_height": "Fence Heights",
    "coverage": "Ground Coverage",
    "balcony": "Balcony Projections",
    "laundry_enclosure": "Laundry Enclosures (מסתורי כביסה)",
    "green_building": "Green Building Requirements",
    "waste": "Waste Storage (אצירת אשפה)",
    "environment": "Environmental Requirements",
}


def compare_sections(
    facts: List[ExtractedFact],
    ruleset: Optional[RuleSet],
    sources: Optional[List[SourceFile]] = None,
) -> List[SectionComparison]:
    """Build section-by-section comparisons from regulation vs submission facts."""
    reg_facts = _partition_by_role(facts, "regulation")
    sub_facts = _partition_by_role(facts, "submission")

    source_map: Dict[str, str] = {}
    if sources:
        for s in sources:
            source_map[s.source_hash] = s.file_name

    rule_params = _extract_rule_params(ruleset) if ruleset else {}

    all_categories = sorted(set(reg_facts.keys()) | set(sub_facts.keys()) | set(rule_params.keys()))
    comparisons: List[SectionComparison] = []
    section_counter = 0

    for cat in all_categories:
        section_counter += 1
        reg_entries = reg_facts.get(cat, [])
        sub_entries = sub_facts.get(cat, [])
        rule_info = rule_params.get(cat)

        if reg_entries and sub_entries:
            comparisons.extend(
                _compare_matched(cat, section_counter, reg_entries, sub_entries, rule_info, source_map)
            )
        elif reg_entries and not sub_entries:
            comparisons.append(_missing_submission(cat, section_counter, reg_entries, rule_info, source_map))
        elif sub_entries and not reg_entries:
            if rule_info:
                comparisons.extend(
                    _compare_against_rule(cat, section_counter, sub_entries, rule_info, source_map)
                )
            else:
                comparisons.append(_no_regulation(cat, section_counter, sub_entries, source_map))
        elif rule_info:
            comparisons.append(_missing_both(cat, section_counter, rule_info))

    return comparisons


def _partition_by_role(
    facts: List[ExtractedFact], role: str,
) -> Dict[str, List[ExtractedFact]]:
    by_cat: Dict[str, List[ExtractedFact]] = defaultdict(list)
    for f in facts:
        doc_role = f.metadata.get("doc_role", "")
        profile = f.metadata.get("profile", "")
        if doc_role == role or profile == role:
            by_cat[f.category].append(f)
    return dict(by_cat)


def _extract_rule_params(ruleset: RuleSet) -> Dict[str, Dict[str, Any]]:
    """Map category → rule parameters for threshold comparisons."""
    params: Dict[str, Dict[str, Any]] = {}
    for rule in ruleset.rules:
        cats = _rule_categories(rule)
        for cat in cats:
            params[cat] = {
                "rule_id": rule.rule_id,
                "description": rule.description,
                "parameters": rule.computation.parameters,
                "layer": rule.metadata.get("layer", ""),
                "source_doc": rule.metadata.get("source_doc", ""),
                "legal_status": rule.metadata.get("legal_status", "unknown"),
            }
    return params


def _rule_categories(rule: Rule) -> List[str]:
    cats = []
    for pre in rule.preconditions:
        cats.append(pre.fact_category)
    if not cats:
        formula = rule.computation.formula
        fc = rule.computation.parameters.get("fact_category", "")
        if fc:
            cats.append(fc)
        elif "area" in formula:
            cats.append("area")
        elif "height" in formula:
            cats.append("height")
        elif "setback" in formula:
            cats.append("setback")
    return cats or ["general"]


def _compare_matched(
    cat: str,
    idx: int,
    reg_facts: List[ExtractedFact],
    sub_facts: List[ExtractedFact],
    rule_info: Optional[Dict],
    source_map: Dict[str, str],
) -> List[SectionComparison]:
    results: List[SectionComparison] = []
    title = _CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())

    for ri, rf in enumerate(reg_facts):
        best_sub, best_dev = _find_closest_submission(rf, sub_facts)
        reg_src = source_map.get(rf.source_hash, rf.metadata.get("source_file", ""))
        sub_src = source_map.get(best_sub.source_hash, best_sub.metadata.get("source_file", "")) if best_sub else ""

        status, explanation = _evaluate_pair(rf, best_sub, best_dev)
        legal = rule_info.get("legal_status", "unknown") if rule_info else "unknown"

        results.append(SectionComparison(
            section_id=f"S{idx}.{ri + 1}",
            section_title=f"{title}: {rf.label}",
            category=cat,
            regulation_source=reg_src,
            regulation_section_ref=rf.raw_source_ref or rf.metadata.get("section_ref", ""),
            regulation_value=rf.value,
            regulation_text=rf.label,
            submission_source=sub_src,
            submission_value=best_sub.value if best_sub else None,
            unit=rf.unit or (best_sub.unit if best_sub else ""),
            status=status,
            deviation=best_dev,
            explanation=explanation,
            legal_status=legal,
            evidence_links=_build_evidence_links(rf, best_sub, source_map),
        ))

    return results


def _missing_submission(
    cat: str,
    idx: int,
    reg_facts: List[ExtractedFact],
    rule_info: Optional[Dict],
    source_map: Dict[str, str],
) -> SectionComparison:
    title = _CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
    rf = reg_facts[0]
    reg_src = source_map.get(rf.source_hash, rf.metadata.get("source_file", ""))
    return SectionComparison(
        section_id=f"S{idx}",
        section_title=title,
        category=cat,
        regulation_source=reg_src,
        regulation_section_ref=rf.raw_source_ref,
        regulation_value=rf.value,
        regulation_text=rf.label,
        submission_value=None,
        unit=rf.unit,
        status="missing",
        explanation=f"Regulation requires {cat} data but no matching submission value was found. Manual intervention required.",
        legal_status=rule_info.get("legal_status", "unknown") if rule_info else "unknown",
    )


def _compare_against_rule(
    cat: str,
    idx: int,
    sub_facts: List[ExtractedFact],
    rule_info: Dict,
    source_map: Dict[str, str],
) -> List[SectionComparison]:
    results: List[SectionComparison] = []
    title = _CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
    params = rule_info.get("parameters", {})

    threshold = _extract_threshold(params)

    for si, sf in enumerate(sub_facts):
        sub_src = source_map.get(sf.source_hash, sf.metadata.get("source_file", ""))
        status = "pass"
        dev = None
        explanation = ""

        if threshold is not None:
            try:
                sv = float(sf.value)
                dev = sv - threshold
                if sv < threshold * 0.95:
                    status = "fail"
                    explanation = f"Submission value {sv} is below threshold {threshold}"
                elif sv < threshold:
                    status = "warn"
                    explanation = f"Submission value {sv} is marginally below threshold {threshold}"
                else:
                    explanation = f"Submission value {sv} meets threshold {threshold}"
            except (TypeError, ValueError):
                status = "manual_review"
                explanation = "Cannot compare non-numeric submission value against rule threshold"

        results.append(SectionComparison(
            section_id=f"S{idx}.{si + 1}",
            section_title=f"{title}: {sf.label}",
            category=cat,
            regulation_source=rule_info.get("source_doc", ""),
            regulation_section_ref=rule_info.get("rule_id", ""),
            regulation_value=threshold,
            regulation_text=rule_info.get("description", ""),
            submission_source=sub_src,
            submission_value=sf.value,
            unit=sf.unit,
            status=status,
            deviation=dev,
            explanation=explanation,
            legal_status=rule_info.get("legal_status", "unknown"),
        ))

    return results


def _no_regulation(
    cat: str,
    idx: int,
    sub_facts: List[ExtractedFact],
    source_map: Dict[str, str],
) -> SectionComparison:
    title = _CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
    sf = sub_facts[0]
    sub_src = source_map.get(sf.source_hash, sf.metadata.get("source_file", ""))
    return SectionComparison(
        section_id=f"S{idx}",
        section_title=title,
        category=cat,
        submission_source=sub_src,
        submission_value=sf.value,
        unit=sf.unit,
        status="manual_review",
        explanation=f"Submission provides {cat} data but no regulation reference was found. Requires manual verification.",
    )


def _missing_both(cat: str, idx: int, rule_info: Dict) -> SectionComparison:
    title = _CATEGORY_TITLES.get(cat, cat.replace("_", " ").title())
    return SectionComparison(
        section_id=f"S{idx}",
        section_title=title,
        category=cat,
        regulation_source=rule_info.get("source_doc", ""),
        regulation_text=rule_info.get("description", ""),
        regulation_value=_extract_threshold(rule_info.get("parameters", {})),
        status="missing",
        explanation=f"Neither regulation facts nor submission facts were extracted for {cat}. Manual intervention required.",
        legal_status=rule_info.get("legal_status", "unknown"),
    )


def _find_closest_submission(
    reg_fact: ExtractedFact, sub_facts: List[ExtractedFact],
) -> Tuple[Optional[ExtractedFact], Optional[float]]:
    """Find the submission fact closest in value to a regulation fact."""
    if not sub_facts:
        return None, None

    try:
        rv = float(reg_fact.value)
    except (TypeError, ValueError):
        return sub_facts[0], None

    best = None
    best_dev = None
    for sf in sub_facts:
        try:
            sv = float(sf.value)
            dev = sv - rv
            if best_dev is None or abs(dev) < abs(best_dev):
                best = sf
                best_dev = dev
        except (TypeError, ValueError):
            if best is None:
                best = sf
    return best, best_dev


def _evaluate_pair(
    reg: ExtractedFact,
    sub: Optional[ExtractedFact],
    deviation: Optional[float],
) -> Tuple[str, str]:
    if sub is None:
        return "missing", "No submission data available for comparison"

    if deviation is None:
        return "manual_review", "Non-numeric values — requires manual comparison"

    try:
        rv = float(reg.value)
    except (TypeError, ValueError):
        return "manual_review", "Cannot parse regulation value"

    abs_dev = abs(deviation)
    if rv == 0:
        pct = 0.0 if deviation == 0 else 100.0
    else:
        pct = (abs_dev / abs(rv)) * 100

    if pct <= 1.0:
        return "pass", f"Submission matches regulation (deviation {deviation:+.2f}, {pct:.1f}%)"
    elif pct <= 5.0:
        return "warn", f"Minor deviation from regulation ({deviation:+.2f}, {pct:.1f}%). Review recommended."
    else:
        return "fail", f"Significant deviation from regulation ({deviation:+.2f}, {pct:.1f}%). Compliance issue."


def _extract_threshold(params: Dict[str, Any]) -> Optional[float]:
    for key in ("min_area", "max_area", "min_setback", "max_height", "min_height", "max_intersections"):
        if key in params:
            try:
                return float(params[key])
            except (TypeError, ValueError):
                pass
    return None


def _build_evidence_links(
    reg: ExtractedFact,
    sub: Optional[ExtractedFact],
    source_map: Dict[str, str],
) -> List[str]:
    links: List[str] = []
    reg_file = source_map.get(reg.source_hash, reg.metadata.get("source_file", ""))
    if reg_file:
        ref = reg.raw_source_ref or ""
        links.append(f"{reg_file}" + (f" ({ref})" if ref else ""))
    if sub:
        sub_file = source_map.get(sub.source_hash, sub.metadata.get("source_file", ""))
        if sub_file:
            ref = sub.raw_source_ref or ""
            links.append(f"{sub_file}" + (f" ({ref})" if ref else ""))
    return links
