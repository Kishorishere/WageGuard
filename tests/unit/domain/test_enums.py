"""Shared enums: CheckType, PayBasis, PayPeriod, WorkerCategory."""

from __future__ import annotations

from wageguard.domain.enums import CheckType, PayBasis, PayPeriod, WorkerCategory


def test_check_type_values() -> None:
    assert set(CheckType) == {CheckType.MINIMUM_WAGE, CheckType.EXEMPTION_SALARY}


def test_pay_basis_values() -> None:
    assert set(PayBasis) == {PayBasis.HOURLY, PayBasis.SALARY}


def test_pay_period_values() -> None:
    assert set(PayPeriod) == {
        PayPeriod.WEEKLY,
        PayPeriod.BIWEEKLY,
        PayPeriod.SEMI_MONTHLY,
        PayPeriod.MONTHLY,
    }


def test_worker_category_general_is_present() -> None:
    # Only GENERAL is in the MVP's supported scope; others route to
    # NEEDS_LEGAL_REVIEW via the scope guard (spec §9.6).
    assert WorkerCategory.GENERAL in WorkerCategory


def test_enum_values_are_snake_case() -> None:
    for enum_cls in (CheckType, PayBasis, PayPeriod, WorkerCategory):
        for member in enum_cls:
            assert member.value == member.value.lower(), f"{enum_cls.__name__}.{member.name}"
            assert " " not in member.value
