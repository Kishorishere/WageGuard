"""Money is a frozen Decimal + Currency pair. Float is banned (S-2, G-01).

The one-cent boundary test is the single most important in this module:
a compliance screening system that cannot detect a one-cent shortfall is
useless. Equality and ordering are exact Decimal operations with no
rounding before comparison.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from wageguard.domain.errors import CurrencyMismatchError
from wageguard.domain.money import Currency, Money


class TestConstruction:
    def test_accepts_decimal(self) -> None:
        m = Money(Decimal("1.50"))
        assert m.amount == Decimal("1.50")
        assert m.currency is Currency.USD

    def test_accepts_decimal_string(self) -> None:
        assert Money("1.50") == Money(Decimal("1.50"))

    def test_rejects_float(self) -> None:
        with pytest.raises(TypeError, match="float"):
            Money(1.5)  # type: ignore[arg-type]

    def test_rejects_float_via_string_is_fine(self) -> None:
        # The ban is on float construction; "1.5" (string) stays exact.
        assert Money("0.1") + Money("0.2") == Money("0.3")

    def test_rejects_non_numeric_string(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            Money("abc")

    def test_rejects_non_decimal_non_string_object(self) -> None:
        with pytest.raises(TypeError, match="Money.amount must be"):
            Money([1, 2])  # type: ignore[arg-type]

    def test_rejects_bool(self) -> None:
        # bool is an int subclass but conceptually not a money amount.
        with pytest.raises(TypeError):
            Money(True)  # type: ignore[arg-type]

    @pytest.mark.guarantee("G-01")
    def test_float_rejection_is_a_guarantee(self) -> None:
        # G-01: constructing Money from float raises.
        with pytest.raises(TypeError):
            Money(0.1 + 0.2)  # type: ignore[arg-type]


class TestEqualityAndOrdering:
    def test_equal_amounts_are_equal(self) -> None:
        assert Money("1.50") == Money("1.50")

    def test_different_amounts_not_equal(self) -> None:
        assert Money("1.50") != Money("1.51")

    def test_one_cent_boundary_is_detectable(self) -> None:
        # The system must distinguish a one-cent shortfall. This test is
        # the engine's sanity check in miniature.
        below = Money("15.24")
        at = Money("15.25")
        above = Money("15.26")
        assert below < at < above
        assert above > at > below
        assert not (below >= at)
        assert at <= above

    def test_decimal_precision_is_preserved(self) -> None:
        # Classic float trap: 0.1 + 0.2 == 0.30000000000000004 in float,
        # but Decimal("0.1") + Decimal("0.2") == Decimal("0.3") exactly.
        assert Money("0.1") + Money("0.2") == Money("0.3")

    def test_trailing_zeros_compare_equal(self) -> None:
        # Decimal("1.5") and Decimal("1.50") compare equal.
        assert Money("1.5") == Money("1.50")


class TestArithmetic:
    def test_addition_returns_money(self) -> None:
        total = Money("1.50") + Money("2.25")
        assert isinstance(total, Money)
        assert total == Money("3.75")

    def test_subtraction_returns_money(self) -> None:
        delta = Money("3.75") - Money("1.50")
        assert delta == Money("2.25")

    def test_mixed_currency_addition_raises(self) -> None:
        # Only USD is defined in Phase 1, so to exercise the guardrail
        # we build a second Money whose currency is a different value
        # (bypassing the frozen-dataclass __init__ via object.__setattr__).
        usd = Money("1.00", Currency.USD)
        other = Money("1.00", Currency.USD)
        object.__setattr__(other, "currency", "EUR")
        with pytest.raises(CurrencyMismatchError):
            _ = usd + other


class TestImmutability:
    def test_money_is_frozen(self) -> None:
        m = Money("1.50")
        with pytest.raises((AttributeError, TypeError)):
            m.amount = Decimal("2.00")  # type: ignore[misc]

    def test_money_is_hashable(self) -> None:
        # Frozen dataclasses with no mutable fields are hashable.
        assert hash(Money("1.50")) == hash(Money("1.50"))
        assert len({Money("1.50"), Money("1.50"), Money("1.51")}) == 2
