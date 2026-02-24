"""Source registry — loads, validates, and queries the dataset manifest."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from src.app.dataset.manifest_models import (
    DatasetCategory,
    DatasetEntry,
    DatasetManifest,
    DownloadPolicy,
    SourceFormat,
)

logger = logging.getLogger(__name__)


def load_manifest(manifest_path: Path) -> DatasetManifest:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return DatasetManifest.model_validate(raw)


def save_manifest(manifest: DatasetManifest, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    from src.app.storage.file_repo import _JSONEncoder
    manifest_path.write_text(
        json.dumps(manifest.model_dump(), cls=_JSONEncoder, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def validate_manifest(manifest: DatasetManifest) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []
    seen_ids = set()
    for entry in manifest.entries:
        if entry.entry_id in seen_ids:
            errors.append(f"Duplicate entry_id: {entry.entry_id}")
        seen_ids.add(entry.entry_id)

        if not entry.source_url:
            errors.append(f"{entry.entry_id}: missing source_url")

        if entry.download_policy == DownloadPolicy.AUTO and not entry.source_url.startswith("http"):
            errors.append(f"{entry.entry_id}: auto policy requires http(s) URL")

        if entry.ground_truth is None and entry.category != DatasetCategory.DIRTY:
            errors.append(f"{entry.entry_id}: non-dirty entries should have ground_truth")

    return errors


def filter_entries(
    manifest: DatasetManifest,
    category: Optional[DatasetCategory] = None,
    policy: Optional[DownloadPolicy] = None,
    source_format: Optional[SourceFormat] = None,
) -> list[DatasetEntry]:
    results = manifest.entries
    if category:
        results = [e for e in results if e.category == category]
    if policy:
        results = [e for e in results if e.download_policy == policy]
    if source_format:
        results = [e for e in results if e.source_format == source_format]
    return results


def get_entry(manifest: DatasetManifest, entry_id: str) -> Optional[DatasetEntry]:
    for e in manifest.entries:
        if e.entry_id == entry_id:
            return e
    return None
