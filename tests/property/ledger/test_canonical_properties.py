"""Canonical serialization: property-level invariants (spec §13.8)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wageguard.ledger.canonical import canonical_bytes


@pytest.mark.property
@given(d=st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), min_size=1, max_size=8))
def test_key_order_invariant(d: dict[str, int]) -> None:
    permuted = dict(sorted(d.items(), reverse=True))
    assert canonical_bytes(d) == canonical_bytes(permuted)


@pytest.mark.property
@given(
    a=st.decimals(
        min_value=Decimal("-100"),
        max_value=Decimal("100"),
        allow_nan=False,
        allow_infinity=False,
        places=4,
    )
)
def test_decimal_canonical_is_stable(a: Decimal) -> None:
    assert canonical_bytes(a) == canonical_bytes(a)


@pytest.mark.property
@given(xs=st.lists(st.integers(), min_size=1, max_size=10))
def test_list_order_preserved(xs: list[int]) -> None:
    # Unlike dicts, list element order is semantically meaningful.
    rev = list(reversed(xs))
    if xs == rev:
        assert canonical_bytes(xs) == canonical_bytes(rev)
    else:
        assert canonical_bytes(xs) != canonical_bytes(rev)
