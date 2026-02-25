"""Unit tests for the document-role bundle classifier."""
import pytest

from src.app.domain.models import DocumentRole, SourceFile, SourceFormat
from src.app.ingestion.bundle_classifier import classify_source, classify_filename


class TestRegulationClassification:
    def test_spatial_guidelines_parking(self):
        role, doc_type = classify_filename(
            "הנחיות מרחביות לפיתוח המגרש והסדרי חניה (1).pdf", SourceFormat.PDF
        )
        assert role == DocumentRole.REGULATION
        assert doc_type == "spatial_guidelines"

    def test_spatial_guidelines_building(self):
        role, doc_type = classify_filename(
            "הנחיות מרחביות לתכנון ועיצוב הבניין (מהדורה 7).pdf", SourceFormat.PDF
        )
        assert role == DocumentRole.REGULATION
        assert doc_type == "spatial_guidelines"

    def test_waste_policy(self):
        role, doc_type = classify_filename(
            "מדיניות להיתרי בניה בנושא אצירת אשפה.pdf", SourceFormat.PDF
        )
        assert role == DocumentRole.REGULATION
        assert doc_type == "waste_policy"

    def test_environment_policy(self):
        role, doc_type = classify_filename(
            "מדיניות להיתרי בניה_ בנושא איכות הסביבה.pdf", SourceFormat.PDF
        )
        assert role == DocumentRole.REGULATION
        assert doc_type == "environment_policy"

    def test_green_building_policy(self):
        role, doc_type = classify_filename(
            "תמצית מדיניות בניה ירוקה להיתרי בניה.pdf", SourceFormat.PDF
        )
        assert role == DocumentRole.REGULATION
        assert doc_type == "green_building_policy"

    def test_taba_plan_number(self):
        role, doc_type = classify_filename("3729A.pdf", SourceFormat.PDF)
        assert role == DocumentRole.REGULATION
        assert doc_type == "statutory_plan"

    def test_taba_tashrit(self):
        role, doc_type = classify_filename("3729A_T.pdf", SourceFormat.PDF)
        assert role == DocumentRole.REGULATION
        assert doc_type == "statutory_plan"


class TestSubmissionClassification:
    def test_committee_draft(self):
        role, doc_type = classify_filename("דראפט לועדה.pdf", SourceFormat.PDF)
        assert role == DocumentRole.SUBMISSION
        assert doc_type == "committee_draft"

    def test_building_plan_dwfx(self):
        role, doc_type = classify_filename("תוכנית הגשה 100.dwfx", SourceFormat.DWFX)
        assert role == DocumentRole.SUBMISSION
        assert doc_type == "building_plan"

    def test_area_calculation(self):
        role, doc_type = classify_filename("חישוב שטחים -150.dwfx", SourceFormat.DWFX)
        assert role == DocumentRole.SUBMISSION
        assert doc_type == "area_calculation"

    def test_site_survey(self):
        role, doc_type = classify_filename("מפת מדידה.dwfx", SourceFormat.DWFX)
        assert role == DocumentRole.SUBMISSION
        assert doc_type == "site_survey"

    def test_traffic_appendix(self):
        role, doc_type = classify_filename("נספח תנועה.dwfx", SourceFormat.DWFX)
        assert role == DocumentRole.SUBMISSION
        assert doc_type == "traffic_appendix"


class TestDefaultClassification:
    def test_dwfx_default_is_submission(self):
        role, doc_type = classify_filename("unknown_drawing.dwfx", SourceFormat.DWFX)
        assert role == DocumentRole.SUBMISSION

    def test_ifc_default_is_submission(self):
        role, doc_type = classify_filename("model.ifc", SourceFormat.IFC)
        assert role == DocumentRole.SUBMISSION

    def test_unknown_pdf_is_unknown(self):
        role, doc_type = classify_filename("random_document.pdf", SourceFormat.PDF)
        assert role == DocumentRole.UNKNOWN


class TestSourceFileClassification:
    def test_full_source_file_object(self):
        sf = SourceFile(
            file_name="הנחיות מרחביות לתכנון ועיצוב הבניין (מהדורה 7).pdf",
            source_format=SourceFormat.PDF,
            source_hash="abc123",
            size_bytes=935657,
            stored_path="/tmp/test.pdf",
        )
        role, doc_type = classify_source(sf)
        assert role == DocumentRole.REGULATION
        assert doc_type == "spatial_guidelines"
