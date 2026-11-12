"""Canonical serialization rules (spec §13.3)."""

from __future__ import annotations

import unicodedata
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

import pytest

from wageguard.ledger.canonical import (
    CANON_VERSION,
    canonical_bytes,
    to_canonical_dict,
    to_canonical_json,
)


class TestVersion:
    def test_canon_version_is_v1(self) -> None:
        assert CANON_VERSION == "canon_v1"


class TestRejectsFloat:
    def test_top_level_float_raises(self) -> None:
        with pytest.raises(ValueError, match="float"):
            to_canonical_dict(1.5)

    def test_nested_float_raises(self) -> None:
        with pytest.raises(ValueError, match="float"):
            to_canonical_dict({"a": [1, 2, 3.14]})


class TestDecimalHandling:
    def test_decimal_serialized_as_string(self) -> None:
        assert to_canonical_dict(Decimal("1.50")) == "1.5000"

    def test_equivalent_decimals_canonicalize_equal(self) -> None:
        assert to_canonical_dict(Decimal("1.5")) == to_canonical_dict(Decimal("1.50"))


class TestDateTime:
    def test_date_iso(self) -> None:
        assert to_canonical_dict(date(2024, 7, 1)) == "2024-07-01"

    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="tz"):
            to_canonical_dict(datetime(2024, 7, 1, 12, 0, 0))  # noqa: DTZ001

    def test_aware_datetime_rfc3339_utc(self) -> None:
        dt = datetime(2024, 7, 1, 12, 30, 45, 123456, tzinfo=UTC)
        canonical = to_canonical_dict(dt)
        assert canonical.endswith("Z")
        assert "2024-07-01" in canonical


class TestEnumAndCollections:
    def test_enum_by_value(self) -> None:
        class X(StrEnum):
            A = "alpha"

        assert to_canonical_dict(X.A) == "alpha"

    def test_tuple_as_array(self) -> None:
        assert to_canonical_dict((1, 2, 3)) == [1, 2, 3]

    def test_set_raises(self) -> None:
        with pytest.raises(ValueError, match="set"):
            to_canonical_dict({1, 2, 3})

    def test_frozenset_raises(self) -> None:
        with pytest.raises(ValueError, match="set"):
            to_canonical_dict(frozenset({1, 2, 3}))


class TestNoneAndStrings:
    def test_none_is_null(self) -> None:
        assert to_canonical_dict(None) is None

    def test_string_nfc_normalized(self) -> None:
        # decomposed 'e' + combining acute
        decomposed = "café"
        canonical = to_canonical_dict(decomposed)
        assert canonical == unicodedata.normalize("NFC", decomposed)


class TestJsonSerialization:
    def test_keys_sorted(self) -> None:
        a = to_canonical_json({"b": 1, "a": 2})
        b = to_canonical_json({"a": 2, "b": 1})
        assert a == b
        # Keys appear in sorted order.
        assert a.index('"a"') < a.index('"b"')

    def test_no_insignificant_whitespace(self) -> None:
        js = to_canonical_json({"a": 1, "b": 2})
        assert " " not in js
        assert "\n" not in js

    def test_bytes_output_is_utf8(self) -> None:
        raw = canonical_bytes({"greeting": "café"})
        assert isinstance(raw, bytes)
        assert raw.decode("utf-8")


class TestKeyOrderInvariance:
    def test_key_insertion_order_does_not_change_output(self) -> None:
        a = canonical_bytes({"x": 1, "y": {"a": 2, "b": 3}})
        b = canonical_bytes({"y": {"b": 3, "a": 2}, "x": 1})
        assert a == b
