"""KPI evaluator — computes MAE, precision, recall, and performance metrics."""
from __future__ import annotations

import logging
from typing import Optional

from src.app.config import settings
from src.app.benchmark.kpi_models import (
    EntryResult,
    GateStatus,
    MetricResult,
)

logger = logging.getLogger(__name__)


def compute_area_mae(results: list[EntryResult]) -> Optional[MetricResult]:
    """Mean absolute error for area measurements (percentage)."""
    errors = [r.area_error_pct for r in results if r.area_error_pct is not None]
    if not errors:
        return None
    mae = sum(abs(e) for e in errors) / len(errors)
    threshold = settings.kpi_thresholds.area_mae_pct
    return MetricResult(
        name="area_mae_pct",
        value=round(mae, 4),
        threshold=threshold,
        status=GateStatus.PASS if mae <= threshold else GateStatus.FAIL,
        unit="%",
        details={"sample_count": len(errors)},
    )


def compute_height_mae(results: list[EntryResult]) -> Optional[MetricResult]:
    """Mean absolute error for height/distance (meters)."""
    errors = [r.height_error_m for r in results if r.height_error_m is not None]
    if not errors:
        return None
    mae = sum(abs(e) for e in errors) / len(errors)
    threshold = settings.kpi_thresholds.height_mae_m
    return MetricResult(
        name="height_mae_m",
        value=round(mae, 4),
        threshold=threshold,
        status=GateStatus.PASS if mae <= threshold else GateStatus.FAIL,
        unit="m",
        details={"sample_count": len(errors)},
    )


def compute_precision(results: list[EntryResult]) -> Optional[MetricResult]:
    """Precision = TP / (TP + FP)."""
    tp = sum(r.true_positives for r in results)
    fp = sum(r.false_positives for r in results)
    if tp + fp == 0:
        return None
    precision = tp / (tp + fp)
    threshold = settings.kpi_thresholds.precision_min
    return MetricResult(
        name="precision",
        value=round(precision, 4),
        threshold=threshold,
        status=GateStatus.PASS if precision >= threshold else GateStatus.FAIL,
        details={"true_positives": tp, "false_positives": fp},
    )


def compute_recall(results: list[EntryResult]) -> Optional[MetricResult]:
    """Recall = TP / (TP + FN)."""
    tp = sum(r.true_positives for r in results)
    fn = sum(r.false_negatives for r in results)
    if tp + fn == 0:
        return None
    recall = tp / (tp + fn)
    threshold = settings.kpi_thresholds.recall_min
    return MetricResult(
        name="recall",
        value=round(recall, 4),
        threshold=threshold,
        status=GateStatus.PASS if recall >= threshold else GateStatus.FAIL,
        details={"true_positives": tp, "false_negatives": fn},
    )


def compute_avg_ingestion_time(results: list[EntryResult]) -> Optional[MetricResult]:
    times = [r.ingestion_time_ms for r in results if r.ingestion_time_ms > 0]
    if not times:
        return None
    avg = sum(times) / len(times)
    return MetricResult(
        name="avg_ingestion_time_ms",
        value=round(avg, 1),
        threshold=0,
        status=GateStatus.PASS,
        unit="ms",
        details={"sample_count": len(times)},
    )


def compute_avg_validation_time(results: list[EntryResult]) -> Optional[MetricResult]:
    times = [r.validation_time_ms for r in results if r.validation_time_ms > 0]
    if not times:
        return None
    avg = sum(times) / len(times)
    return MetricResult(
        name="avg_validation_time_ms",
        value=round(avg, 1),
        threshold=0,
        status=GateStatus.PASS,
        unit="ms",
        details={"sample_count": len(times)},
    )


def evaluate_all(results: list[EntryResult]) -> tuple[list[MetricResult], GateStatus]:
    """Compute all KPI metrics and determine overall gate status.

    Only entries with baseline_status='gating' affect the pass/fail gate.
    Exploratory entries are still processed for informational metrics but
    their results are reported separately and don't block the gate.
    """
    gating = [r for r in results if r.baseline_status == "gating"]
    exploratory = [r for r in results if r.baseline_status != "gating"]
    metrics: list[MetricResult] = []

    for compute_fn in [
        compute_area_mae,
        compute_height_mae,
        compute_precision,
        compute_recall,
    ]:
        m = compute_fn(gating) if gating else None
        if m is not None:
            m.details["scope"] = "gating"
            metrics.append(m)

    for compute_fn in [compute_avg_ingestion_time, compute_avg_validation_time]:
        m = compute_fn(results)
        if m is not None:
            m.details["scope"] = "all"
            metrics.append(m)

    if exploratory:
        for compute_fn in [compute_precision, compute_recall]:
            m = compute_fn(exploratory)
            if m is not None:
                m.name = f"{m.name}_exploratory"
                m.status = GateStatus.SKIP
                m.details["scope"] = "exploratory"
                metrics.append(m)

    gating_metrics = [m for m in metrics if m.details.get("scope") == "gating"]
    has_failure = any(m.status == GateStatus.FAIL for m in gating_metrics)
    gate = GateStatus.FAIL if has_failure else GateStatus.PASS
    return metrics, gate
