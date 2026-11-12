"""Pure validators: FactValue -> FactStatus. Table-driven per field."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.domain.enums import PayBasis, WorkerCategory
from wageguard.domain.fact_status import FactStatus
from wageguard.intake.validators import (
    validate_money,
    validate_pay_basis,
    validate_us_state,
    validate_work_date,
    validate_worker_category,
)


class TestUsStateValidator:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, FactStatus.MISSING),
            ("", FactStatus.INVALID),
            ("WA", FactStatus.PRESENT),
            ("CA", FactStatus.PRESENT),
            ("wa", FactStatus.INVALID),  # normalization should uppercase first
            ("Washington", FactStatus.INVALID),
            ("W", FactStatus.INVALID),
            ("WAX", FactStatus.INVALID),
            (42, FactStatus.INVALID),
        ],
    )
    def test_table(self, value: object, expected: FactStatus) -> None:
        assert validate_us_state(value) == expected


class TestWorkDateValidator:
    def test_present(self) -> None:
        assert validate_work_date(date(2024, 7, 1)) == FactStatus.PRESENT

    def test_missing(self) -> None:
        assert validate_work_date(None) == FactStatus.MISSING

    def test_wrong_type(self) -> None:
        assert validate_work_date("2024-07-01") == FactStatus.INVALID


class TestMoneyValidator:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, FactStatus.MISSING),
            (Decimal("15.50"), FactStatus.PRESENT),
            (Decimal("0.01"), FactStatus.PRESENT),
            (Decimal("0"), FactStatus.INVALID),
            (Decimal("-1.00"), FactStatus.INVALID),
            (15.5, FactStatus.INVALID),
            ("15.50", FactStatus.INVALID),
        ],
    )
    def test_table(self, value: object, expected: FactStatus) -> None:
        assert validate_money(value) == expected


class TestPayBasisValidator:
    def test_present(self) -> None:
        assert validate_pay_basis(PayBasis.HOURLY) == FactStatus.PRESENT

    def test_missing(self) -> None:
        assert validate_pay_basis(None) == FactStatus.MISSING

    def test_wrong_type(self) -> None:
        assert validate_pay_basis("hourly") == FactStatus.INVALID


class TestWorkerCategoryValidator:
    def test_general_is_present(self) -> None:
        assert validate_worker_category(WorkerCategory.GENERAL) == FactStatus.PRESENT

    def test_missing(self) -> None:
        assert validate_worker_category(None) == FactStatus.MISSING

    def test_wrong_type(self) -> None:
        assert validate_worker_category("general") == FactStatus.INVALID
