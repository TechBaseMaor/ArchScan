"""Unit tests for the DWFx ingestion adapter."""
import io
import zipfile
import pytest
from pathlib import Path

from src.app.domain.models import DocumentRole
from src.app.ingestion.dwfx_adapter import (
    extract_facts_from_dwfx,
    _extract_glyphs_text,
)


REV_ID = "rev-test"
HASH = "hash-dwfx"


def _create_minimal_dwfx(tmp_path: Path, sheets: int = 1, glyphs_text: str = "") -> Path:
    """Create a minimal DWFx ZIP file for testing."""
    dwfx_path = tmp_path / "test.dwfx"

    with zipfile.ZipFile(dwfx_path, "w") as zf:
        pages_xml = ""
        for i in range(sheets):
            pages_xml += f'<PageContent Source="/dwf/doc/sections/s{i}/FixedPage.fpage" Width="7559" Height="3420"/>'

            fpage_content = '<?xml version="1.0" encoding="utf-8"?><FixedPage xmlns="http://schemas.microsoft.com/xps/2005/06">'
            if glyphs_text and i == 0:
                fpage_content += f'<Glyphs UnicodeString="{glyphs_text}" />'
            fpage_content += "</FixedPage>"
            zf.writestr(f"dwf/doc/sections/s{i}/FixedPage.fpage", fpage_content)

        fdoc = f'<?xml version="1.0" encoding="utf-8"?><FixedDocument xmlns="http://schemas.microsoft.com/xps/2005/06">{pages_xml}</FixedDocument>'
        zf.writestr("dwf/doc/FixedDocument.fdoc", fdoc)

    return dwfx_path


class TestSheetMetadata:
    def test_single_sheet(self, tmp_path):
        path = _create_minimal_dwfx(tmp_path, sheets=1)
        facts = extract_facts_from_dwfx(str(path), REV_ID, HASH)
        sheet_facts = [f for f in facts if f.category == "sheet_info"]
        assert len(sheet_facts) == 1
        assert sheet_facts[0].value == 1

    def test_multiple_sheets(self, tmp_path):
        path = _create_minimal_dwfx(tmp_path, sheets=3)
        facts = extract_facts_from_dwfx(str(path), REV_ID, HASH)
        sheet_facts = [f for f in facts if f.category == "sheet_info"]
        assert len(sheet_facts) == 1
        assert sheet_facts[0].value == 3

    def test_sheet_dimensions(self, tmp_path):
        path = _create_minimal_dwfx(tmp_path, sheets=1)
        facts = extract_facts_from_dwfx(str(path), REV_ID, HASH)
        dim_facts = [f for f in facts if f.category == "sheet_dimensions"]
        assert len(dim_facts) == 1
        assert dim_facts[0].metadata["width_mm"] > 0
        assert dim_facts[0].metadata["height_mm"] > 0


class TestGlyphsExtraction:
    def test_unicode_string_extraction(self):
        xaml = '<Glyphs UnicodeString="שטח: 120" FontUri="/fonts/f1.ttf" />'
        text = _extract_glyphs_text(xaml)
        assert "120" in text

    def test_empty_glyphs(self):
        xaml = '<Glyphs UnicodeString="" FontUri="/fonts/f1.ttf" />'
        text = _extract_glyphs_text(xaml)
        assert text.strip() == ""


class TestTextExtraction:
    def test_area_from_glyphs(self, tmp_path):
        path = _create_minimal_dwfx(tmp_path, glyphs_text="area: 150 m2")
        facts = extract_facts_from_dwfx(str(path), REV_ID, HASH, DocumentRole.SUBMISSION)
        area_facts = [f for f in facts if f.category == "area"]
        assert len(area_facts) >= 1
        assert area_facts[0].value == 150.0


class TestMissingFile:
    def test_nonexistent_file(self):
        facts = extract_facts_from_dwfx("/nonexistent/file.dwfx", REV_ID, HASH)
        assert facts == []

    def test_invalid_zip(self, tmp_path):
        bad_file = tmp_path / "bad.dwfx"
        bad_file.write_text("not a zip file")
        facts = extract_facts_from_dwfx(str(bad_file), REV_ID, HASH)
        assert facts == []
