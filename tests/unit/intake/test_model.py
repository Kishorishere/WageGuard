"""CheckRequestModel is the trust boundary.

Pydantic v2 strict mode plus `extra='forbid'` turn typos and ill-typed
values into Rejection at the edge, before any compliance code runs
(spec §8.2, G-04).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from wageguard.intake.model import CheckRequestModel


class TestExtraForbid:
    def test_unknown_fields_rejected(self) -> None:
        # Typos become errors, not silently-missing facts (G-04).
        with pytest.raises(ValidationError):
            CheckRequestModel.model_validate({"check": "minimum_wage", "paY_rate": "15.00"})

    def test_unknown_field_error_names_the_field(self) -> None:
        try:
            CheckRequestModel.model_validate({"check": "minimum_wage", "nonsense_field": True})
        except ValidationError as e:
            msg = str(e)
            assert "nonsense_field" in msg
        else:
            pytest.fail("expected ValidationError")


class TestTypedFields:
    def test_check_type_required(self) -> None:
        with pytest.raises(ValidationError):
            CheckRequestModel.model_validate({})

    def test_check_type_enum_strict(self) -> None:
        with pytest.raises(ValidationError):
            CheckRequestModel.model_validate({"check": "bogus_check"})

    def test_pay_rate_from_decimal_string(self) -> None:
        m = CheckRequestModel.model_validate({"check": "minimum_wage", "pay_rate": "15.50"})
        assert m.pay_rate == Decimal("15.50")

    def test_pay_rate_rejects_json_float(self) -> None:
        # §8.2: money fields are decimal strings, not JSON floats.
        with pytest.raises(ValidationError):
            CheckRequestModel.model_validate({"check": "minimum_wage", "pay_rate": 15.5})

    def test_work_date_iso_only(self) -> None:
        m = CheckRequestModel.model_validate({"check": "minimum_wage", "work_date": "2024-07-01"})
        assert m.work_date == date(2024, 7, 1)

    def test_work_date_rejects_non_iso(self) -> None:
        with pytest.raises(ValidationError):
            CheckRequestModel.model_validate({"check": "minimum_wage", "work_date": "07/01/2024"})

    def test_pay_basis_enum(self) -> None:
        m = CheckRequestModel.model_validate({"check": "minimum_wage", "pay_basis": "hourly"})
        assert m.pay_basis is not None


class TestNullAbsentPolicy:
    def test_absent_field_is_none(self) -> None:
        m = CheckRequestModel.model_validate({"check": "minimum_wage"})
        assert m.pay_rate is None

    def test_explicit_null_is_none(self) -> None:
        m = CheckRequestModel.model_validate({"check": "minimum_wage", "pay_rate": None})
        assert m.pay_rate is None

    def test_empty_string_on_string_field_preserved(self) -> None:
        # The policy (§8.2): empty string -> INVALID downstream. The
        # model preserves the empty string so the validator can see it.
        m = CheckRequestModel.model_validate({"check": "minimum_wage", "work_state": ""})
        assert m.work_state == ""
