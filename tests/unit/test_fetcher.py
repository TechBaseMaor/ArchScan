"""Unit tests for dataset fetcher and checksum verification."""
import pytest
from pathlib import Path

from src.app.config import settings
from src.app.dataset.manifest_models import (
    DatasetCategory,
    DatasetEntry,
    DatasetManifest,
    DownloadPolicy,
    DownloadStatus,
    GroundTruth,
    SourceFormat,
)
from src.app.dataset.fetcher import (
    compute_sha256,
    sync_dataset,
    load_provenance,
    save_provenance,
)
from src.app.dataset.validator import validate_dataset


def _make_entry(entry_id: str, policy: DownloadPolicy = DownloadPolicy.MANUAL, **kw) -> DatasetEntry:
    defaults = {
        "entry_id": entry_id,
        "name": f"Test {entry_id}",
        "category": DatasetCategory.SIMPLE,
        "source_format": SourceFormat.PDF,
        "source_url": "local://test",
        "download_policy": policy,
        "ground_truth": GroundTruth(gross_area=100.0),
    }
    defaults.update(kw)
    return DatasetEntry(**defaults)


@pytest.fixture(autouse=True)
def setup_dirs(tmp_path):
    old_dir = settings.golden_dataset_dir
    settings.golden_dataset_dir = tmp_path / "golden"
    settings.golden_dataset_dir.mkdir(parents=True, exist_ok=True)
    (settings.golden_dataset_dir / "simple").mkdir(parents=True, exist_ok=True)
    yield
    settings.golden_dataset_dir = old_dir


class TestChecksum:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        h1 = compute_sha256(f)
        h2 = compute_sha256(f)
        assert h1 == h2
        assert len(h1) == 16

    def test_different_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"content a")
        f2.write_bytes(b"content b")
        assert compute_sha256(f1) != compute_sha256(f2)


class TestManualDownload:
    def test_manual_missing_file(self):
        manifest = DatasetManifest(entries=[_make_entry("m1")])
        records = sync_dataset(manifest, dry_run=False)
        assert len(records) == 1
        assert records[0].status == DownloadStatus.MANUAL_REQUIRED

    def test_manual_existing_file(self):
        local_path = settings.golden_dataset_dir / "simple" / "m1.pdf"
        local_path.write_bytes(b"test pdf content")
        manifest = DatasetManifest(entries=[_make_entry("m1")])
        records = sync_dataset(manifest, dry_run=False)
        assert len(records) == 1
        assert records[0].status == DownloadStatus.DOWNLOADED


class TestDryRun:
    def test_dry_run_no_downloads(self):
        manifest = DatasetManifest(entries=[
            _make_entry("d1", policy=DownloadPolicy.AUTO, source_url="https://example.com/test.ifc")
        ])
        records = sync_dataset(manifest, dry_run=True)
        assert len(records) == 1
        assert records[0].status == DownloadStatus.PENDING


class TestProvenancePersistence:
    def test_save_and_load(self):
        from src.app.dataset.manifest_models import ProvenanceRecord
        records = {"e1": ProvenanceRecord(entry_id="e1", status=DownloadStatus.DOWNLOADED)}
        save_provenance(records)
        loaded = load_provenance()
        assert "e1" in loaded
        assert loaded["e1"].status == DownloadStatus.DOWNLOADED


class TestDatasetValidator:
    def test_empty_provenance(self):
        manifest = DatasetManifest(entries=[_make_entry("v1")])
        result = validate_dataset(manifest)
        assert result.missing == 1
        assert not result.is_complete

    def test_complete_dataset(self):
        local_path = settings.golden_dataset_dir / "simple" / "c1.pdf"
        local_path.write_bytes(b"test content")
        manifest = DatasetManifest(entries=[_make_entry("c1")])
        sync_dataset(manifest, dry_run=False)
        result = validate_dataset(manifest)
        assert result.downloaded == 1
        assert result.is_complete
