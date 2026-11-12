"""Normalization: trim, NFC, uppercase state codes. Idempotent by design."""

from __future__ import annotations

import unicodedata

from wageguard.intake.normalize import normalize_check_request


def _model(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"check": "minimum_wage"}
    base.update(overrides)
    return base


def test_strips_surrounding_whitespace_on_strings() -> None:
    out = normalize_check_request(_model(work_state="  wa  "))
    assert out["work_state"] == "WA"


def test_uppercases_two_letter_state_codes() -> None:
    assert normalize_check_request(_model(work_state="wa"))["work_state"] == "WA"
    assert normalize_check_request(_model(work_state="CA"))["work_state"] == "CA"


def test_does_not_uppercase_longer_strings() -> None:
    # The uppercase rule is for the US state code only. Other string
    # fields keep their original casing (modulo trimming).
    out = normalize_check_request(_model(locality="  seattle  "))
    assert out["locality"] == "seattle"


def test_preserves_none() -> None:
    assert normalize_check_request(_model(work_state=None))["work_state"] is None


def test_unicode_nfc_normalization() -> None:
    # Combine 'e' + U+0301 (combining acute); NFC should produce
    # U+00E9 (é precomposed). Non-ASCII in a US state field is still
    # invalid downstream; this test just pins the normalization step.
    decomposed = "e" + "́"
    out = normalize_check_request(_model(locality=decomposed))
    assert out["locality"] == unicodedata.normalize("NFC", decomposed)


def test_is_idempotent() -> None:
    once = normalize_check_request(_model(work_state=" wa ", locality=" café "))
    twice = normalize_check_request({**once, "check": "minimum_wage"})
    assert once == twice


def test_check_field_passes_through() -> None:
    assert normalize_check_request(_model())["check"] == "minimum_wage"
