"""Extraction coverage audit — runs adapters on pilot corpus and reports gaps.

Produces a structured report of what each adapter extracted per file, which
categories are well-covered vs. missing, and low-confidence clusters.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.app.domain.models import DocumentRole, ExtractedFact, SourceFormat
from src.app.ingestion.pdf_adapter import extract_facts_from_pdf
from src.app.ingestion.dwfx_adapter import extract_facts_from_dwfx
from src.app.pilot.corpus_manifest import CorpusManifest, CorpusEntry

logger = logging.getLogger(__name__)

_EXPECTED_CATEGORIES = {
    "area", "height", "setback", "parking", "dwelling_units",
    "level", "floor_summary", "coverage", "regulatory_threshold",
    "text_clause", "sheet_info", "sheet_dimensions",
}


class FileExtractionResult(BaseModel):
    file_name: str
    source_format: str
    document_role: str
    document_type: str
    total_facts: int = 0
    categories_found: list[str] = Field(default_factory=list)
    categories_missing: list[str] = Field(default_factory=list)
    low_confidence_facts: int = 0
    unknown_category_facts: int = 0
    facts_by_category: dict[str, int] = Field(default_factory=dict)
    sample_values: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class CategoryCoverage(BaseModel):
    category: str
    files_with_data: int = 0
    total_facts: int = 0
    avg_confidence: float = 0.0
    min_confidence: float = 1.0
    sources: list[str] = Field(default_factory=list)


class CoverageReport(BaseModel):
    report_version: str = "1.0"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_files_processed: int = 0
    total_facts_extracted: int = 0
    total_errors: int = 0
    overall_unknown_rate: float = 0.0
    overall_low_confidence_rate: float = 0.0
    file_results: list[FileExtractionResult] = Field(default_factory=list)
    category_coverage: list[CategoryCoverage] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    gap_backlog: list[dict[str, Any]] = Field(default_factory=list)


def _run_adapter(entry: CorpusEntry) -> tuple[list[ExtractedFact], list[str]]:
    """Execute the appropriate adapter for a corpus entry."""
    facts: list[ExtractedFact] = []
    errors: list[str] = []
    dummy_revision = "pilot-audit"
    dummy_hash = entry.file_hash

    try:
        role = DocumentRole(entry.document_role) if entry.document_role != "unknown" else DocumentRole.UNKNOWN
        if entry.source_format == "pdf":
            facts = extract_facts_from_pdf(
                entry.file_path, dummy_revision, dummy_hash,
                document_role=role,
            )
        elif entry.source_format == "dwfx":
            facts = extract_facts_from_dwfx(
                entry.file_path, dummy_revision, dummy_hash,
                document_role=role,
            )
        else:
            errors.append(f"No adapter for format: {entry.source_format}")
    except Exception as exc:
        errors.append(f"Adapter error: {exc}")
        logger.exception("Adapter failed for %s", entry.file_name)

    return facts, errors


def run_coverage_audit(manifest: CorpusManifest) -> CoverageReport:
    """Run all adapters against the manifest and produce a coverage report."""
    file_results: list[FileExtractionResult] = []
    all_facts: list[ExtractedFact] = []
    total_errors = 0
    cat_facts: dict[str, list[ExtractedFact]] = defaultdict(list)

    for entry in manifest.entries:
        facts, errors = _run_adapter(entry)
        total_errors += len(errors)

        facts_by_cat: dict[str, int] = defaultdict(int)
        sample_vals: dict[str, Any] = {}
        low_conf = 0
        unknown_cat = 0

        for f in facts:
            facts_by_cat[f.category] += 1
            cat_facts[f.category].append(f)
            if f.category not in sample_vals:
                sample_vals[f.category] = f.value
            if f.confidence < 0.7:
                low_conf += 1
            if f.category not in _EXPECTED_CATEGORIES:
                unknown_cat += 1

        found_cats = sorted(facts_by_cat.keys())
        role_expected = _expected_for_role(entry.document_role)
        missing_cats = sorted(role_expected - set(found_cats))

        result = FileExtractionResult(
            file_name=entry.file_name,
            source_format=entry.source_format,
            document_role=entry.document_role,
            document_type=entry.document_type,
            total_facts=len(facts),
            categories_found=found_cats,
            categories_missing=missing_cats,
            low_confidence_facts=low_conf,
            unknown_category_facts=unknown_cat,
            facts_by_category=dict(facts_by_cat),
            sample_values=sample_vals,
            errors=errors,
        )
        file_results.append(result)
        all_facts.extend(facts)

    cat_coverage: list[CategoryCoverage] = []
    for cat in sorted(set(list(cat_facts.keys()) + list(_EXPECTED_CATEGORIES))):
        cfacts = cat_facts.get(cat, [])
        confs = [f.confidence for f in cfacts] if cfacts else [0.0]
        sources = sorted({f.metadata.get("source_file", "") for f in cfacts if f.metadata.get("source_file")})
        cat_coverage.append(CategoryCoverage(
            category=cat,
            files_with_data=len({f.source_hash for f in cfacts}),
            total_facts=len(cfacts),
            avg_confidence=sum(confs) / len(confs) if confs else 0.0,
            min_confidence=min(confs) if confs else 0.0,
            sources=sources,
        ))

    globally_missing = sorted(
        _EXPECTED_CATEGORIES - set(cat_facts.keys())
    )

    total_facts = len(all_facts)
    low_conf_total = sum(r.low_confidence_facts for r in file_results)
    unknown_total = sum(r.unknown_category_facts for r in file_results)

    gap_backlog = _build_gap_backlog(cat_coverage, globally_missing, file_results)

    report = CoverageReport(
        total_files_processed=len(file_results),
        total_facts_extracted=total_facts,
        total_errors=total_errors,
        overall_unknown_rate=unknown_total / total_facts if total_facts else 0.0,
        overall_low_confidence_rate=low_conf_total / total_facts if total_facts else 0.0,
        file_results=file_results,
        category_coverage=cat_coverage,
        missing_categories=globally_missing,
        gap_backlog=gap_backlog,
    )

    logger.info(
        "Coverage audit: %d files, %d facts, %d errors, %d missing categories",
        report.total_files_processed,
        report.total_facts_extracted,
        report.total_errors,
        len(globally_missing),
    )
    return report


def _expected_for_role(role: str) -> set[str]:
    """Which categories we expect to find given a document role."""
    if role == "regulation":
        return {"regulatory_threshold", "text_clause", "area", "height", "setback", "parking"}
    elif role == "submission":
        return {"area", "height", "setback", "parking", "dwelling_units", "floor_summary"}
    return set()


_IMPACT_SCORES: dict[str, int] = {
    "area": 10,
    "height": 9,
    "setback": 8,
    "parking": 7,
    "dwelling_units": 6,
    "coverage": 5,
    "floor_summary": 4,
    "regulatory_threshold": 8,
    "text_clause": 3,
    "level": 3,
    "sheet_info": 1,
    "sheet_dimensions": 1,
}


def _build_gap_backlog(
    coverage: list[CategoryCoverage],
    missing: list[str],
    file_results: list[FileExtractionResult],
) -> list[dict[str, Any]]:
    """Prioritized backlog of extraction gaps ranked by business impact."""
    backlog: list[dict[str, Any]] = []

    for cat in missing:
        backlog.append({
            "category": cat,
            "gap_type": "completely_missing",
            "impact_score": _IMPACT_SCORES.get(cat, 2),
            "description": f"No {cat} facts extracted from any document",
            "recommendation": f"Improve adapter patterns for {cat} or add manual labeling",
        })

    for cc in coverage:
        if cc.total_facts > 0 and cc.avg_confidence < 0.5:
            backlog.append({
                "category": cc.category,
                "gap_type": "low_confidence",
                "impact_score": _IMPACT_SCORES.get(cc.category, 2) - 1,
                "description": f"{cc.category} extracted but avg confidence {cc.avg_confidence:.2f}",
                "recommendation": "Review extraction patterns and add validation",
            })

    backlog.sort(key=lambda g: g["impact_score"], reverse=True)
    return backlog


def save_coverage_report(report: CoverageReport, output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Coverage report saved to %s", out)
    return out
