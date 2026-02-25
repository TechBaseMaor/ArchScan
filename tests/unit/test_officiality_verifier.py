"""Unit tests for hybrid officiality verifier."""
import pytest

from src.app.domain.models import (
    DocumentRole,
    LegalStatus,
    OfficialityStatus,
    ReadabilityGrade,
    SourceFile,
    SourceFormat,
)
from src.app.ingestion.officiality_verifier import (
    verify_officiality,
    AUTO_APPROVE_THRESHOLD,
    MANUAL_REVIEW_THRESHOLD,
)


def _src(
    name: str,
    role: DocumentRole = DocumentRole.REGULATION,
    fmt: SourceFormat = SourceFormat.PDF,
    size: int = 1_000_000,
) -> SourceFile:
    return SourceFile(
        file_name=name,
        source_format=fmt,
        source_hash="abc123",
        size_bytes=size,
        stored_path=f"/tmp/{name}",
        document_role=role,
    )


class TestOfficialityAutoApproval:
    def test_known_spatial_guidelines_auto_approved(self):
        source = _src("הנחיות מרחביות לתכנון ועיצוב הבניין (מהדורה 7).pdf")
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL
        assert updated.officiality_confidence >= AUTO_APPROVE_THRESHOLD
        assert review is None

    def test_known_policy_document_auto_approved(self):
        source = _src("מדיניות להיתרי בניה בנושא אצירת אשפה.pdf")
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL
        assert review is None

    def test_statutory_plan_number_approved(self):
        source = _src("3729A.pdf")
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL
        assert updated.officiality_confidence >= AUTO_APPROVE_THRESHOLD

    def test_green_building_policy_approved(self):
        source = _src("תמצית מדיניות בניה ירוקה להיתרי בניה.pdf")
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL


class TestOfficialityReviewTriggering:
    def test_unknown_regulation_doc_triggers_review(self):
        source = _src("unknown_regulation.pdf", size=500)
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status in (
            OfficialityStatus.LIKELY_OFFICIAL,
            OfficialityStatus.UNVERIFIED,
        )
        assert review is not None
        assert review.review_type == "officiality"
        assert review.project_id == "p1"
        assert review.revision_id == "r1"

    def test_small_unknown_file_low_confidence(self):
        source = _src("file.pdf", size=100)
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_confidence < AUTO_APPROVE_THRESHOLD
        assert review is not None


class TestSubmissionDocsSkipVerification:
    def test_submission_doc_auto_verified(self):
        source = _src(
            "תוכנית הגשה 100.dwfx",
            role=DocumentRole.SUBMISSION,
            fmt=SourceFormat.DWFX,
        )
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL
        assert updated.officiality_confidence == 1.0
        assert review is None

    def test_supporting_doc_auto_verified(self):
        source = _src("notes.pdf", role=DocumentRole.SUPPORTING)
        updated, review = verify_officiality(source, "p1", "r1")
        assert updated.officiality_status == OfficialityStatus.VERIFIED_OFFICIAL
        assert review is None


class TestLegalStatusDetection:
    def test_spatial_directive_detected(self):
        source = _src("הנחיות מרחביות לפיתוח המגרש.pdf")
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.legal_status == LegalStatus.SPATIAL_DIRECTIVE

    def test_policy_detected(self):
        source = _src("מדיניות להיתרי בניה בנושא איכות הסביבה.pdf")
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.legal_status == LegalStatus.POLICY

    def test_statutory_detected(self):
        source = _src("תקנון תב\"ע 3729.pdf")
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.legal_status == LegalStatus.STATUTORY


class TestReadabilityGrade:
    def test_pdf_gets_high_readability(self):
        source = _src("policy.pdf", size=100_000)
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.readability_grade == ReadabilityGrade.HIGH

    def test_dwfx_gets_medium_readability(self):
        source = _src("plan.dwfx", fmt=SourceFormat.DWFX, size=100_000)
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.readability_grade == ReadabilityGrade.MEDIUM

    def test_tiny_file_gets_low_readability(self):
        source = _src("tiny.pdf", size=100)
        updated, _ = verify_officiality(source, "p1", "r1")
        assert updated.readability_grade == ReadabilityGrade.LOW


class TestSignalsPopulated:
    def test_signals_dict_populated(self):
        source = _src("הנחיות מרחביות.pdf")
        updated, _ = verify_officiality(source, "p1", "r1")
        signals = updated.officiality_signals
        assert "registry_match" in signals
        assert "registry_confidence" in signals
        assert "structural_score" in signals
        assert "format_score" in signals
