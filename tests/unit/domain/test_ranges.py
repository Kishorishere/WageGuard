"""EffectiveRange is half-open [start, end). Adjacent ranges do NOT overlap (G-02).

The half-open invariant is why compliance dates are unambiguous: a rule
that takes effect on 2024-07-01 and a predecessor that ended on
2024-07-01 tile cleanly; the work date 2024-07-01 belongs to exactly one.
"""

from __future__ import annotations

from datetime import date

import pytest

from wageguard.domain.ranges import EffectiveRange


class TestConstruction:
    def test_closed_range(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert r.start == date(2024, 1, 1)
        assert r.end == date(2024, 12, 31)

    def test_open_ended(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), None)
        assert r.end is None

    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValueError, match="end must be after start"):
            EffectiveRange(date(2024, 12, 31), date(2024, 1, 1))

    def test_zero_length_rejected(self) -> None:
        # [a, a) is empty; half-open semantics require end > start.
        with pytest.raises(ValueError, match="end must be after start"):
            EffectiveRange(date(2024, 1, 1), date(2024, 1, 1))


class TestContains:
    def test_start_is_inclusive(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert r.contains(date(2024, 1, 1))

    def test_end_is_exclusive(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert not r.contains(date(2024, 12, 31))
        assert r.contains(date(2024, 12, 30))

    def test_day_before_start_excluded(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert not r.contains(date(2023, 12, 31))

    def test_open_ended_contains_far_future(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), None)
        assert r.contains(date(9999, 12, 31))

    def test_open_ended_excludes_before_start(self) -> None:
        r = EffectiveRange(date(2024, 1, 1), None)
        assert not r.contains(date(2023, 12, 31))


class TestOverlap:
    @pytest.mark.guarantee("G-02")
    def test_adjacent_ranges_do_not_overlap(self) -> None:
        # G-02: half-open [start, end) means adjacent ranges tile without
        # overlap. [Jan, Jul) and [Jul, Dec) share no date.
        a = EffectiveRange(date(2024, 1, 1), date(2024, 7, 1))
        b = EffectiveRange(date(2024, 7, 1), date(2024, 12, 31))
        assert not a.overlaps(b)
        assert not b.overlaps(a)

    def test_overlapping_closed_ranges(self) -> None:
        a = EffectiveRange(date(2024, 1, 1), date(2024, 7, 1))
        b = EffectiveRange(date(2024, 6, 1), date(2024, 12, 31))
        assert a.overlaps(b)
        assert b.overlaps(a)

    def test_identical_ranges_overlap(self) -> None:
        a = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert a.overlaps(a)

    def test_open_ended_overlap(self) -> None:
        a = EffectiveRange(date(2024, 1, 1), None)
        b = EffectiveRange(date(2024, 6, 1), date(2024, 12, 31))
        assert a.overlaps(b)

    def test_disjoint_ranges(self) -> None:
        a = EffectiveRange(date(2023, 1, 1), date(2023, 12, 31))
        b = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        assert not a.overlaps(b)

    def test_overlap_is_symmetric(self) -> None:
        a = EffectiveRange(date(2024, 1, 1), date(2024, 12, 31))
        b = EffectiveRange(date(2024, 6, 1), None)
        assert a.overlaps(b) == b.overlaps(a)
