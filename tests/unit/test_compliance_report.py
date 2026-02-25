"""Unit tests for compliance report builder — missing evidence and non-guessing policy."""
import pytest

from src.app.domain.models import (
    ComplianceReport,
    DocumentRole,
    ExtractedFact,
    ExtractedMetricSummary,
    FactType,
    Finding,
    MissingEvidence,
    RuleSet,
    Severity,
    SourceFile,
    SourceFormat,
    ComputationTrace,
)
from src.app.reporting.insights_service import build_compliance_report


def _fact(
    category: str,
    value,
    source_hash: str = "hash-a",
    fact_type: FactType = FactType.TEXTUAL,
    confidence: float = 1.0,
) -> ExtractedFact:
    return ExtractedFact(
        revision_id="rev1",
        source_hash=source_hash,
        fact_type=fact_type,
        category=category,
        label=f"test {category}",
        value=value,
        unit="m" if category != "area" else "m²",
        confidence=confidence,
    )


def _source(
    name: str,
    role: DocumentRole = DocumentRole.SUBMISSION,
    doc_type: str = "building_plan",
    fmt: SourceFormat = SourceFormat.PDF,
    source_hash: str = "hash-a",
) -> SourceFile:
    return SourceFile(
        file_name=name,
        source_format=fmt,
        source_hash=source_hash,
        size_bytes=1000,
        stored_path=f"/tmp/{name}",
        document_role=role,
        document_type=doc_type,
    )


def _finding(
    rule_ref: str = "TLV-TEST:1.0",
    severity: Severity = Severity.ERROR,
    message: str = "test finding",
) -> Finding:
    return Finding(
        validation_id="val1",
        rule_ref=rule_ref,
        severity=severity,
        message=message,
        input_facts=["f1"],
        computation_trace=ComputationTrace(formula="test_check"),
        project_id="p1",
        revision_id="rev1",
    )


class TestMissingEvidence:
    """Missing evidence entries must be explicit for every expected category without facts."""

    def test_no_facts_produces_missing_evidence_for_all_expected(self):
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=[],
        )
        assert len(report.missing_evidence) > 0
        missing_cats = {m.category for m in report.missing_evidence}
        for expected in ("area", "height", "setback", "parking", "dwelling_units"):
            assert expected in missing_cats, f"{expected} should be in missing_evidence"

    def test_missing_evidence_has_reason(self):
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=[],
        )
        for ev in report.missing_evidence:
            assert ev.reason, f"Missing evidence for {ev.category} must have a reason"
            assert ev.expected_source, f"Missing evidence for {ev.category} must have expected_source"

    def test_partial_facts_marks_only_missing_categories(self):
        facts = [_fact("area", 120.0), _fact("height", 3.2)]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
        )
        missing_cats = {m.category for m in report.missing_evidence}
        assert "area" not in missing_cats
        assert "height" not in missing_cats
        assert "setback" in missing_cats
        assert "parking" in missing_cats
        assert "dwelling_units" in missing_cats

    def test_all_expected_categories_present_means_no_missing_evidence(self):
        facts = [
            _fact("area", 120.0),
            _fact("height", 3.2),
            _fact("setback", 4.0),
            _fact("parking", 10),
            _fact("dwelling_units", 5),
        ]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
        )
        assert len(report.missing_evidence) == 0


class TestExtractedMetrics:
    """Extracted metrics must reflect actual facts and mark missing ones explicitly."""

    def test_metrics_include_actual_values(self):
        facts = [_fact("area", 120.0, source_hash="h1")]
        sources = [_source("plan.pdf", source_hash="h1")]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
            sources=sources,
        )
        area_metrics = [m for m in report.extracted_metrics if m.category == "area"]
        assert len(area_metrics) >= 1
        found = area_metrics[0]
        assert found.value == 120.0
        assert found.is_missing is False
        assert found.source_file == "plan.pdf"

    def test_missing_category_has_null_value_and_flag(self):
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=[],
        )
        parking_metrics = [m for m in report.extracted_metrics if m.category == "parking"]
        assert len(parking_metrics) == 1
        assert parking_metrics[0].value is None
        assert parking_metrics[0].is_missing is True
        assert parking_metrics[0].missing_reason != ""

    def test_no_inferred_values(self):
        """Values must never be computed/guessed — only real extracted values or None."""
        facts = [_fact("area", 120.0)]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
        )
        for m in report.extracted_metrics:
            if m.is_missing:
                assert m.value is None, f"Missing metric {m.category} must have null value, got {m.value}"


class TestDocumentCoverage:
    def test_sources_appear_in_coverage(self):
        sources = [
            _source("plan.pdf", DocumentRole.SUBMISSION, "building_plan", source_hash="h1"),
            _source("3729A.pdf", DocumentRole.REGULATION, "statutory_plan", source_hash="h2"),
        ]
        facts = [_fact("area", 100, source_hash="h1")]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
            sources=sources,
        )
        assert len(report.document_coverage) == 2
        names = {d.file_name for d in report.document_coverage}
        assert "plan.pdf" in names
        assert "3729A.pdf" in names

    def test_facts_count_per_source(self):
        sources = [_source("plan.pdf", source_hash="h1")]
        facts = [
            _fact("area", 100, source_hash="h1"),
            _fact("height", 3.2, source_hash="h1"),
        ]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=facts,
            sources=sources,
        )
        assert report.document_coverage[0].facts_extracted == 2


class TestMissingDocuments:
    def test_missing_expected_doc_types(self):
        sources = [
            _source("plan.pdf", doc_type="building_plan", source_hash="h1"),
        ]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
            facts=[],
            sources=sources,
        )
        assert "statutory_plan" in report.missing_documents
        assert "building_plan" not in report.missing_documents


class TestComplianceGroups:
    def test_findings_grouped_correctly(self):
        ruleset = RuleSet(
            name="test",
            rules=[],
        )
        findings = [_finding()]
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=findings,
            ruleset=ruleset,
        )
        assert report.total_findings == 1
        assert report.total_errors == 1

    def test_empty_findings_empty_groups(self):
        report = build_compliance_report(
            validation_id="v1",
            project_id="p1",
            revision_id="r1",
            findings=[],
        )
        assert report.groups == []
        assert report.total_findings == 0
