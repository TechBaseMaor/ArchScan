"""Deterministic geometry engine — performs calculations with strict tolerance enforcement."""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.app.config import settings


@dataclass(frozen=True)
class ToleranceResult:
    """Outcome of a tolerance-aware comparison."""
    value: float
    reference: float
    difference: float
    within_tolerance: bool
    tolerance_applied: float


def compare_distance(measured: float, reference: float) -> ToleranceResult:
    tol = settings.tolerance.distance_cm / 100.0  # convert cm to m
    diff = measured - reference
    return ToleranceResult(
        value=measured,
        reference=reference,
        difference=diff,
        within_tolerance=abs(diff) <= tol,
        tolerance_applied=tol,
    )


def compare_area(measured: float, reference: float) -> ToleranceResult:
    if reference == 0:
        pct_diff = 0.0 if measured == 0 else float("inf")
    else:
        pct_diff = abs(measured - reference) / reference * 100.0
    tol = settings.tolerance.area_pct
    return ToleranceResult(
        value=measured,
        reference=reference,
        difference=measured - reference,
        within_tolerance=pct_diff <= tol,
        tolerance_applied=tol,
    )


def compare_angle(measured: float, reference: float) -> ToleranceResult:
    diff = measured - reference
    tol = settings.tolerance.angle_deg
    return ToleranceResult(
        value=measured,
        reference=reference,
        difference=diff,
        within_tolerance=abs(diff) <= tol,
        tolerance_applied=tol,
    )


def check_minimum(value: float, minimum: float, tolerance_m: float | None = None) -> ToleranceResult:
    """Check that value >= minimum (with optional tolerance)."""
    tol = tolerance_m if tolerance_m is not None else settings.tolerance.distance_cm / 100.0
    diff = value - minimum
    return ToleranceResult(
        value=value,
        reference=minimum,
        difference=diff,
        within_tolerance=diff >= -tol,
        tolerance_applied=tol,
    )


def check_maximum(value: float, maximum: float, tolerance_m: float | None = None) -> ToleranceResult:
    """Check that value <= maximum (with optional tolerance)."""
    tol = tolerance_m if tolerance_m is not None else settings.tolerance.distance_cm / 100.0
    diff = value - maximum
    return ToleranceResult(
        value=value,
        reference=maximum,
        difference=diff,
        within_tolerance=diff <= tol,
        tolerance_applied=tol,
    )


def compute_area_polygon(coords: list[tuple[float, float]]) -> float:
    """Shoelace formula for simple polygon area."""
    n = len(coords)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2.0


def compute_distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def compute_distance_3d(p1: tuple[float, float, float], p2: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
