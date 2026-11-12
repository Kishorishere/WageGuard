"""EffectiveRange: half-open invariants and symmetric overlap (spec §7.5)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wageguard.domain.ranges import EffectiveRange

_dates = st.dates(min_value=date(1900, 1, 1), max_value=date(2099, 12, 31))


@pytest.mark.property
@given(start=_dates, length=st.integers(min_value=1, max_value=10_000))
def test_start_in_range_end_out(start: date, length: int) -> None:
    end = start + timedelta(days=length)
    r = EffectiveRange(start, end)
    assert r.contains(start)
    assert not r.contains(end)
    assert r.contains(start + timedelta(days=length - 1))


@pytest.mark.property
@given(start=_dates)
def test_open_ended_contains_start_and_beyond(start: date) -> None:
    r = EffectiveRange(start, None)
    assert r.contains(start)
    assert r.contains(start + timedelta(days=365_000))
    assert not r.contains(start - timedelta(days=1))


@pytest.mark.property
@given(
    s1=_dates,
    l1=st.integers(min_value=1, max_value=1000),
    s2=_dates,
    l2=st.integers(min_value=1, max_value=1000),
)
def test_overlap_is_symmetric(s1: date, l1: int, s2: date, l2: int) -> None:
    a = EffectiveRange(s1, s1 + timedelta(days=l1))
    b = EffectiveRange(s2, s2 + timedelta(days=l2))
    assert a.overlaps(b) == b.overlaps(a)


@pytest.mark.property
@given(start=_dates, length=st.integers(min_value=1, max_value=1000))
def test_adjacent_ranges_never_overlap(start: date, length: int) -> None:
    mid = start + timedelta(days=length)
    far = mid + timedelta(days=length)
    a = EffectiveRange(start, mid)
    b = EffectiveRange(mid, far)
    assert not a.overlaps(b)
    assert not b.overlaps(a)
