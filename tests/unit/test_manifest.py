"""Unit tests for dataset manifest schema and source registry."""
import pytest
import json
from pathlib import Path

from src.app.dataset.manifest_models import (
    DatasetCategory,
    DatasetEntry,
    DatasetManifest,
    DownloadPolicy,
    GroundTruth,
    ExpectedFinding,
    SourceFormat,
)
from src.app.dataset.source_registry import (
    filter_entries,
    get_entry,
    validate_manifest,
    load_manifest,
    save_manifest,
)


def _make_entry(**overrides) -> DatasetEntry:
    defaults = {
        "entry_id": "test-1",
        "name": "Test Entry",
        "category": DatasetCategory.SIMPLE,
        "source_format": SourceFormat.IFC,
        "source_url": "https://example.com/test.ifc",
        "download_policy": DownloadPolicy.AUTO,
        "ground_truth": GroundTruth(gross_area=100.0),
    }
    defaults.update(overrides)
    return DatasetEntry(**defaults)


class TestManifestSchema:
    def test_valid_entry(self):
        e = _make_entry()
        assert e.entry_id == "test-1"
        assert e.category == DatasetCategory.SIMPLE

    def test_ground_truth_fields(self):
        gt = GroundTruth(gross_area=200.0, max_height=8.5, min_setback=3.0)
        assert gt.gross_area == 200.0
        assert gt.max_height == 8.5

    def test_expected_finding(self):
        ef = ExpectedFinding(rule_id="R1", rule_version="1.0", severity="error", expected=True)
        assert ef.rule_id == "R1"
        assert ef.expected is True

    def test_manifest_serialization(self, tmp_path):
        m = DatasetManifest(entries=[_make_entry()])
        path = tmp_path / "manifest.json"
        save_manifest(m, path)
        loaded = load_manifest(path)
        assert len(loaded.entries) == 1
        assert loaded.entries[0].entry_id == "test-1"


class TestManifestValidation:
    def test_valid_manifest(self):
        m = DatasetManifest(entries=[_make_entry()])
        errors = validate_manifest(m)
        assert errors == []

    def test_duplicate_ids(self):
        m = DatasetManifest(entries=[_make_entry(), _make_entry()])
        errors = validate_manifest(m)
        assert any("Duplicate" in e for e in errors)

    def test_auto_requires_http(self):
        m = DatasetManifest(entries=[_make_entry(source_url="file:///local")])
        errors = validate_manifest(m)
        assert any("http" in e for e in errors)

    def test_non_dirty_needs_ground_truth(self):
        m = DatasetManifest(entries=[_make_entry(ground_truth=None)])
        errors = validate_manifest(m)
        assert any("ground_truth" in e for e in errors)

    def test_dirty_ok_without_ground_truth(self):
        m = DatasetManifest(entries=[
            _make_entry(entry_id="dirty-1", category=DatasetCategory.DIRTY, ground_truth=None)
        ])
        errors = validate_manifest(m)
        assert not any("ground_truth" in e for e in errors)


class TestSourceRegistry:
    def test_filter_by_category(self):
        entries = [
            _make_entry(entry_id="s1", category=DatasetCategory.SIMPLE),
            _make_entry(entry_id="m1", category=DatasetCategory.MEDIUM),
        ]
        m = DatasetManifest(entries=entries)
        result = filter_entries(m, category=DatasetCategory.SIMPLE)
        assert len(result) == 1
        assert result[0].entry_id == "s1"

    def test_filter_by_policy(self):
        entries = [
            _make_entry(entry_id="a1", download_policy=DownloadPolicy.AUTO),
            _make_entry(entry_id="m1", download_policy=DownloadPolicy.MANUAL),
        ]
        m = DatasetManifest(entries=entries)
        result = filter_entries(m, policy=DownloadPolicy.MANUAL)
        assert len(result) == 1

    def test_get_entry(self):
        m = DatasetManifest(entries=[_make_entry(entry_id="find-me")])
        assert get_entry(m, "find-me") is not None
        assert get_entry(m, "not-found") is None
