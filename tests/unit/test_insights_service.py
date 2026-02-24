"""Unit tests for the insights service (summary + reconciliation)."""
import pytest

from src.app.domain.models import (
    AgreementStatus,
    ExtractedFact,
    FactType,
    RevisionSummary,
)
from src.app.reporting.insights_service import build_revision_summary


def _fact(
    category: str,
    value,
    fact_type: FactType = FactType.GEOMETRIC,
    confidence: float = 1.0,
    source_hash: str = "ifc-hash",
    **kwargs,
) -> ExtractedFact:
    return ExtractedFact(
        revision_id="rev1",
        source_hash=source_hash,
        fact_type=fact_type,
        category=category,
        label=f"test {category}",
        value=value,
        unit="m2" if "area" in category else "m",
        confidence=confidence,
        **kwargs,
    )


class TestBuildSummary:
    def test_empty_facts(self):
        s = build_revision_summary("p1", "r1", [])
        assert s.total_facts == 0
        assert s.areas == []
        assert s.reconciliation == []

    def test_area_facts_grouped(self):
        facts = [
            _fact("area", 100.0),
            _fact("area", 80.0),
            _fact("height", 3.0),
        ]
        s = build_revision_summary("p1", "r1", facts)
        assert len(s.areas) == 2
        assert len(s.heights) == 1
        assert s.total_facts == 3

    def test_openings_grouped(self):
        facts = [
            _fact("opening_window", 1),
            _fact("opening_door", 1),
        ]
        s = build_revision_summary("p1", "r1", facts)
        assert len(s.openings) == 2

    def test_floors_and_setbacks(self):
        facts = [
            _fact("level", 3.0),
            _fact("floor_summary", 5),
            _fact("setback", 4.0),
        ]
        s = build_revision_summary("p1", "r1", facts)
        assert len(s.floors) == 2
        assert len(s.setbacks) == 1

    def test_sources_used(self):
        facts = [
            _fact("area", 100, source_hash="h1"),
            _fact("area", 200, source_hash="h2"),
        ]
        s = build_revision_summary("p1", "r1", facts)
        assert sorted(s.sources_used) == ["h1", "h2"]


class TestReconciliation:
    def test_single_source_ifc(self):
        facts = [_fact("area", 100.0, FactType.GEOMETRIC)]
        s = build_revision_summary("p1", "r1", facts)
        recon = [r for r in s.reconciliation if r.category == "area"]
        assert len(recon) == 1
        assert recon[0].agreement == AgreementStatus.SINGLE_SOURCE
        assert recon[0].ifc_value == 100.0

    def test_single_source_pdf(self):
        facts = [_fact("area", 100.0, FactType.TEXTUAL, source_hash="pdf-hash")]
        s = build_revision_summary("p1", "r1", facts)
        recon = [r for r in s.reconciliation if r.category == "area"]
        assert recon[0].agreement == AgreementStatus.SINGLE_SOURCE
        assert recon[0].pdf_value == 100.0

    def test_matched_values(self):
        facts = [
            _fact("area", 100.0, FactType.GEOMETRIC),
            _fact("area", 100.0, FactType.TEXTUAL, source_hash="pdf"),
        ]
        s = build_revision_summary("p1", "r1", facts)
        recon = [r for r in s.reconciliation if r.category == "area"]
        assert recon[0].agreement == AgreementStatus.MATCHED
        assert recon[0].deviation_pct == 0.0

    def test_major_deviation(self):
        facts = [
            _fact("area", 100.0, FactType.GEOMETRIC),
            _fact("area", 200.0, FactType.TEXTUAL, source_hash="pdf"),
        ]
        s = build_revision_summary("p1", "r1", facts)
        recon = [r for r in s.reconciliation if r.category == "area"]
        assert recon[0].agreement == AgreementStatus.MAJOR_DEVIATION
        assert recon[0].chosen_value == 100.0  # IFC preferred

    def test_metric_source_label(self):
        facts = [
            _fact("height", 3.0, FactType.GEOMETRIC),
            _fact("height", 2.8, FactType.TEXTUAL, source_hash="pdf"),
        ]
        s = build_revision_summary("p1", "r1", facts)
        ifc_metrics = [m for m in s.heights if m.source == "ifc"]
        pdf_metrics = [m for m in s.heights if m.source == "pdf"]
        assert len(ifc_metrics) >= 1
        assert len(pdf_metrics) >= 1
