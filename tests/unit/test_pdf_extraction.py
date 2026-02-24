"""Unit tests for expanded PDF adapter extraction."""
import pytest

from src.app.domain.models import ExtractedFact
from src.app.ingestion.pdf_adapter import (
    _extract_area_mentions,
    _extract_height_mentions,
    _extract_setback_mentions,
    _extract_opening_mentions,
    _extract_floor_mentions,
)

REV_ID = "rev-test"
HASH = "hash123"


def _collect(fn, text: str) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    fn(text, REV_ID, HASH, facts)
    return facts


class TestAreaExtraction:
    def test_basic_area(self):
        facts = _collect(_extract_area_mentions, 'area: 120 m2')
        assert len(facts) == 1
        assert facts[0].value == 120.0
        assert facts[0].unit == "m2"

    def test_gross_area(self):
        facts = _collect(_extract_area_mentions, 'gross area: 250.5 m2')
        assert len(facts) == 1
        assert facts[0].metadata.get("subtype") == "gross"

    def test_net_area(self):
        facts = _collect(_extract_area_mentions, 'net area: 180 sqm')
        assert len(facts) == 1
        assert facts[0].metadata.get("subtype") == "net"

    def test_hebrew_area(self):
        facts = _collect(_extract_area_mentions, 'שטח ברוטו: 200 מ"ר')
        assert len(facts) == 1
        assert facts[0].value == 200.0
        assert facts[0].metadata.get("subtype") == "gross"

    def test_multiple_areas(self):
        text = 'area: 100 m2 net area: 80 m2 gross area: 120 m2'
        facts = _collect(_extract_area_mentions, text)
        assert len(facts) == 3


class TestHeightExtraction:
    def test_basic_height(self):
        facts = _collect(_extract_height_mentions, 'height: 3.5 m')
        assert len(facts) == 1
        assert facts[0].value == 3.5

    def test_ceiling_height(self):
        facts = _collect(_extract_height_mentions, 'ceiling height: 2.7 meters')
        assert len(facts) == 1
        assert facts[0].value == 2.7

    def test_hebrew_height(self):
        facts = _collect(_extract_height_mentions, "גובה תקרה: 3.0 מטר")
        assert len(facts) == 1
        assert facts[0].value == 3.0


class TestOpeningExtraction:
    def test_window_dimensions(self):
        facts = _collect(_extract_opening_mentions, 'window: 1.2 x 1.5 m')
        assert len(facts) == 1
        assert facts[0].category == "opening_window"
        assert facts[0].metadata.get("width_m") == 1.2
        assert facts[0].metadata.get("height_m") == 1.5

    def test_window_count(self):
        facts = _collect(_extract_opening_mentions, 'windows: 6 units')
        assert len(facts) == 1
        assert facts[0].value == 6

    def test_door_dimensions(self):
        facts = _collect(_extract_opening_mentions, 'door: 0.9 x 2.1 m')
        assert len(facts) == 1
        assert facts[0].category == "opening_door"
        assert facts[0].metadata.get("width_m") == 0.9

    def test_hebrew_window(self):
        facts = _collect(_extract_opening_mentions, 'חלון: 120 x 150 cm')
        assert len(facts) == 1
        assert facts[0].metadata.get("width_m") == 1.2
        assert facts[0].metadata.get("height_m") == 1.5


class TestFloorExtraction:
    def test_floor_mention(self):
        facts = _collect(_extract_floor_mentions, 'floor 1')
        assert len(facts) == 1
        assert facts[0].category == "floor_summary"
        assert facts[0].value == "1"

    def test_hebrew_floor(self):
        facts = _collect(_extract_floor_mentions, 'קומה א')
        assert len(facts) == 1

    def test_dedup_floors(self):
        facts = _collect(_extract_floor_mentions, 'floor 1 and floor 1 again')
        assert len(facts) == 1


class TestSetbackExtraction:
    def test_basic_setback(self):
        facts = _collect(_extract_setback_mentions, 'setback: 3.0 m')
        assert len(facts) == 1
        assert facts[0].value == 3.0

    def test_hebrew_setback(self):
        facts = _collect(_extract_setback_mentions, 'קו בניין: 4.5 מטר')
        assert len(facts) == 1
        assert facts[0].value == 4.5
