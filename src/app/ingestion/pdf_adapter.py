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
    _extract_opening_mentions(text, revision_id, source_hash, facts)
    _extract_floor_mentions(text, revision_id, source_hash, facts)
    _extract_generic_clauses(text, revision_id, source_hash, facts)

    logger.info("PDF adapter extracted %d facts from %s", len(facts), file_path)
    return facts


def _extract_text(file_path: str) -> str:
    """Try PyMuPDF first (vector PDF), fall back to OCR, then raw bytes."""
    text = _extract_text_pymupdf(file_path)
    if text.strip():
        return text
    text = _extract_text_ocr(file_path)
    if text.strip():
        return text
    return _extract_text_raw(file_path)


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


def _extract_text_raw(file_path: str) -> str:
    """Last-resort: decode the file bytes as text (handles synthetic test PDFs)."""
    try:
        raw = Path(file_path).read_bytes()
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── Pattern-based fact extraction ─────────────────────────────────────────

_AREA_PATTERN = re.compile(
    r'(?:שטח\s*(?:ברוטו|נטו|עיקרי|שירות|כולל)?|'
    r'area|net\s*area|gross\s*area|total\s*area|built\s*area|floor\s*area)'
    r'[:\s]*(\d+[\.,]?\d*)\s*(?:מ"ר|m2|sqm|sq\.?\s*m)',
    re.IGNORECASE,
)

_HEIGHT_PATTERN = re.compile(
    r"(?:גובה(?:\s*(?:תקרה|מבנה|קומה))?|height|clear\s*height|ceiling\s*height|elevation)"
    r"[:\s]*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ')",
    re.IGNORECASE,
)

_SETBACK_PATTERN = re.compile(
    r"(?:קו\s*בניין(?:\s*\S+)?|setback(?:\s*\S+)?|מרחק|distance)"
    r"[:\s]*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ')",
    re.IGNORECASE,
)

_WINDOW_PATTERN = re.compile(
    r'(?:חלונות|חלון|window(?:s)?)'
    r'[:\s]*(?:(\d+[\.,]?\d*)\s*[xX×]\s*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ\'|ס"מ|cm)?'
    r"|(\d+)\s*(?:יח'?|units?|pcs?)?"
    r')',
    re.IGNORECASE,
)

_DOOR_PATTERN = re.compile(
    r'(?:דלתות|דלת|door(?:s)?)'
    r'[:\s]*(?:(\d+[\.,]?\d*)\s*[xX×]\s*(\d+[\.,]?\d*)\s*(?:מטר|m(?:eter)?s?|מ\'|ס"מ|cm)?'
    r"|(\d+)\s*(?:יח'?|units?|pcs?)?"
    r')',
    re.IGNORECASE,
)

_FLOOR_PATTERN = re.compile(
    r"(?:קומה|קומת|floor|level|storey)\s*([\-\w]+)",
    re.IGNORECASE,
)


def _parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _classify_area_subtype(snippet: str) -> str:
    lower = snippet.lower()
    if any(w in lower for w in ("ברוטו", "gross", "כולל")):
        return "gross"
    if any(w in lower for w in ("נטו", "net", "עיקרי")):
        return "net"
    return "unknown"


def _extract_area_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    for match in _AREA_PATTERN.finditer(text):
        snippet = match.group(0).strip()
        subtype = _classify_area_subtype(snippet)
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="area",
                label=f"Area mentioned in document: {snippet}",
                value=_parse_number(match.group(1)),
                unit="m2",
                confidence=0.85,
                extraction_method="regex",
                raw_source_ref=snippet,
                metadata={"subtype": subtype},
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


def _extract_opening_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    for pattern, category, type_label in [
        (_WINDOW_PATTERN, "opening_window", "Window"),
        (_DOOR_PATTERN, "opening_door", "Door"),
    ]:
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            meta: dict = {}
            width_g, height_g, count_g = match.group(1), match.group(2), match.group(3)

            if width_g and height_g:
                w, h = _parse_number(width_g), _parse_number(height_g)
                if w > 10:
                    w, h = w / 100, h / 100
                meta["width_m"] = round(w, 4)
                meta["height_m"] = round(h, 4)
                label = f"{type_label} ({w}x{h}m) mentioned in document"
                value = 1
            elif count_g:
                value = int(count_g)
                label = f"{type_label}: {value} units mentioned in document"
            else:
                value = 1
                label = f"{type_label} mentioned in document"

            facts.append(
                ExtractedFact(
                    revision_id=revision_id,
                    source_hash=source_hash,
                    fact_type=FactType.TEXTUAL,
                    category=category,
                    label=label,
                    value=value,
                    unit="count",
                    confidence=0.7,
                    extraction_method="regex",
                    raw_source_ref=snippet,
                    metadata=meta,
                )
            )


def _extract_floor_mentions(text: str, revision_id: str, source_hash: str, facts: list[ExtractedFact]) -> None:
    seen: set[str] = set()
    for match in _FLOOR_PATTERN.finditer(text):
        floor_label = match.group(1).strip()
        if floor_label.lower() in seen:
            continue
        seen.add(floor_label.lower())
        facts.append(
            ExtractedFact(
                revision_id=revision_id,
                source_hash=source_hash,
                fact_type=FactType.TEXTUAL,
                category="floor_summary",
                label=f"Floor/level reference: {floor_label}",
                value=floor_label,
                unit="",
                confidence=0.65,
                extraction_method="regex",
                raw_source_ref=match.group(0).strip(),
                metadata={"storey_name": floor_label},
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
