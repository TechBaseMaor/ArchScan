"""DWFx ingestion adapter — extracts metadata and structured text from Autodesk DWFx files.

DWFx files are ZIP-based packages (Microsoft OOXML variant) containing XPS-like
fixed pages with vector graphics. Text extraction is best-effort; many DWFx files
from AutoCAD contain only path/glyph data without a searchable text layer.

Extraction strategy:
1. Read manifest/descriptor XML for sheet metadata (title, page count, dimensions)
2. Attempt text extraction from FixedPage XAML content
3. Classify extracted text through the same fact patterns as the PDF adapter
"""
from __future__ import annotations

import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from src.app.domain.models import DocumentRole, ExtractedFact, FactType

logger = logging.getLogger(__name__)


def extract_facts_from_dwfx(
    file_path: str,
    revision_id: str,
    source_hash: str,
    document_role: DocumentRole = DocumentRole.UNKNOWN,
) -> list[ExtractedFact]:
    """Extract facts from a DWFx file."""
    path = Path(file_path)
    if not path.exists():
        logger.warning("DWFx file not found: %s", file_path)
        return []

    facts: list[ExtractedFact] = []

    try:
        with zipfile.ZipFile(path, "r") as zf:
            _extract_sheet_metadata(zf, revision_id, source_hash, facts)
            text = _extract_text_from_pages(zf)
            if text.strip():
                _extract_text_facts(text, revision_id, source_hash, document_role, facts)
    except zipfile.BadZipFile:
        logger.warning("Invalid DWFx (not a valid ZIP): %s", file_path)
    except Exception as exc:
        logger.warning("DWFx extraction failed for %s: %s", file_path, exc)

    logger.info("DWFx adapter extracted %d facts from %s", len(facts), file_path)
    return facts


def _extract_sheet_metadata(
    zf: zipfile.ZipFile,
    revision_id: str,
    source_hash: str,
    facts: list[ExtractedFact],
) -> None:
    """Extract sheet count and page dimensions from FixedDocument."""
    fdoc_entries = [n for n in zf.namelist() if n.endswith("FixedDocument.fdoc")]
    for fdoc_path in fdoc_entries:
        try:
            root = ET.fromstring(zf.read(fdoc_path))
            ns = {"xps": "http://schemas.microsoft.com/xps/2005/06"}
            pages = root.findall(".//xps:PageContent", ns)
            if not pages:
                pages = root.findall(".//{http://schemas.microsoft.com/xps/2005/06}PageContent")

            sheet_count = len(pages)
            if sheet_count > 0:
                facts.append(
                    ExtractedFact(
                        revision_id=revision_id,
                        source_hash=source_hash,
                        fact_type=FactType.GEOMETRIC,
                        category="sheet_info",
                        label=f"DWFx contains {sheet_count} sheet(s)",
                        value=sheet_count,
                        unit="sheets",
                        confidence=1.0,
                        extraction_method="dwfx_manifest",
                        raw_source_ref=fdoc_path,
                    )
                )

            for i, page in enumerate(pages):
                width = page.get("Width")
                height = page.get("Height")
                if width and height:
                    w_mm = float(width) * 25.4 / 96.0
                    h_mm = float(height) * 25.4 / 96.0
                    facts.append(
                        ExtractedFact(
                            revision_id=revision_id,
                            source_hash=source_hash,
                            fact_type=FactType.GEOMETRIC,
                            category="sheet_dimensions",
                            label=f"Sheet {i + 1}: {w_mm:.0f}x{h_mm:.0f} mm",
                            value={"width_mm": round(w_mm, 1), "height_mm": round(h_mm, 1)},
                            unit="mm",
                            confidence=1.0,
                            extraction_method="dwfx_manifest",
                            raw_source_ref=fdoc_path,
                            metadata={"sheet_index": i, "width_mm": round(w_mm, 1), "height_mm": round(h_mm, 1)},
                        )
                    )
        except ET.ParseError:
            logger.debug("Failed to parse FixedDocument: %s", fdoc_path)


def _extract_text_from_pages(zf: zipfile.ZipFile) -> str:
    """Best-effort text extraction from FixedPage XAML content."""
    text_parts: list[str] = []
    fpage_entries = sorted(n for n in zf.namelist() if n.endswith(".fpage"))

    for fpage_path in fpage_entries:
        try:
            content = zf.read(fpage_path).decode("utf-8", errors="replace")
            glyphs = _extract_glyphs_text(content)
            if glyphs:
                text_parts.append(glyphs)
        except Exception as exc:
            logger.debug("Failed to extract text from %s: %s", fpage_path, exc)

    return "\n".join(text_parts)


_UNICODE_INDICES_RE = re.compile(r"UnicodeString\s*=\s*\"([^\"]+)\"", re.IGNORECASE)
_GLYPHS_CONTENT_RE = re.compile(r"<[^>]*Glyphs[^>]*UnicodeString\s*=\s*\"([^\"]+)\"[^>]*/?>", re.IGNORECASE)


def _extract_glyphs_text(xaml_content: str) -> str:
    """Extract UnicodeString attributes from Glyphs elements in XPS/XAML."""
    parts: list[str] = []
    for match in _GLYPHS_CONTENT_RE.finditer(xaml_content):
        text = match.group(1).strip()
        if text and text not in ("", " "):
            text = text.replace("{}", "")
            if text.strip():
                parts.append(text.strip())
    return " ".join(parts)


def _extract_text_facts(
    text: str,
    revision_id: str,
    source_hash: str,
    document_role: DocumentRole,
    facts: list[ExtractedFact],
) -> None:
    """Route extracted text through PDF-style fact extractors based on role."""
    from src.app.ingestion.pdf_adapter import (
        _extract_area_mentions,
        _extract_height_mentions,
        _extract_setback_mentions,
        _extract_floor_mentions,
        _extract_unit_count,
        _extract_parking_count,
        _extract_generic_clauses,
        _extract_regulatory_thresholds,
    )

    if document_role == DocumentRole.REGULATION:
        _extract_regulatory_thresholds(text, revision_id, source_hash, facts)
        _extract_generic_clauses(text, revision_id, source_hash, facts)
    else:
        _extract_area_mentions(text, revision_id, source_hash, facts)
        _extract_height_mentions(text, revision_id, source_hash, facts)
        _extract_setback_mentions(text, revision_id, source_hash, facts)
        _extract_floor_mentions(text, revision_id, source_hash, facts)
        _extract_unit_count(text, revision_id, source_hash, facts)
        _extract_parking_count(text, revision_id, source_hash, facts)
