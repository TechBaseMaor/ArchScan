"""Verify frontend locale JSON files have matching keys (no missing translations)."""
import json
import pytest
from pathlib import Path

LOCALES_DIR = Path(__file__).parent.parent.parent / "frontend" / "src" / "shared" / "i18n" / "locales"


@pytest.fixture
def en_keys():
    with open(LOCALES_DIR / "en.json") as f:
        return set(json.load(f).keys())


@pytest.fixture
def he_keys():
    with open(LOCALES_DIR / "he.json") as f:
        return set(json.load(f).keys())


def test_en_file_exists():
    assert (LOCALES_DIR / "en.json").exists()


def test_he_file_exists():
    assert (LOCALES_DIR / "he.json").exists()


def test_all_en_keys_present_in_he(en_keys, he_keys):
    missing = en_keys - he_keys
    assert not missing, f"Keys in en.json but missing in he.json: {missing}"


def test_all_he_keys_present_in_en(en_keys, he_keys):
    extra = he_keys - en_keys
    assert not extra, f"Keys in he.json but missing in en.json: {extra}"


def test_no_empty_en_values():
    with open(LOCALES_DIR / "en.json") as f:
        data = json.load(f)
    empties = [k for k, v in data.items() if not v.strip()]
    assert not empties, f"Empty values in en.json: {empties}"


def test_no_empty_he_values():
    with open(LOCALES_DIR / "he.json") as f:
        data = json.load(f)
    empties = [k for k, v in data.items() if not v.strip()]
    assert not empties, f"Empty values in he.json: {empties}"


def test_valid_json_en():
    with open(LOCALES_DIR / "en.json") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0


def test_valid_json_he():
    with open(LOCALES_DIR / "he.json") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert len(data) > 0
