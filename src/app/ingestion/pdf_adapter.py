"""PDF ingestion adapter — extracts textual facts from vector or scanned PDFs."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from src.app.domain.models import ExtractedFact, FactType

logger = logging.getLogger(__name__)


def extract_facts_from_pdf(file_path: str, revision_id: str, source_hash: str) -> list[ExtractedFact]:
    text = _extract_text(file_path)
    if not text.strip():
        logger.warning("No text extracted from PDF %s", file_path)
        return []

    facts: list[ExtractedFact] = []

    _extract_area_mentions(text, revision_id, source_hash, facts)
    _extract_height_mentions(text, revision_id, source_hash, facts)
    _extract_setback_mentions(text, revision_id, source_hash, facts)
    _extract_generic_clauses(text, revision_id, source_hash, facts)

    logger.info("PDF adapter extracted %d facts from %s", len(facts), file_path)
    return facts


def _extract_text(file_path: str) -> str:
    """Try PyMuPDF first (vector PDF), fall back to OCR via pytesseract."""
    text = _extract_text_pymupdf(file_path)
    if text.strip():
        return text
    return _extract_text_ocr(file_path)


def _extract_text_pymupdf(file_path: str) -> str:
    try:
        import fitz  # pymupdf
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except ImportError:
        logger.warning("pymupdf not installed")
        return ""
    except Exception as exc:
        logger.debug("PyMuPDF extraction failed: %s", exc)
        return ""


def _extract_text_ocr(file_path: str) -> str:
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            pages.append(pytesseract.image_to_string(img, lang="heb+eng"))
        doc.close()
        return "\n".join(pages)
    except ImportError:
        logger.warning("pytesseract/PIL not installed — OCR unavailable")
        return ""
    except Exception as exc:
        logger.debug("OCR extraction failed: %s", exc)
        return ""


# ── Pattern-based fact extraction ─────────────────────────────────────────

_AREA_PATTERN = re.compile(
    r'(?:שטח|area|net\s*area|gross\s*area)[:\s]*(\d+[\.,]?\d*)\s*(?:מ"ר|m2|sqm|sq\.?\s*m)',
    re.IGNORECASE,
)

_HEIGHT_PATTERN = re.compile(
    r"(?:גובה|height|elevation)[:\s]*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ')",
    re.IGNORECASE,
)

_SETBACK_PATTERN = re.compile(
    r"(?:קו\s*בניין|setback|מרחק)[:\s]*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ')",
    re.IGNORECASE,
)


def _parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _extract_area_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    for match in _AREA_PATTERN.finditer(text):
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="area",
                label=f"Area mentioned in document: {match.group(0).strip()}",
                value=_parse_number(match.group(1)),
                unit="m2",
                confidence=0.85,
                extraction_method="regex",
                raw_source_ref=match.group(0).strip(),
            )
        )


def _extract_height_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    for match in _HEIGHT_PATTERN.finditer(text):
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="height",
                label=f"Height mentioned in document: {match.group(0).strip()}",
                value=_parse_number(match.group(1)),
                unit="m",
                confidence=0.85,
                extraction_method="regex",
                raw_source_ref=match.group(0).strip(),
            )
        )


def _extract_setback_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    for match in _SETBACK_PATTERN.finditer(text):
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="setback",
                label=f"Setback mentioned in document: {match.group(0).strip()}",
                value=_parse_number(match.group(1)),
                unit="m",
                confidence=0.85,
                extraction_method="regex",
                raw_source_ref=match.group(0).strip(),
            )
        )


def _extract_generic_clauses(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    """Extract regulatory clause references (e.g. 'סעיף 4.1.2' or 'clause 3.2')."""
    clause_pattern = re.compile(r"(?:סעיף|clause|section)\s*([\d]+(?:\.[\d]+)*)", re.IGNORECASE)
    for match in clause_pattern.finditer(text):
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="text_clause",
                label=f"Clause reference: {match.group(0).strip()}",
                value=match.group(1),
                unit="",
                confidence=0.9,
                extraction_method="regex",
                raw_source_ref=match.group(0).strip(),
            )
        )
