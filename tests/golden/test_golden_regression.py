"""Golden dataset regression tests — verify findings match expected results."""
import pytest
from pathlib import Path

from src.app.config import settings
from src.app.dataset.manifest_models import (
    DatasetCategory,
    DatasetEntry,
    DatasetManifest,
    DownloadPolicy,
    ExpectedFinding,
    GroundTruth,
    SourceFormat,
)
from src.app.domain.models import RuleSet, Rule, RuleComputation, RulePrecondition, Severity
from src.app.benchmark.runner import _process_entry, _extract_facts
from src.app.benchmark.evaluator import evaluate_all
from src.app.benchmark.kpi_models import GateStatus


def _sample_ruleset() -> RuleSet:
    return RuleSet(
        ruleset_id="test-golden",
        name="Golden Test Rules",
        rules=[
            Rule(
                rule_id="AREA-MAX",
                version="1.0",
                severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                computation=RuleComputation(formula="area_max_check", parameters={"max_area": 200}),
            ),
            Rule(
                rule_id="HEIGHT-MIN",
                version="1.0",
                severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="height", operator="exists")],
                computation=RuleComputation(formula="height_min_check", parameters={"min_height": 2.5}),
            ),
            Rule(
                rule_id="SETBACK-MIN",
                version="1.0",
                severity=Severity.ERROR,
                preconditions=[RulePrecondition(fact_category="setback", operator="exists")],
                computation=RuleComputation(formula="setback_min_check", parameters={"min_setback": 3.0}),
            ),
        ],
    )


def _make_synthetic_pdf(tmp_path: Path, entry_id: str, text: str) -> Path:
    p = tmp_path / "simple" / f"{entry_id}.pdf"
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "", 12)
        for line in text.split("\n"):
            pdf.cell(0, 8, line.strip(), new_x="LMARGIN", new_y="NEXT")
        pdf.output(str(p))
    except ImportError:
        p.write_text(text)
    return p


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path):
    old_dir = settings.golden_dataset_dir
    settings.golden_dataset_dir = tmp_path
    yield
    settings.golden_dataset_dir = old_dir


class TestAreaViolationDetection:
    def test_area_exceeding_max_triggers_finding(self, tmp_path):
        entry = DatasetEntry(
            entry_id="area-viol",
            name="Area Violation",
            category=DatasetCategory.SIMPLE,
            source_format=SourceFormat.PDF,
            source_url="local://synthetic",
            download_policy=DownloadPolicy.MANUAL,
            ground_truth=GroundTruth(gross_area=250.0),
            expected_findings=[
                ExpectedFinding(rule_id="AREA-MAX", rule_version="1.0", severity="error", expected=True),
            ],
        )
        path = _make_synthetic_pdf(tmp_path, "area-viol", "area: 250 m2\nheight: 3.0 m")
        result = _process_entry(entry, path, _sample_ruleset())
        assert result.true_positives >= 1
        assert result.false_negatives == 0


class TestHeightViolationDetection:
    def test_height_below_min_triggers_finding(self, tmp_path):
        entry = DatasetEntry(
            entry_id="height-viol",
            name="Height Violation",
            category=DatasetCategory.SIMPLE,
            source_format=SourceFormat.PDF,
            source_url="local://synthetic",
            download_policy=DownloadPolicy.MANUAL,
            ground_truth=GroundTruth(max_height=2.0),
            expected_findings=[
                ExpectedFinding(rule_id="HEIGHT-MIN", rule_version="1.0", severity="error", expected=True),
            ],
        )
        path = _make_synthetic_pdf(tmp_path, "height-viol", "area: 100 m2\nheight: 2.0 m")
        result = _process_entry(entry, path, _sample_ruleset())
        assert result.true_positives >= 1
        assert result.false_negatives == 0


class TestSetbackViolationDetection:
    def test_setback_below_min_triggers_finding(self, tmp_path):
        entry = DatasetEntry(
            entry_id="setback-viol",
            name="Setback Violation",
            category=DatasetCategory.SIMPLE,
            source_format=SourceFormat.PDF,
            source_url="local://synthetic",
            download_policy=DownloadPolicy.MANUAL,
            ground_truth=GroundTruth(min_setback=1.5),
            expected_findings=[
                ExpectedFinding(rule_id="SETBACK-MIN", rule_version="1.0", severity="error", expected=True),
            ],
        )
        path = _make_synthetic_pdf(tmp_path, "setback-viol", "area: 100 m2\nsetback: 1.5 m")
        result = _process_entry(entry, path, _sample_ruleset())
        assert result.true_positives >= 1


class TestCleanProjectNoFindings:
    def test_compliant_project_no_findings(self, tmp_path):
        entry = DatasetEntry(
            entry_id="clean",
            name="Clean",
            category=DatasetCategory.SIMPLE,
            source_format=SourceFormat.PDF,
            source_url="local://synthetic",
            download_policy=DownloadPolicy.MANUAL,
            ground_truth=GroundTruth(gross_area=120.0, max_height=3.0, min_setback=5.0),
            expected_findings=[],
        )
        path = _make_synthetic_pdf(tmp_path, "clean", "area: 120 m2\nheight: 3.0 m\nsetback: 5.0 m")
        result = _process_entry(entry, path, _sample_ruleset())
        assert result.false_positives == 0


class TestKPIGateIntegration:
    def test_perfect_results_pass_gate(self):
        from src.app.benchmark.kpi_models import EntryResult
        results = [
            EntryResult(
                entry_id="t1", category="simple", source_format="pdf",
                baseline_status="gating",
                area_error_pct=0.1, height_error_m=0.005,
                true_positives=3, false_positives=0, false_negatives=0,
                ingestion_time_ms=50, validation_time_ms=20,
            ),
        ]
        metrics, gate = evaluate_all(results)
        assert gate == GateStatus.PASS

    def test_bad_precision_fails_gate(self):
        from src.app.benchmark.kpi_models import EntryResult
        results = [
            EntryResult(
                entry_id="t1", category="simple", source_format="pdf",
                baseline_status="gating",
                true_positives=1, false_positives=20, false_negatives=0,
            ),
        ]
        metrics, gate = evaluate_all(results)
        assert gate == GateStatus.FAIL
        assert any(m.name == "precision" and m.status == GateStatus.FAIL for m in metrics)
