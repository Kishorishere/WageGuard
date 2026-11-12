"""FakeClock + SystemClock Protocol shape."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wageguard.resilience.clock import FakeClock


def test_advance_moves_monotonic_and_wall() -> None:
    c = FakeClock(start=datetime(2024, 1, 1, tzinfo=UTC))
    t0 = c.now_utc()
    m0 = c.monotonic_seconds()
    c.advance(5.0)
    assert (c.now_utc() - t0).total_seconds() == 5.0
    assert c.monotonic_seconds() - m0 == 5.0


def test_sleep_records_and_advances() -> None:
    c = FakeClock()
    c.sleep(0.5)
    c.sleep(1.0)
    assert c.sleeps == [0.5, 1.0]
    assert c.monotonic_seconds() == 1.5


def test_sleep_negative_raises() -> None:
    c = FakeClock()
    with pytest.raises(ValueError, match="FakeClock"):
        c.sleep(-1.0)
