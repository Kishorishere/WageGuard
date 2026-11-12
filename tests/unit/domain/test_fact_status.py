"""FactStatus is a closed enum covering the four lifecycle states."""

from __future__ import annotations

from wageguard.domain.fact_status import FactStatus


def test_closed_set() -> None:
    assert set(FactStatus) == {
        FactStatus.PRESENT,
        FactStatus.MISSING,
        FactStatus.INVALID,
        FactStatus.AMBIGUOUS,
    }


def test_values_are_snake_case() -> None:
    for s in FactStatus:
        assert s.value == s.value.lower()
        assert " " not in s.value
