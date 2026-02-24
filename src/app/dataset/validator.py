"""Dataset integrity validator — checks checksums and completeness."""
from __future__ import annotations

import logging
from pathlib import Path

from src.app.dataset.fetcher import compute_sha256, load_provenance
from src.app.dataset.manifest_models import (
    DatasetManifest,
    DownloadStatus,
)

logger = logging.getLogger(__name__)


class ValidationResult:
    def __init__(self):
        self.total: int = 0
        self.downloaded: int = 0
        self.missing: int = 0
        self.checksum_mismatch: int = 0
        self.failed: int = 0
        self.manual_pending: int = 0
        self.errors: list[str] = []

    @property
    def is_complete(self) -> bool:
        return self.missing == 0 and self.failed == 0 and self.checksum_mismatch == 0

    @property
    def ready_pct(self) -> float:
        return (self.downloaded / self.total * 100) if self.total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "downloaded": self.downloaded,
            "missing": self.missing,
            "checksum_mismatch": self.checksum_mismatch,
            "failed": self.failed,
            "manual_pending": self.manual_pending,
            "is_complete": self.is_complete,
            "ready_pct": round(self.ready_pct, 1),
            "errors": self.errors,
        }


def validate_dataset(manifest: DatasetManifest) -> ValidationResult:
    """Check completeness and integrity of the local dataset."""
    provenance = load_provenance()
    result = ValidationResult()
    result.total = len(manifest.entries)

    for entry in manifest.entries:
        rec = provenance.get(entry.entry_id)
        if not rec:
            result.missing += 1
            result.errors.append(f"{entry.entry_id}: no provenance record")
            continue

        if rec.status == DownloadStatus.DOWNLOADED:
            if rec.local_path and Path(rec.local_path).exists():
                actual = compute_sha256(Path(rec.local_path))
                if entry.expected_checksum and actual != entry.expected_checksum:
                    result.checksum_mismatch += 1
                    result.errors.append(f"{entry.entry_id}: checksum changed since download")
                else:
                    result.downloaded += 1
            else:
                result.missing += 1
                result.errors.append(f"{entry.entry_id}: file missing from disk")
        elif rec.status == DownloadStatus.MANUAL_REQUIRED:
            result.manual_pending += 1
        elif rec.status == DownloadStatus.CHECKSUM_MISMATCH:
            result.checksum_mismatch += 1
            result.errors.append(f"{entry.entry_id}: checksum mismatch")
        elif rec.status == DownloadStatus.FAILED:
            result.failed += 1
            result.errors.append(f"{entry.entry_id}: download failed — {rec.error_message}")
        else:
            result.missing += 1

    return result
