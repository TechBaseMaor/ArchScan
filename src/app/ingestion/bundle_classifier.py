"""Deterministic document-role classifier for permit bundle files.

Classifies each source file as regulation, submission, or supporting based on
filename patterns and lightweight content signals. No AI inference is used.
"""
from __future__ import annotations

import logging
import re
from typing import Tuple

from src.app.domain.models import DocumentRole, SourceFile, SourceFormat

logger = logging.getLogger(__name__)

# ── Filename-based classification rules ─────────────────────────────────────
# Each entry: (compiled regex, DocumentRole, human-readable document_type)

_REGULATION_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"הנחיות\s*מרחביות", re.IGNORECASE), "spatial_guidelines"),
    (re.compile(r"בניה\s*ירוקה|בנייה\s*ירוקה", re.IGNORECASE), "green_building_policy"),
    (re.compile(r"אצירת\s*אשפה", re.IGNORECASE), "waste_policy"),
    (re.compile(r"איכות\s*הסביבה", re.IGNORECASE), "environment_policy"),
    (re.compile(r"מדיניות", re.IGNORECASE), "municipal_policy"),
    (re.compile(r"תמצית", re.IGNORECASE), "policy_summary"),
    (re.compile(r"תקנון", re.IGNORECASE), "statutory_regulations"),
    (re.compile(r"תב.?ע", re.IGNORECASE), "statutory_plan"),
    # Taba plan number pattern (e.g. 3729A.pdf, 3729A_T.pdf)
    (re.compile(r"^\d{3,5}[A-Za-zא-ת]?(?:_T)?\.pdf$", re.IGNORECASE), "statutory_plan"),
]

_SUBMISSION_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"תוכנית\s*הגשה", re.IGNORECASE), "building_plan"),
    (re.compile(r"חישוב\s*שטחים", re.IGNORECASE), "area_calculation"),
    (re.compile(r"מפת\s*מדידה", re.IGNORECASE), "site_survey"),
    (re.compile(r"נספח\s*תנועה", re.IGNORECASE), "traffic_appendix"),
    (re.compile(r"דראפט\s*לו?עדה", re.IGNORECASE), "committee_draft"),
]

# Format-level defaults when no filename pattern matches
_FORMAT_ROLE_DEFAULTS: dict[SourceFormat, DocumentRole] = {
    SourceFormat.DWFX: DocumentRole.SUBMISSION,
    SourceFormat.DWG: DocumentRole.SUBMISSION,
    SourceFormat.IFC: DocumentRole.SUBMISSION,
}


def classify_source(source: SourceFile) -> Tuple[DocumentRole, str]:
    """Return (document_role, document_type) for a source file.

    Classification priority:
    1. Filename pattern match against known regulation patterns
    2. Filename pattern match against known submission patterns
    3. Format-level default (DWFX/DWG/IFC → submission)
    4. Fallback to UNKNOWN
    """
    fname = source.file_name

    for pattern, doc_type in _REGULATION_PATTERNS:
        if pattern.search(fname):
            logger.debug("Classified %s as regulation/%s", fname, doc_type)
            return DocumentRole.REGULATION, doc_type

    for pattern, doc_type in _SUBMISSION_PATTERNS:
        if pattern.search(fname):
            logger.debug("Classified %s as submission/%s", fname, doc_type)
            return DocumentRole.SUBMISSION, doc_type

    default_role = _FORMAT_ROLE_DEFAULTS.get(source.source_format)
    if default_role is not None:
        logger.debug("Classified %s as %s (format default)", fname, default_role.value)
        return default_role, f"{source.source_format.value}_default"

    logger.debug("Classified %s as unknown", fname)
    return DocumentRole.UNKNOWN, ""


def classify_filename(filename: str, source_format: SourceFormat) -> Tuple[DocumentRole, str]:
    """Convenience wrapper for classification without a full SourceFile object."""
    stub = SourceFile(
        file_name=filename,
        source_format=source_format,
        source_hash="",
        size_bytes=0,
        stored_path="",
    )
    return classify_source(stub)
