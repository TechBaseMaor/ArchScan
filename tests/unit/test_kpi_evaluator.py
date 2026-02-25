"""Unit tests for KPI evaluator math correctness."""
import pytest

from src.app.benchmark.kpi_models import EntryResult, GateStatus
from src.app.benchmark.evaluator import (
    compute_area_mae,
    compute_height_mae,
    compute_precision,
    compute_recall,
    evaluate_all,
)


def _make_result(**kwargs) -> EntryResult:
    defaults = {"entry_id": "test", "category": "simple", "source_format": "ifc", "baseline_status": "gating"}
    defaults.update(kwargs)
    return EntryResult(**defaults)


class TestAreaMAE:
    def test_zero_error(self):
        results = [_make_result(area_error_pct=0.0), _make_result(area_error_pct=0.0)]
        m = compute_area_mae(results)
        assert m is not None
        assert m.value == 0.0
        assert m.status == GateStatus.PASS

    def test_within_threshold(self):
        results = [_make_result(area_error_pct=0.3), _make_result(area_error_pct=0.4)]
        m = compute_area_mae(results)
        assert m.value == pytest.approx(0.35, abs=0.01)
        assert m.status == GateStatus.PASS

    def test_exceeds_threshold(self):
        results = [_make_result(area_error_pct=1.0), _make_result(area_error_pct=2.0)]
        m = compute_area_mae(results)
        assert m.value == pytest.approx(1.5, abs=0.01)
        assert m.status == GateStatus.FAIL

    def test_no_data(self):
        results = [_make_result()]
        m = compute_area_mae(results)
        assert m is None


class TestHeightMAE:
    def test_within_threshold(self):
        results = [_make_result(height_error_m=0.005), _make_result(height_error_m=0.008)]
        m = compute_height_mae(results)
        assert m.value == pytest.approx(0.0065, abs=0.001)
        assert m.status == GateStatus.PASS

    def test_exceeds_threshold(self):
        results = [_make_result(height_error_m=0.05)]
        m = compute_height_mae(results)
        assert m.status == GateStatus.FAIL


class TestPrecision:
    def test_perfect_precision(self):
        results = [_make_result(true_positives=5, false_positives=0)]
        m = compute_precision(results)
        assert m.value == 1.0
        assert m.status == GateStatus.PASS

    def test_low_precision(self):
        results = [_make_result(true_positives=1, false_positives=10)]
        m = compute_precision(results)
        assert m.value < 0.95
        assert m.status == GateStatus.FAIL

    def test_no_data(self):
        results = [_make_result(true_positives=0, false_positives=0)]
        m = compute_precision(results)
        assert m is None


class TestRecall:
    def test_perfect_recall(self):
        results = [_make_result(true_positives=5, false_negatives=0)]
        m = compute_recall(results)
        assert m.value == 1.0
        assert m.status == GateStatus.PASS

    def test_low_recall(self):
        results = [_make_result(true_positives=1, false_negatives=10)]
        m = compute_recall(results)
        assert m.value < 0.90
        assert m.status == GateStatus.FAIL


class TestEvaluateAll:
    def test_all_pass(self):
        results = [
            _make_result(
                area_error_pct=0.1,
                height_error_m=0.005,
                true_positives=10,
                false_positives=0,
                false_negatives=0,
                ingestion_time_ms=100,
                validation_time_ms=50,
            )
        ]
        metrics, gate = evaluate_all(results)
        assert gate == GateStatus.PASS
        assert len(metrics) > 0

    def test_one_fail_triggers_gate_fail(self):
        results = [
            _make_result(
                area_error_pct=5.0,
                height_error_m=0.005,
                true_positives=10,
                false_positives=0,
                false_negatives=0,
            )
        ]
        metrics, gate = evaluate_all(results)
        assert gate == GateStatus.FAIL
