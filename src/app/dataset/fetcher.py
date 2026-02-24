"""Mixed download pipeline — auto-fetches stable sources, queues manual ones."""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.app.config import settings
from src.app.dataset.manifest_models import (
    DatasetEntry,
    DatasetManifest,
    DownloadPolicy,
    DownloadStatus,
    ProvenanceRecord,
)

logger = logging.getLogger(__name__)


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _category_dir(entry: DatasetEntry) -> Path:
    return settings.golden_dataset_dir / entry.category.value


def _local_file_path(entry: DatasetEntry) -> Path:
    ext = entry.source_format.value
    return _category_dir(entry) / f"{entry.entry_id}.{ext}"


def _provenance_path() -> Path:
    return settings.golden_dataset_dir / "provenance.json"


def load_provenance() -> dict[str, ProvenanceRecord]:
    p = _provenance_path()
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return {k: ProvenanceRecord.model_validate(v) for k, v in raw.items()}


def save_provenance(records: dict[str, ProvenanceRecord]) -> None:
    from src.app.storage.file_repo import _JSONEncoder
    p = _provenance_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v.model_dump() for k, v in records.items()}
    p.write_text(json.dumps(data, cls=_JSONEncoder, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_dataset(
    manifest: DatasetManifest,
    dry_run: bool = False,
    force: bool = False,
) -> list[ProvenanceRecord]:
    """Download/validate all dataset entries per their policy."""
    provenance = load_provenance()
    results: list[ProvenanceRecord] = []

    for entry in manifest.entries:
        existing = provenance.get(entry.entry_id)
        local_path = _local_file_path(entry)

        if not force and existing and existing.status == DownloadStatus.DOWNLOADED and local_path.exists():
            logger.info("Skipping %s — already downloaded", entry.entry_id)
            results.append(existing)
            continue

        if entry.download_policy == DownloadPolicy.MANUAL:
            record = _handle_manual(entry, local_path, dry_run)
        else:
            record = _handle_auto(entry, local_path, dry_run)

        provenance[entry.entry_id] = record
        results.append(record)

    if not dry_run:
        save_provenance(provenance)

    return results


def _handle_auto(entry: DatasetEntry, local_path: Path, dry_run: bool) -> ProvenanceRecord:
    if dry_run:
        return ProvenanceRecord(
            entry_id=entry.entry_id,
            status=DownloadStatus.PENDING,
        )

    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        logger.info("Downloading %s from %s", entry.entry_id, entry.source_url)
        req = urllib.request.Request(entry.source_url, headers={"User-Agent": "ArchScan/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()
        local_path.write_bytes(content)
    except (urllib.error.URLError, OSError) as exc:
        logger.error("Download failed for %s: %s", entry.entry_id, exc)
        return ProvenanceRecord(
            entry_id=entry.entry_id,
            status=DownloadStatus.FAILED,
            error_message=str(exc),
        )

    actual_checksum = compute_sha256(local_path)
    status = DownloadStatus.DOWNLOADED

    if entry.expected_checksum and entry.expected_checksum != actual_checksum:
        logger.warning(
            "Checksum mismatch for %s: expected=%s actual=%s",
            entry.entry_id, entry.expected_checksum, actual_checksum,
        )
        status = DownloadStatus.CHECKSUM_MISMATCH

    return ProvenanceRecord(
        entry_id=entry.entry_id,
        status=status,
        local_path=str(local_path),
        actual_checksum=actual_checksum,
        downloaded_at=datetime.utcnow(),
        file_size_bytes=local_path.stat().st_size,
    )


def _handle_manual(entry: DatasetEntry, local_path: Path, dry_run: bool) -> ProvenanceRecord:
    if local_path.exists():
        actual_checksum = compute_sha256(local_path)
        status = DownloadStatus.DOWNLOADED
        if entry.expected_checksum and entry.expected_checksum != actual_checksum:
            status = DownloadStatus.CHECKSUM_MISMATCH
        return ProvenanceRecord(
            entry_id=entry.entry_id,
            status=status,
            local_path=str(local_path),
            actual_checksum=actual_checksum,
            downloaded_at=datetime.utcnow(),
            file_size_bytes=local_path.stat().st_size,
        )

    logger.info(
        "Manual download required for %s — place file at %s (source: %s)",
        entry.entry_id, local_path, entry.source_url,
    )
    return ProvenanceRecord(
        entry_id=entry.entry_id,
        status=DownloadStatus.MANUAL_REQUIRED,
        local_path=str(local_path),
    )


def get_ready_entries(manifest: DatasetManifest) -> list[tuple[DatasetEntry, Path]]:
    """Return entries that are locally available and verified."""
    provenance = load_provenance()
    ready = []
    for entry in manifest.entries:
        rec = provenance.get(entry.entry_id)
        if rec and rec.status == DownloadStatus.DOWNLOADED and rec.local_path:
            p = Path(rec.local_path)
            if p.exists():
                ready.append((entry, p))
    return ready
