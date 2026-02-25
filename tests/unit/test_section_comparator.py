"""Unit tests for section-by-section requirement vs submission comparator."""
import pytest

from src.app.domain.models import (
    DocumentRole,
    ExtractedFact,
    FactType,
    Rule,
    RuleComputation,
    RuleSet,
    SectionComparison,
    SourceFile,
    SourceFormat,
)
from src.app.engine.section_comparator import compare_sections


def _fact(
    category: str,
    value,
    role: str = "submission",
    source_hash: str = "h1",
    label: str = "",
) -> ExtractedFact:
    return ExtractedFact(
        revision_id="rev1",
        source_hash=source_hash,
        fact_type=FactType.TEXTUAL,
        category=category,
        label=label or f"test {category}",
        value=value,
        unit="m",
        metadata={"doc_role": role, "profile": role, "source_file": f"{role}_doc.pdf"},
    )


def _source(
    name: str,
    role: DocumentRole = DocumentRole.SUBMISSION,
    source_hash: str = "h1",
) -> SourceFile:
    return SourceFile(
        file_name=name,
        source_format=SourceFormat.PDF,
        source_hash=source_hash,
        size_bytes=1000,
        stored_path=f"/tmp/{name}",
        document_role=role,
    )


def _ruleset() -> RuleSet:
    return RuleSet(
        name="Test RS",
        rules=[
            Rule(
                rule_id="AREA-MIN",
                version="1.0",
                computation=RuleComputation(
                    formula="area_min_check",
                    parameters={"min_area": 35.0},
                ),
                preconditions=[],
                metadata={"layer": "statutory", "source_doc": "3729A"},
            ),
        ],
    )


class TestSectionComparison:
    def test_matched_regulation_and_submission_exact(self):
        facts = [
            _fact("setback", 5.0, role="regulation", source_hash="h-reg"),
            _fact("setback", 5.0, role="submission", source_hash="h-sub"),
        ]
        comparisons = compare_sections(facts, None)
        assert len(comparisons) >= 1
        c = comparisons[0]
        assert c.category == "setback"
        assert c.regulation_value == 5.0
        assert c.submission_value == 5.0
        assert c.status == "pass"
        assert c.deviation is not None

    def test_significant_deviation_fails(self):
        facts = [
            _fact("height", 3.3, role="regulation", source_hash="h-reg"),
            _fact("height", 4.5, role="submission", source_hash="h-sub"),
        ]
        comparisons = compare_sections(facts, None)
        assert len(comparisons) >= 1
        c = comparisons[0]
        assert c.status == "fail"
        assert "Significant deviation" in c.explanation

    def test_missing_submission_marked(self):
        facts = [
            _fact("parking", 10, role="regulation", source_hash="h-reg"),
        ]
        comparisons = compare_sections(facts, None)
        assert len(comparisons) >= 1
        c = comparisons[0]
        assert c.status == "missing"
        assert c.submission_value is None
        assert "Manual intervention" in c.explanation

    def test_only_submission_triggers_manual_review(self):
        facts = [
            _fact("dwelling_units", 5, role="submission"),
        ]
        comparisons = compare_sections(facts, None)
        assert len(comparisons) >= 1
        c = comparisons[0]
        assert c.status == "manual_review"
        assert "manual verification" in c.explanation.lower()

    def test_submission_compared_against_rule_threshold(self):
        facts = [
            _fact("area", 120.0, role="submission"),
        ]
        comparisons = compare_sections(facts, _ruleset())
        area_comps = [c for c in comparisons if c.category == "area"]
        assert len(area_comps) >= 1
        c = area_comps[0]
        assert c.regulation_value == 35.0
        assert c.submission_value == 120.0
        assert c.status == "pass"

    def test_submission_below_rule_threshold_fails(self):
        facts = [
            _fact("area", 20.0, role="submission"),
        ]
        comparisons = compare_sections(facts, _ruleset())
        area_comps = [c for c in comparisons if c.category == "area"]
        assert len(area_comps) >= 1
        c = area_comps[0]
        assert c.status == "fail"

    def test_empty_facts_with_ruleset_produces_missing(self):
        comparisons = compare_sections([], _ruleset())
        assert len(comparisons) >= 1
        c = comparisons[0]
        assert c.status == "missing"
        assert "Manual intervention" in c.explanation

    def test_evidence_links_populated(self):
        sources = [
            _source("reg.pdf", DocumentRole.REGULATION, "h-reg"),
            _source("sub.pdf", DocumentRole.SUBMISSION, "h-sub"),
        ]
        facts = [
            _fact("setback", 4.0, role="regulation", source_hash="h-reg"),
            _fact("setback", 4.1, role="submission", source_hash="h-sub"),
        ]
        comparisons = compare_sections(facts, None, sources)
        c = comparisons[0]
        assert len(c.evidence_links) == 2
        assert any("reg.pdf" in link for link in c.evidence_links)
        assert any("sub.pdf" in link for link in c.evidence_links)


class TestSectionIds:
    def test_section_ids_unique(self):
        facts = [
            _fact("area", 100, role="regulation", source_hash="h1"),
            _fact("area", 105, role="submission", source_hash="h2"),
            _fact("height", 3.0, role="regulation", source_hash="h1"),
            _fact("height", 3.1, role="submission", source_hash="h2"),
        ]
        comparisons = compare_sections(facts, None)
        ids = [c.section_id for c in comparisons]
        assert len(ids) == len(set(ids)), f"Duplicate section IDs: {ids}"


class TestMinorDeviation:
    def test_minor_deviation_warns(self):
        facts = [
            _fact("area", 100.0, role="regulation", source_hash="h-reg"),
            _fact("area", 103.0, role="submission", source_hash="h-sub"),
        ]
        comparisons = compare_sections(facts, None)
        c = comparisons[0]
        assert c.status == "warn"
        assert "Minor deviation" in c.explanation
