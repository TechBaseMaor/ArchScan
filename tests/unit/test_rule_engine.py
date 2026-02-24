"""Unit tests for the rule engine."""
import pytest
from datetime import date

from src.app.domain.models import (
    ExtractedFact,
    FactType,
    Rule,
    RuleComputation,
    RulePrecondition,
    RuleSet,
    Severity,
)
from src.app.engine.rule_engine import evaluate_ruleset


def _make_fact(category: str, value, fact_type: FactType = FactType.GEOMETRIC, **kwargs) -> ExtractedFact:
    return ExtractedFact(
        revision_id="rev1",
        source_hash="abc123",
        fact_type=fact_type,
        category=category,
        label=f"test {category}",
        value=value,
        unit="m2" if category == "area" else "m",
        **kwargs,
    )


def _make_ruleset(rules: list[Rule]) -> RuleSet:
    return RuleSet(ruleset_id="test-rs", name="Test Rules", rules=rules)


class TestAreaMaxCheck:
    def test_area_within_limit(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R1", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 200}),
            )
        ])
        facts = [_make_fact("area", 150.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 0

    def test_area_exceeds_limit(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R1", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 200}),
            )
        ])
        facts = [_make_fact("area", 250.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 1
        assert findings[0].rule_ref == "R1:1.0"
        assert findings[0].severity == Severity.ERROR
        assert "250" in findings[0].message


class TestHeightMinCheck:
    def test_height_above_minimum(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R2", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="height", operator="exists")],
                computation=RuleComputation(formula="height_min_check", parameters={"min_height": 2.5}),
            )
        ])
        facts = [_make_fact("height", 3.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 0

    def test_height_below_minimum(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R2", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="height", operator="exists")],
                computation=RuleComputation(formula="height_min_check", parameters={"min_height": 2.5}),
            )
        ])
        facts = [_make_fact("height", 2.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 1


class TestSetbackMinCheck:
    def test_setback_ok(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R3", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="setback", operator="exists")],
                computation=RuleComputation(formula="setback_min_check", parameters={"min_setback": 3.0}),
            )
        ])
        facts = [_make_fact("setback", 5.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 0

    def test_setback_violation(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R3", version="1.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="setback", operator="exists")],
                computation=RuleComputation(formula="setback_min_check", parameters={"min_setback": 3.0}),
            )
        ])
        facts = [_make_fact("setback", 1.5)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 1


class TestEffectiveDateFiltering:
    def test_rule_not_yet_effective(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R4", version="1.0", severity=Severity.ERROR,
                effective_from=date(2030, 1, 1),
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 100}),
            )
        ])
        facts = [_make_fact("area", 999.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1", reference_date=date(2025, 1, 1))
        assert len(findings) == 0

    def test_rule_expired(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R5", version="1.0", severity=Severity.ERROR,
                effective_from=date(2020, 1, 1),
                effective_to=date(2023, 12, 31),
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 100}),
            )
        ])
        facts = [_make_fact("area", 999.0)]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1", reference_date=date(2025, 1, 1))
        assert len(findings) == 0


class TestCrossDocumentConsistency:
    def test_matching_areas(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R6", version="1.0", severity=Severity.WARNING,
                computation=RuleComputation(formula="cross_document_area_consistency", parameters={"max_deviation_pct": 0.5}),
            )
        ])
        facts = [
            _make_fact("area", 100.0, fact_type=FactType.GEOMETRIC),
            _make_fact("area", 100.0, fact_type=FactType.TEXTUAL),
        ]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 0

    def test_mismatched_areas(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="R6", version="1.0", severity=Severity.WARNING,
                computation=RuleComputation(formula="cross_document_area_consistency", parameters={"max_deviation_pct": 0.5}),
            )
        ])
        facts = [
            _make_fact("area", 100.0, fact_type=FactType.GEOMETRIC),
            _make_fact("area", 110.0, fact_type=FactType.TEXTUAL),
        ]
        findings = evaluate_ruleset(ruleset, facts, "p1", "r1", "v1")
        assert len(findings) == 1


class TestFindingTraceability:
    def test_finding_has_full_trace(self):
        ruleset = _make_ruleset([
            Rule(
                rule_id="TRACE-1", version="2.0", severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 50}),
            )
        ])
        facts = [_make_fact("area", 100.0)]
        findings = evaluate_ruleset(ruleset, facts, "proj1", "rev1", "val1")
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_ref == "TRACE-1:2.0"
        assert f.project_id == "proj1"
        assert f.revision_id == "rev1"
        assert f.validation_id == "val1"
        assert len(f.input_facts) == 1
        assert f.computation_trace.formula == "area_max_check"
        assert "measured" in f.computation_trace.inputs
        assert len(f.source_hashes) > 0
