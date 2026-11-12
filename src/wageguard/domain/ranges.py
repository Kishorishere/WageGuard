"""EffectiveRange: half-open `[start, end)` dated range (spec §7.2, G-02, ADR-0006).

Adjacent ranges tile without overlap — a work date belongs to exactly one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class EffectiveRange:
    start: date
    end: date | None

    def __post_init__(self) -> None:
        if self.end is not None and self.end <= self.start:
            raise ValueError(
                f"EffectiveRange: end must be after start (half-open); "
                f"got start={self.start} end={self.end}"
            )

    def contains(self, d: date) -> bool:
        if d < self.start:
            return False
        if self.end is None:
            return True
        return d < self.end

    def overlaps(self, other: EffectiveRange) -> bool:
        # [a, b) overlaps [c, d) iff a < d and c < b; infinities handled by None.
        a_lt_d = other.end is None or self.start < other.end
        c_lt_b = self.end is None or other.start < self.end
        return a_lt_d and c_lt_b
