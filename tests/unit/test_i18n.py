"""Tests for i18n locale resolution, translation catalog, and deterministic parity."""
import pytest

from src.app.i18n import t, resolve_locale, _CATALOG
from src.app.domain.models import (
    ExtractedFact,
    FactType,
    Rule,
    RuleComputation,
    RulePrecondition,
    RuleSet,
    Severity,
)
from src.app.engine.rule_engine import evaluate_ruleset


class TestTranslationCatalog:
    """Verify that EN and HE catalogs have identical key coverage."""

    def test_all_en_keys_exist_in_he(self):
        missing = set(_CATALOG["en"].keys()) - set(_CATALOG["he"].keys())
        assert not missing, f"Keys missing in HE catalog: {missing}"

    def test_all_he_keys_exist_in_en(self):
        extra = set(_CATALOG["he"].keys()) - set(_CATALOG["en"].keys())
        assert not extra, f"Extra keys in HE catalog not in EN: {extra}"

    def test_no_empty_values_en(self):
        empties = [k for k, v in _CATALOG["en"].items() if not v.strip()]
        assert not empties, f"Empty EN values: {empties}"

    def test_no_empty_values_he(self):
        empties = [k for k, v in _CATALOG["he"].items() if not v.strip()]
        assert not empties, f"Empty HE values: {empties}"


class TestTranslationFunction:
    def test_en_lookup(self):
        assert t("error.project_not_found", "en") == "Project not found"

    def test_he_lookup(self):
        result = t("error.project_not_found", "he")
        assert result != "error.project_not_found"
        assert "לא נמצא" in result

    def test_missing_key_returns_key(self):
        assert t("nonexistent.key.xyz", "en") == "nonexistent.key.xyz"

    def test_param_interpolation_en(self):
        result = t("finding.area_exceeds_max", "en", measured=120.5, max_allowed=100.0, diff="+20.5")
        assert "120.5" in result
        assert "100.0" in result

    def test_param_interpolation_he(self):
        result = t("finding.area_exceeds_max", "he", measured=120.5, max_allowed=100.0, diff="+20.5")
        assert "120.5" in result
        assert "100.0" in result

    def test_fallback_to_en_for_unknown_locale(self):
        result = t("error.project_not_found", "fr")
        assert result == "Project not found"


class TestLocaleResolver:
    def test_explicit_lang_param(self):
        assert resolve_locale(lang="he") == "he"
        assert resolve_locale(lang="en") == "en"

    def test_invalid_lang_param_falls_back(self):
        assert resolve_locale(lang="fr") == "en"

    def test_no_input_defaults_to_en(self):
        assert resolve_locale() == "en"


class TestDeterministicParity:
    """Verify that the same facts+rules produce identical numeric results
    regardless of locale. Only message text should differ."""

    def _run_for_locale(self, locale: str):
        ruleset = RuleSet(
            ruleset_id="parity-test",
            name="Parity Test",
            rules=[
                Rule(
                    rule_id="R1", version="1.0", severity=Severity.ERROR,
                    preconditions=[RulePrecondition(fact_category="area", operator="exists")],
                    computation=RuleComputation(formula="area_max_check", parameters={"max_area": 100}),
                ),
            ],
        )
        facts = [
            ExtractedFact(
                revision_id="rev1",
                source_hash="abc123",
                fact_type=FactType.GEOMETRIC,
                category="area",
                label="test area",
                value=150.0,
                unit="m2",
            ),
        ]
        return evaluate_ruleset(ruleset, facts, "p1", "r1", "v1", locale=locale)

    def test_same_finding_count(self):
        en_findings = self._run_for_locale("en")
        he_findings = self._run_for_locale("he")
        assert len(en_findings) == len(he_findings) == 1

    def test_same_numeric_result(self):
        en_f = self._run_for_locale("en")[0]
        he_f = self._run_for_locale("he")[0]
        assert en_f.computation_trace.result == he_f.computation_trace.result
        assert en_f.computation_trace.inputs["measured"] == he_f.computation_trace.inputs["measured"]
        assert en_f.computation_trace.inputs["max_allowed"] == he_f.computation_trace.inputs["max_allowed"]

    def test_same_severity_and_rule_ref(self):
        en_f = self._run_for_locale("en")[0]
        he_f = self._run_for_locale("he")[0]
        assert en_f.severity == he_f.severity
        assert en_f.rule_ref == he_f.rule_ref

    def test_different_message_text(self):
        en_f = self._run_for_locale("en")[0]
        he_f = self._run_for_locale("he")[0]
        assert en_f.message != he_f.message
        assert "exceeds" in en_f.message
        assert "חורג" in he_f.message

    def test_message_key_preserved_in_trace(self):
        en_f = self._run_for_locale("en")[0]
        assert en_f.computation_trace.inputs.get("message_key") == "finding.area_exceeds_max"
