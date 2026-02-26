"""Corpus inventory and manifest builder for the Alon pilot document set.

Scans a directory of pilot files, classifies each by role/format/discipline,
and produces a structured manifest suitable for coverage audits and ontology seeding.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.app.domain.models import DocumentRole, SourceFormat
from src.app.ingestion.bundle_classifier import classify_filename

logger = logging.getLogger(__name__)

_FORMAT_EXTENSIONS: dict[str, SourceFormat] = {
    ".pdf": SourceFormat.PDF,
    ".dwfx": SourceFormat.DWFX,
    ".dwg": SourceFormat.DWG,
    ".ifc": SourceFormat.IFC,
}

_DISCIPLINE_MAP: dict[str, str] = {
    "statutory_plan": "planning",
    "statutory_regulations": "planning",
    "policy_summary": "planning",
    "spatial_guidelines": "design",
    "green_building_policy": "environment",
    "waste_policy": "environment",
    "environment_policy": "environment",
    "municipal_policy": "policy",
    "building_plan": "architecture",
    "area_calculation": "architecture",
    "site_survey": "survey",
    "traffic_appendix": "traffic",
    "committee_draft": "administration",
}


class CorpusEntry(BaseModel):
    file_name: str
    file_path: str
    size_bytes: int
    source_format: str
    document_role: str
    document_type: str
    discipline: str
    file_hash: str
    quality_notes: list[str] = Field(default_factory=list)


class CorpusManifest(BaseModel):
    manifest_version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_directory: str = ""
    total_files: int = 0
    entries: list[CorpusEntry] = Field(default_factory=list)
    role_summary: dict[str, int] = Field(default_factory=dict)
    format_summary: dict[str, int] = Field(default_factory=dict)
    discipline_summary: dict[str, int] = Field(default_factory=dict)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _detect_format(path: Path) -> SourceFormat | None:
    ext = path.suffix.lower()
    return _FORMAT_EXTENSIONS.get(ext)


def _assess_quality(path: Path, fmt: SourceFormat) -> list[str]:
    notes: list[str] = []
    size = path.stat().st_size
    if size < 1024:
        notes.append("very_small_file")
    if size > 50_000_000:
        notes.append("very_large_file")
    if fmt == SourceFormat.DWFX and size < 10_000:
        notes.append("possibly_empty_dwfx")
    return notes


def build_manifest(corpus_dir: str | Path) -> CorpusManifest:
    """Scan a directory and produce a typed corpus manifest."""
    corpus_path = Path(corpus_dir)
    if not corpus_path.is_dir():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_dir}")

    entries: list[CorpusEntry] = []
    role_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    discipline_counts: dict[str, int] = {}

    for item in sorted(corpus_path.iterdir()):
        if item.is_dir() or item.name.startswith("."):
            continue

        fmt = _detect_format(item)
        if fmt is None:
            logger.warning("Skipping unsupported file: %s", item.name)
            continue

        role, doc_type = classify_filename(item.name, fmt)
        discipline = _DISCIPLINE_MAP.get(doc_type, "unknown")
        quality = _assess_quality(item, fmt)

        entry = CorpusEntry(
            file_name=item.name,
            file_path=str(item.resolve()),
            size_bytes=item.stat().st_size,
            source_format=fmt.value,
            document_role=role.value,
            document_type=doc_type,
            discipline=discipline,
            file_hash=_hash_file(item),
            quality_notes=quality,
        )
        entries.append(entry)

        role_counts[role.value] = role_counts.get(role.value, 0) + 1
        format_counts[fmt.value] = format_counts.get(fmt.value, 0) + 1
        discipline_counts[discipline] = discipline_counts.get(discipline, 0) + 1

    manifest = CorpusManifest(
        source_directory=str(corpus_path.resolve()),
        total_files=len(entries),
        entries=entries,
        role_summary=role_counts,
        format_summary=format_counts,
        discipline_summary=discipline_counts,
    )

    logger.info(
        "Corpus manifest: %d files — roles=%s, formats=%s",
        manifest.total_files,
        role_counts,
        format_counts,
    )
    return manifest


def save_manifest(manifest: CorpusManifest, output_path: str | Path) -> Path:
    """Persist manifest to JSON."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Manifest saved to %s", out)
    return out


def load_manifest(path: str | Path) -> CorpusManifest:
    """Load a previously saved manifest."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return CorpusManifest.model_validate(raw)
