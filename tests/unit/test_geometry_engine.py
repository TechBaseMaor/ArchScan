"""Unit tests for the deterministic geometry engine."""
import pytest
from src.app.engine.geometry_engine import (
    check_maximum,
    check_minimum,
    compare_area,
    compare_distance,
    compare_angle,
    compute_area_polygon,
    compute_distance,
    compute_distance_3d,
)


class TestCompareDistance:
    def test_within_tolerance(self):
        result = compare_distance(5.005, 5.0)
        assert result.within_tolerance is True

    def test_outside_tolerance(self):
        result = compare_distance(5.02, 5.0)
        assert result.within_tolerance is False

    def test_exact_match(self):
        result = compare_distance(3.0, 3.0)
        assert result.within_tolerance is True
        assert result.difference == 0.0

    def test_negative_difference(self):
        result = compare_distance(4.99, 5.0)
        assert result.within_tolerance is True
        assert result.difference < 0


class TestCompareArea:
    def test_within_tolerance(self):
        result = compare_area(100.4, 100.0)
        assert result.within_tolerance is True

    def test_outside_tolerance(self):
        result = compare_area(101.0, 100.0)
        assert result.within_tolerance is False

    def test_zero_reference(self):
        result = compare_area(0.0, 0.0)
        assert result.within_tolerance is True


class TestCompareAngle:
    def test_within_tolerance(self):
        result = compare_angle(90.3, 90.0)
        assert result.within_tolerance is True

    def test_outside_tolerance(self):
        result = compare_angle(91.0, 90.0)
        assert result.within_tolerance is False


class TestCheckMinimum:
    def test_above_minimum(self):
        result = check_minimum(3.5, 3.0)
        assert result.within_tolerance is True

    def test_below_minimum(self):
        result = check_minimum(2.5, 3.0)
        assert result.within_tolerance is False

    def test_at_minimum_within_tolerance(self):
        result = check_minimum(2.995, 3.0)
        assert result.within_tolerance is True


class TestCheckMaximum:
    def test_below_maximum(self):
        result = check_maximum(3.5, 4.0)
        assert result.within_tolerance is True

    def test_above_maximum(self):
        result = check_maximum(4.5, 4.0)
        assert result.within_tolerance is False

    def test_at_maximum_within_tolerance(self):
        result = check_maximum(4.005, 4.0)
        assert result.within_tolerance is True


class TestComputeAreaPolygon:
    def test_square(self):
        coords = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert compute_area_polygon(coords) == pytest.approx(100.0)

    def test_triangle(self):
        coords = [(0, 0), (4, 0), (0, 3)]
        assert compute_area_polygon(coords) == pytest.approx(6.0)

    def test_degenerate(self):
        assert compute_area_polygon([(0, 0), (1, 1)]) == 0.0
        assert compute_area_polygon([]) == 0.0


class TestComputeDistance:
    def test_horizontal(self):
        assert compute_distance((0, 0), (3, 0)) == pytest.approx(3.0)

    def test_diagonal(self):
        assert compute_distance((0, 0), (3, 4)) == pytest.approx(5.0)

    def test_3d(self):
        assert compute_distance_3d((0, 0, 0), (1, 2, 2)) == pytest.approx(3.0)
