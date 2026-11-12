"""Wilson score interval (spec §14.4, ADR-0018).

Pure. 95% Wilson interval for a binomial proportion. Handles the
edge cases `x = 0`, `x = n`, and `n = 0` explicitly — the formula
does not collapse to zero width at the boundaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

# 95% two-sided normal critical value.
Z_95: Final = 1.959963984540054


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    lower: float
    upper: float


def wilson_score_interval(x: int, n: int, z: float = Z_95) -> WilsonInterval:
    if n < 0 or x < 0 or x > n:
        raise ValueError(f"wilson: require 0 <= x <= n; got x={x}, n={n}")
    if n == 0:
        # No observations -> any proportion is consistent with the data.
        return WilsonInterval(lower=0.0, upper=1.0)
    p_hat = x / n
    z_sq = z * z
    denom = 1.0 + z_sq / n
    center = (p_hat + z_sq / (2 * n)) / denom
    radicand = (p_hat * (1.0 - p_hat) / n) + (z_sq / (4 * n * n))
    half = (z * math.sqrt(radicand)) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    return WilsonInterval(lower=lower, upper=upper)
