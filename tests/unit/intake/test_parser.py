"""The parser is the one function that converts untrusted JSON to RawFacts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.facts import RawFacts
from wageguard.domain.enums import CheckType, PayBasis, WorkerCategory
from wageguard.domain.errors import InputRejected
from wageguard.domain.fields import FieldName
from wageguard.intake.parser import parse_check_request


class TestHappyPath:
    def test_minimum_wage_request_parses(self) -> None:
        raw = (
            '{"check": "minimum_wage", "work_state": "WA", '
            '"work_date": "2024-07-01", "pay_rate": "15.50", '
            '"pay_basis": "hourly", "worker_category": "general"}'
        )
        rf = parse_check_request(raw)
        assert isinstance(rf, RawFacts)
        assert rf.check is CheckType.MINIMUM_WAGE
        assert rf.values[FieldName.WORK_STATE] == "WA"
        assert rf.values[FieldName.WORK_DATE] == date(2024, 7, 1)
        assert rf.values[FieldName.PAY_RATE] == Decimal("15.50")
        assert rf.values[FieldName.PAY_BASIS] is PayBasis.HOURLY
        assert rf.values[FieldName.WORKER_CATEGORY] is WorkerCategory.GENERAL


class TestRejections:
    def test_malformed_json_raises_rejection(self) -> None:
        with pytest.raises(InputRejected):
            parse_check_request("{not: valid}")

    def test_non_object_json_raises_rejection(self) -> None:
        with pytest.raises(InputRejected):
            parse_check_request('["not", "an", "object"]')

    def test_unknown_field_raises_rejection(self) -> None:
        # The error type is Rejection (not Abstention).
        with pytest.raises(InputRejected):
            parse_check_request('{"check": "minimum_wage", "paY_rate": "15"}')

    def test_float_money_raises_rejection(self) -> None:
        with pytest.raises(InputRejected):
            parse_check_request('{"check": "minimum_wage", "pay_rate": 15.5}')

    def test_non_iso_date_raises_rejection(self) -> None:
        with pytest.raises(InputRejected):
            parse_check_request('{"check": "minimum_wage", "work_date": "07/01/2024"}')

    def test_unparseable_decimal_string_raises_rejection(self) -> None:
        with pytest.raises(InputRejected, match="pay_rate"):
            parse_check_request('{"check": "minimum_wage", "pay_rate": "not_a_number"}')


class TestNullAbsentEmptyPolicy:
    def test_absent_field_becomes_none(self) -> None:
        rf = parse_check_request('{"check": "minimum_wage"}')
        assert rf.values.get(FieldName.PAY_RATE) is None

    def test_explicit_null_becomes_none(self) -> None:
        rf = parse_check_request('{"check": "minimum_wage", "pay_rate": null}')
        assert rf.values.get(FieldName.PAY_RATE) is None

    def test_empty_string_is_preserved_for_downstream_validator(self) -> None:
        # Downstream the validator will mark this INVALID (not MISSING).
        rf = parse_check_request('{"check": "minimum_wage", "work_state": ""}')
        assert rf.values.get(FieldName.WORK_STATE) == ""


class TestRejectionCarriesFieldErrors:
    def test_rejection_message_names_problem_fields(self) -> None:
        with pytest.raises(InputRejected) as exc:
            parse_check_request('{"check": "minimum_wage", "pay_rate": 15.5, "work_date": "x"}')
        # Error message must name both offending fields, not just one.
        msg = str(exc.value)
        assert "pay_rate" in msg
        assert "work_date" in msg
