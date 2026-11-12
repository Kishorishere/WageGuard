"""Money canonicalization: equal values serialize identically (spec §7.5)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wageguard.domain.money import Currency, Money

_amounts = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)


@pytest.mark.property
@given(a=_amounts)
def test_canonical_string_roundtrip(a: Decimal) -> None:
    m = Money(a, Currency.USD)
    # The canonical string (used by the ledger) must round-trip exactly.
    s = m.to_canonical_string()
    m2 = Money.from_canonical_string(s, Currency.USD)
    assert m == m2


@pytest.mark.property
@given(a=_amounts, b=_amounts)
def test_addition_is_commutative(a: Decimal, b: Decimal) -> None:
    assert Money(a) + Money(b) == Money(b) + Money(a)


@pytest.mark.property
@given(a=_amounts, b=_amounts)
def test_subtraction_reverses_addition(a: Decimal, b: Decimal) -> None:
    m = Money(a)
    assert (m + Money(b)) - Money(b) == m
