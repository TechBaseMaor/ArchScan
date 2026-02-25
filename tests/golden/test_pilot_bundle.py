"""Pilot bundle regression tests — verify the full permit-package pipeline.

Tests the end-to-end flow: classify -> extract -> validate against pilot ruleset.
Uses synthetic test data to avoid dependency on actual permit files.
"""
import pytest
from pathlib import Path
from unittest.mock import patch

from src.app.domain.models import (
    DocumentRole,
    ExtractedFact,
    FactType,
    RuleSet,
    SourceFile,
    SourceFormat,
)
from src.app.ingestion.bundle_classifier import classify_source
from src.app.ingestion.pdf_adapter import extract_facts_from_pdf
from src.app.engine.rule_engine import evaluate_ruleset
from src.app.dataset.manifest_models import DatasetManifest, SourceFormat as DSSourceFormat


def _load_pilot_ruleset() -> RuleSet:
    import json
    path = Path(__file__).resolve().parents[2] / "rulesets" / "tel_aviv_pilot_v1" / "1.0.0.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RuleSet.model_validate(raw)


def _make_synthetic_pdf(tmp_path: Path, name: str, text: str) -> Path:
    """Create a synthetic test file. Uses raw text fallback for Hebrew content."""
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


class TestBundleClassificationRegression:
    """Verify all pilot files are classified correctly."""

    EXPECTED = [
        ("3729A.pdf", SourceFormat.PDF, DocumentRole.REGULATION, "statutory_plan"),
        ("3729A_T.pdf", SourceFormat.PDF, DocumentRole.REGULATION, "statutory_plan"),
        ("דראפט לועדה.pdf", SourceFormat.PDF, DocumentRole.SUBMISSION, "committee_draft"),
        ("הנחיות מרחביות לפיתוח המגרש והסדרי חניה (1).pdf", SourceFormat.PDF, DocumentRole.REGULATION, "spatial_guidelines"),
        ("הנחיות מרחביות לתכנון ועיצוב הבניין (מהדורה 7).pdf", SourceFormat.PDF, DocumentRole.REGULATION, "spatial_guidelines"),
        ("מדיניות להיתרי בניה בנושא אצירת אשפה.pdf", SourceFormat.PDF, DocumentRole.REGULATION, "waste_policy"),
        ("מדיניות להיתרי בניה_ בנושא איכות הסביבה.pdf", SourceFormat.PDF, DocumentRole.REGULATION, "environment_policy"),
        ("תמצית מדיניות בניה ירוקה להיתרי בניה.pdf", SourceFormat.PDF, DocumentRole.REGULATION, "green_building_policy"),
        ("תוכנית הגשה 100.dwfx", SourceFormat.DWFX, DocumentRole.SUBMISSION, "building_plan"),
        ("מפת מדידה.dwfx", SourceFormat.DWFX, DocumentRole.SUBMISSION, "site_survey"),
        ("נספח תנועה.dwfx", SourceFormat.DWFX, DocumentRole.SUBMISSION, "traffic_appendix"),
        ("חישוב שטחים -150.dwfx", SourceFormat.DWFX, DocumentRole.SUBMISSION, "area_calculation"),
    ]

    @pytest.mark.parametrize("filename,fmt,expected_role,expected_type", EXPECTED)
    def test_classification(self, filename, fmt, expected_role, expected_type):
        sf = SourceFile(
            file_name=filename,
            source_format=fmt,
            source_hash="test",
            size_bytes=0,
            stored_path="",
        )
        role, doc_type = classify_source(sf)
        assert role == expected_role, f"{filename}: got {role}, expected {expected_role}"
        assert doc_type == expected_type, f"{filename}: got {doc_type}, expected {expected_type}"


class TestRegulationExtraction:
    """Verify regulation-profile extraction from PDF text."""

    def test_extract_setback_from_regulation(self, tmp_path):
        text = "קו בניין קדמי: 4.00 מ'\nקו בניין אחורי: 5.00 מ'\nקו בניין צדדי: 3.00 מ'"
        path = _make_synthetic_pdf(tmp_path, "regulation.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.REGULATION)
        setback_facts = [f for f in facts if f.category == "setback"]
        assert len(setback_facts) >= 3

    def test_extract_regulatory_threshold(self, tmp_path):
        text = "גובה קומה: עד 3.30 מ'\nתכסית: לא תעלה על 45%"
        path = _make_synthetic_pdf(tmp_path, "thresholds.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.REGULATION)
        threshold_facts = [f for f in facts if f.category == "regulatory_threshold"]
        assert len(threshold_facts) >= 1

    def test_extract_clause_references(self, tmp_path):
        text = "סעיף 02.05 - גובה הגדר\nסעיף 3.30 - דירוג הבניה"
        path = _make_synthetic_pdf(tmp_path, "clauses.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.REGULATION)
        clause_facts = [f for f in facts if f.category == "text_clause"]
        assert len(clause_facts) >= 2


class TestSubmissionExtraction:
    """Verify submission-profile extraction from PDF text."""

    def test_extract_dwelling_units(self, tmp_path):
        text = 'יחידות דיור: 19\nחניה: 20'
        path = _make_synthetic_pdf(tmp_path, "submission.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.SUBMISSION)
        unit_facts = [f for f in facts if f.category == "dwelling_units"]
        assert len(unit_facts) >= 1

    def test_extract_dwelling_units_rtl(self, tmp_path):
        text = 'דיור יחדות 19'
        path = _make_synthetic_pdf(tmp_path, "submission_rtl.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.SUBMISSION)
        unit_facts = [f for f in facts if f.category == "dwelling_units"]
        assert len(unit_facts) >= 1

    def test_extract_parking(self, tmp_path):
        text = "חניה מקומות 20\nsetback: 4.0 m"
        path = _make_synthetic_pdf(tmp_path, "parking.pdf", text)
        facts = extract_facts_from_pdf(str(path), "rev1", "hash1", DocumentRole.SUBMISSION)
        parking_facts = [f for f in facts if f.category == "parking"]
        assert len(parking_facts) >= 1


class TestPilotRulesetEvaluation:
    """Verify pilot ruleset produces expected findings."""

    def test_setback_violation_triggers_finding(self):
        ruleset = _load_pilot_ruleset()
        facts = [
            ExtractedFact(
                revision_id="rev1",
                source_hash="h1",
                fact_type=FactType.TEXTUAL,
                category="setback",
                label="Front setback",
                value=2.5,
                unit="m",
                metadata={"profile": "submission"},
            ),
        ]
        findings = evaluate_ruleset(ruleset, facts, "proj1", "rev1", "val1")
        setback_findings = [f for f in findings if "setback" in f.rule_ref.lower() or "SETBACK" in f.rule_ref]
        assert len(setback_findings) >= 1

    def test_compliant_setbacks_no_finding(self):
        ruleset = _load_pilot_ruleset()
        facts = [
            ExtractedFact(
                revision_id="rev1",
                source_hash="h1",
                fact_type=FactType.TEXTUAL,
                category="setback",
                label="Front setback",
                value=6.0,
                unit="m",
                metadata={"profile": "submission"},
            ),
        ]
        findings = evaluate_ruleset(ruleset, facts, "proj1", "rev1", "val1")
        setback_findings = [f for f in findings if "SETBACK" in f.rule_ref]
        assert len(setback_findings) == 0

    def test_cross_doc_parking_mismatch(self):
        ruleset = _load_pilot_ruleset()
        facts = [
            ExtractedFact(
                revision_id="rev1",
                source_hash="h1",
                fact_type=FactType.TEXTUAL,
                category="parking",
                label="Parking provided",
                value=10,
                unit="spaces",
                metadata={"profile": "submission"},
            ),
            ExtractedFact(
                revision_id="rev1",
                source_hash="h2",
                fact_type=FactType.TEXTUAL,
                category="parking",
                label="Parking required",
                value=20,
                unit="spaces",
                metadata={"profile": "regulation"},
            ),
        ]
        findings = evaluate_ruleset(ruleset, facts, "proj1", "rev1", "val1")
        parking_findings = [f for f in findings if "PARKING" in f.rule_ref]
        assert len(parking_findings) >= 1


class TestPilotManifestEntries:
    """Verify pilot entries are properly registered in the manifest."""

    def test_manifest_has_pilot_entries(self):
        import json
        manifest_path = Path(__file__).resolve().parents[2] / "golden-dataset" / "manifest.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = DatasetManifest.model_validate(raw)

        pilot_entries = [e for e in manifest.entries if "pilot" in e.tags]
        assert len(pilot_entries) >= 12

    def test_pilot_has_dwfx_entries(self):
        import json
        manifest_path = Path(__file__).resolve().parents[2] / "golden-dataset" / "manifest.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = DatasetManifest.model_validate(raw)

        dwfx_entries = [e for e in manifest.entries if e.source_format == DSSourceFormat.DWFX]
        assert len(dwfx_entries) >= 4

    def test_pilot_has_gating_entries(self):
        import json
        manifest_path = Path(__file__).resolve().parents[2] / "golden-dataset" / "manifest.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = DatasetManifest.model_validate(raw)

        pilot_gating = [
            e for e in manifest.entries
            if "pilot" in e.tags and e.baseline_status.value == "gating"
        ]
        assert len(pilot_gating) >= 4
