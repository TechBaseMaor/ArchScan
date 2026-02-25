"""Hybrid officiality verifier for regulation documents.

Scores each source file's likelihood of being an official authority document
using a combination of:
  1. Known authority registry matching (filename + metadata patterns)
  2. Structural/content heuristic signals (headers, logos, version, date)
  3. Format and metadata signals

Documents below a confidence threshold are flagged for manual review.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from src.app.domain.models import (
    DocumentRole,
    LegalStatus,
    OfficialityStatus,
    ReadabilityGrade,
    ReviewItem,
    ReviewStatus,
    SourceFile,
)

logger = logging.getLogger(__name__)

AUTO_APPROVE_THRESHOLD = 0.75
MANUAL_REVIEW_THRESHOLD = 0.40

# ── Authority registry ────────────────────────────────────────────────────
# Known patterns for official documents by Israeli municipalities/authorities.

_AUTHORITY_PATTERNS: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(r"הנחיות\s*מרחביות", re.IGNORECASE), "municipal_spatial_directive", 0.90),
    (re.compile(r"מדיניות\s*להיתרי\s*בניה", re.IGNORECASE), "municipal_permit_policy", 0.90),
    (re.compile(r"תמצית\s*מדיניות", re.IGNORECASE), "municipal_policy_summary", 0.85),
    (re.compile(r"תב.?ע", re.IGNORECASE), "statutory_plan", 0.95),
    (re.compile(r"תקנון", re.IGNORECASE), "statutory_regulations", 0.90),
    (re.compile(r"^\d{3,5}[A-Za-zא-ת]?(?:_T)?\.pdf$", re.IGNORECASE), "statutory_plan_number", 0.80),
    (re.compile(r"בניה\s*ירוקה|בנייה\s*ירוקה", re.IGNORECASE), "green_building_policy", 0.85),
    (re.compile(r"אצירת\s*אשפה", re.IGNORECASE), "waste_management_policy", 0.85),
    (re.compile(r"איכות\s*הסביבה", re.IGNORECASE), "environmental_policy", 0.85),
    (re.compile(r"תכנית\s*מתאר", re.IGNORECASE), "master_plan", 0.90),
]

_SUBMISSION_INDICATOR_PATTERNS: List[re.Pattern] = [
    re.compile(r"תוכנית\s*הגשה", re.IGNORECASE),
    re.compile(r"חישוב\s*שטחים", re.IGNORECASE),
    re.compile(r"מפת\s*מדידה", re.IGNORECASE),
    re.compile(r"נספח\s*תנועה", re.IGNORECASE),
    re.compile(r"דראפט", re.IGNORECASE),
]

_LEGAL_STATUS_PATTERNS: List[Tuple[re.Pattern, LegalStatus]] = [
    (re.compile(r"הנחיה\s*מרחבית|הנחיות\s*מרחביות", re.IGNORECASE), LegalStatus.SPATIAL_DIRECTIVE),
    (re.compile(r"מדיניות", re.IGNORECASE), LegalStatus.POLICY),
    (re.compile(r"תקנון|תב.?ע|חוק", re.IGNORECASE), LegalStatus.STATUTORY),
]


def verify_officiality(
    source: SourceFile,
    project_id: str,
    revision_id: str,
) -> Tuple[SourceFile, ReviewItem | None]:
    """Score and set officiality status on a source file.

    Returns the updated source and an optional ReviewItem if manual review is needed.
    """
    if source.document_role != DocumentRole.REGULATION:
        source.officiality_status = OfficialityStatus.VERIFIED_OFFICIAL
        source.officiality_confidence = 1.0
        return source, None

    signals: Dict[str, Any] = {}
    confidence = 0.0

    reg_confidence, reg_type = _check_authority_registry(source.file_name)
    signals["registry_match"] = reg_type or "none"
    signals["registry_confidence"] = reg_confidence
    confidence = max(confidence, reg_confidence)

    struct_score = _check_structural_signals(source)
    signals["structural_score"] = struct_score
    confidence = max(confidence, (confidence + struct_score) / 2)

    format_score = _check_format_signals(source)
    signals["format_score"] = format_score
    confidence = (confidence * 0.7) + (format_score * 0.3)

    submission_penalty = _check_submission_indicators(source.file_name)
    if submission_penalty > 0:
        signals["submission_indicator_penalty"] = submission_penalty
        confidence *= (1.0 - submission_penalty)

    source.officiality_confidence = round(confidence, 3)
    source.officiality_signals = signals
    source.legal_status = _detect_legal_status(source.file_name)
    source.readability_grade = _assess_readability(source)

    review_item = None

    if confidence >= AUTO_APPROVE_THRESHOLD:
        source.officiality_status = OfficialityStatus.VERIFIED_OFFICIAL
        logger.info(
            "Auto-approved officiality for %s (confidence=%.2f)",
            source.file_name, confidence,
        )
    elif confidence >= MANUAL_REVIEW_THRESHOLD:
        source.officiality_status = OfficialityStatus.LIKELY_OFFICIAL
        review_item = ReviewItem(
            project_id=project_id,
            revision_id=revision_id,
            file_name=source.file_name,
            source_hash=source.source_hash,
            review_type="officiality",
            reason=f"Officiality confidence {confidence:.0%} is below auto-approve threshold",
            confidence=confidence,
            status=ReviewStatus.PENDING_REVIEW,
            context=signals,
        )
        logger.info(
            "Flagged %s for manual officiality review (confidence=%.2f)",
            source.file_name, confidence,
        )
    else:
        source.officiality_status = OfficialityStatus.UNVERIFIED
        review_item = ReviewItem(
            project_id=project_id,
            revision_id=revision_id,
            file_name=source.file_name,
            source_hash=source.source_hash,
            review_type="officiality",
            reason=f"Low officiality confidence {confidence:.0%} — likely not an official document",
            confidence=confidence,
            status=ReviewStatus.PENDING_REVIEW,
            context=signals,
        )
        logger.warning(
            "Low officiality for %s (confidence=%.2f) — flagged for review",
            source.file_name, confidence,
        )

    return source, review_item


def _check_authority_registry(filename: str) -> Tuple[float, str | None]:
    """Match filename against known authority document patterns."""
    best_confidence = 0.0
    best_type = None
    for pattern, doc_type, conf in _AUTHORITY_PATTERNS:
        if pattern.search(filename):
            if conf > best_confidence:
                best_confidence = conf
                best_type = doc_type
    return best_confidence, best_type


def _check_structural_signals(source: SourceFile) -> float:
    """Heuristic score from file metadata and naming structure."""
    score = 0.0
    fname = source.file_name.lower()
    if "מהדורה" in fname or "גרסה" in fname or "version" in fname:
        score += 0.15
    if re.search(r"\d{4}", fname):
        score += 0.10
    if source.size_bytes > 500_000:
        score += 0.10
    if source.source_format.value == "pdf":
        score += 0.10
    return min(score, 1.0)


def _check_format_signals(source: SourceFile) -> float:
    """Higher confidence for PDF regulation docs; lower for CAD-like formats."""
    if source.source_format.value == "pdf":
        return 0.7
    if source.source_format.value in ("dwfx", "dwg", "ifc"):
        return 0.2
    return 0.4


def _check_submission_indicators(filename: str) -> float:
    """Penalize if filename looks like a submission document."""
    for pattern in _SUBMISSION_INDICATOR_PATTERNS:
        if pattern.search(filename):
            return 0.6
    return 0.0


def _detect_legal_status(filename: str) -> LegalStatus:
    for pattern, status in _LEGAL_STATUS_PATTERNS:
        if pattern.search(filename):
            return status
    return LegalStatus.UNKNOWN


def _assess_readability(source: SourceFile) -> ReadabilityGrade:
    """Basic readability assessment based on format and size."""
    if source.source_format.value in ("dwfx", "dwg", "ifc"):
        return ReadabilityGrade.MEDIUM
    if source.size_bytes < 1000:
        return ReadabilityGrade.LOW
    return ReadabilityGrade.HIGH
