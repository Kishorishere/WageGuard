"""Clock port + implementations (spec §S-6: inject time, don't read it).

SystemClock reads real UTC time. FakeClock advances only when the
test calls `advance()`; it is used to drive bounded-retry timing
without wall-clock sleeps.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...
    def monotonic_seconds(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    def monotonic_seconds(self) -> float:
        import time

        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)


class FakeClock:
    """Test clock. `advance` moves time forward; `sleep` advances internally."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2024, 1, 1, tzinfo=UTC)
        self._monotonic = 0.0
        self.sleeps: list[float] = []

    def now_utc(self) -> datetime:
        return self._now

    def monotonic_seconds(self) -> float:
        return self._monotonic

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"FakeClock.sleep: seconds must be >= 0, got {seconds}")
        self.sleeps.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._monotonic += seconds
        self._now = self._now + timedelta(seconds=seconds)
