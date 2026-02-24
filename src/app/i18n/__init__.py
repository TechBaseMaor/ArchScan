"""Backend i18n — locale resolution and message catalog for API/findings/reports."""
from __future__ import annotations

from typing import Optional

from fastapi import Request

Locale = str  # "en" | "he"

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        "error.project_not_found": "Project not found",
        "error.revision_not_found": "Revision not found",
        "error.ruleset_not_found": "RuleSet not found",
        "error.validation_not_found": "Validation not found",
        "error.report_not_generated": "Report not yet generated",
        "error.benchmark_not_found": "Benchmark not found",
        "error.manifest_not_found": "Golden dataset manifest not found",
        "error.unsupported_format": "Unsupported file format: {filename}",

        "finding.area_exceeds_max": "Area {measured} m2 exceeds maximum {max_allowed} m2 (diff: {diff} m2)",
        "finding.area_below_min": "Area {measured} m2 below minimum {min_required} m2 (diff: {diff} m2)",
        "finding.height_exceeds_max": "Height {measured} m exceeds maximum {max_allowed} m (diff: {diff} m)",
        "finding.height_below_min": "Height {measured} m below minimum {min_required} m (diff: {diff} m)",
        "finding.setback_below_min": "Setback {measured} m below minimum {min_required} m (diff: {diff} m)",
        "finding.cross_doc_area_mismatch": "Cross-document area mismatch: model={geometric_value} m2 vs document={textual_value} m2 (diff: {diff} m2)",
        "finding.intersection_exceeds_max": "Intersection count {detected} exceeds maximum {max_allowed}",

        "report.title": "ArchScan Validation Report",
        "report.validation_id": "Validation ID",
        "report.project_id": "Project ID",
        "report.revision_id": "Revision ID",
        "report.ruleset_id": "RuleSet ID",
        "report.status": "Status",
        "report.generated": "Generated",
        "report.summary": "Summary",
        "report.total_findings": "Total findings",
        "report.errors": "Errors",
        "report.warnings": "Warnings",
        "report.info": "Info",
        "report.findings_detail": "Findings Detail",
        "report.no_findings": "No findings - all checks passed.",
        "report.message": "Message",
        "report.formula": "Formula",
        "report.inputs": "Inputs",
        "report.result": "Result",
        "report.tolerance": "Tolerance",
        "report.source_hashes": "Source hashes",
        "report.fact_ids": "Fact IDs",
    },
    "he": {
        "error.project_not_found": "הפרויקט לא נמצא",
        "error.revision_not_found": "הרוויזיה לא נמצאה",
        "error.ruleset_not_found": "סט החוקים לא נמצא",
        "error.validation_not_found": "הבדיקה לא נמצאה",
        "error.report_not_generated": "הדוח עדיין לא נוצר",
        "error.benchmark_not_found": "הבנצ'מרק לא נמצא",
        "error.manifest_not_found": "מניפסט מאגר הזהב לא נמצא",
        "error.unsupported_format": "פורמט קובץ לא נתמך: {filename}",

        "finding.area_exceeds_max": "שטח {measured} מ\"ר חורג מהמקסימום {max_allowed} מ\"ר (הפרש: {diff} מ\"ר)",
        "finding.area_below_min": "שטח {measured} מ\"ר מתחת למינימום {min_required} מ\"ר (הפרש: {diff} מ\"ר)",
        "finding.height_exceeds_max": "גובה {measured} מ' חורג מהמקסימום {max_allowed} מ' (הפרש: {diff} מ')",
        "finding.height_below_min": "גובה {measured} מ' מתחת למינימום {min_required} מ' (הפרש: {diff} מ')",
        "finding.setback_below_min": "קו בניין {measured} מ' מתחת למינימום {min_required} מ' (הפרש: {diff} מ')",
        "finding.cross_doc_area_mismatch": "אי-התאמת שטח בין מסמכים: מודל={geometric_value} מ\"ר מול מסמך={textual_value} מ\"ר (הפרש: {diff} מ\"ר)",
        "finding.intersection_exceeds_max": "מספר התנגשויות {detected} חורג מהמקסימום {max_allowed}",

        "report.title": "דוח בדיקת ArchScan",
        "report.validation_id": "מזהה בדיקה",
        "report.project_id": "מזהה פרויקט",
        "report.revision_id": "מזהה רוויזיה",
        "report.ruleset_id": "מזהה סט חוקים",
        "report.status": "סטטוס",
        "report.generated": "נוצר",
        "report.summary": "סיכום",
        "report.total_findings": "סה\"כ ממצאים",
        "report.errors": "שגיאות",
        "report.warnings": "אזהרות",
        "report.info": "מידע",
        "report.findings_detail": "פרטי ממצאים",
        "report.no_findings": "לא נמצאו ממצאים - כל הבדיקות עברו.",
        "report.message": "הודעה",
        "report.formula": "נוסחה",
        "report.inputs": "קלט",
        "report.result": "תוצאה",
        "report.tolerance": "סובלנות",
        "report.source_hashes": "חתימות מקור",
        "report.fact_ids": "מזהי עובדות",
    },
}


def resolve_locale(request: Optional[Request] = None, lang: Optional[str] = None) -> Locale:
    """Resolve locale from explicit param, query string, Accept-Language header, or default."""
    if lang and lang in ("en", "he"):
        return lang

    if request:
        query_lang = request.query_params.get("lang")
        if query_lang in ("en", "he"):
            return query_lang

        accept = request.headers.get("accept-language", "")
        if "he" in accept:
            return "he"

    return "en"


def t(key: str, locale: Locale = "en", **params: object) -> str:
    """Look up a translated string, interpolating parameters."""
    catalog = _CATALOG.get(locale, _CATALOG["en"])
    template = catalog.get(key, _CATALOG["en"].get(key, key))
    if params:
        try:
            return template.format(**params)
        except (KeyError, IndexError):
            return template
    return template
