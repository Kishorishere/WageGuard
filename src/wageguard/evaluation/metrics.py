"""Metrics over a sequence of classifications (spec §14.3, G-19).

Every rate reports its numerator and denominator alongside its Wilson
interval. `non_abstained == 0` yields **undefined**, not zero — a
system that abstains on everything must not look clean on the
headline rate (spec §14.3 denominator edge case).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from wageguard.evaluation.intervals import WilsonInterval, wilson_score_interval
from wageguard.evaluation.scoring import Classification


@dataclass(frozen=True, slots=True)
class RateReport:
    numerator: int
    denominator: int
    rate: float | None  # None = undefined (denominator == 0)
    interval: WilsonInterval | None


@dataclass(frozen=True, slots=True)
class MetricsReport:
    total_cases: int
    tally: tuple[tuple[Classification, int], ...]
    confidently_wrong_rate: RateReport
    answerable_coverage: RateReport
    correct_abstention_rate: RateReport
    over_abstention_rate: RateReport
    fault_count: int


def _rate(x: int, n: int) -> RateReport:
    if n == 0:
        return RateReport(numerator=x, denominator=0, rate=None, interval=None)
    return RateReport(
        numerator=x,
        denominator=n,
        rate=x / n,
        interval=wilson_score_interval(x=x, n=n),
    )


def compute_metrics(
    classifications: Sequence[Classification],
    *,
    answerable_cases: int,
    should_abstain_cases: int,
) -> MetricsReport:
    counts = Counter(classifications)
    tally = tuple(sorted(counts.items(), key=lambda kv: kv[0].value))
    correct_decisive = counts.get(Classification.CORRECT_DECISIVE, 0)
    confidently_wrong = counts.get(Classification.CONFIDENTLY_WRONG, 0)
    correct_abstention = counts.get(Classification.CORRECT_ABSTENTION, 0)
    over_abstention = counts.get(Classification.OVER_ABSTENTION, 0)
    fault_count = counts.get(Classification.FAULT, 0)

    non_abstained = correct_decisive + confidently_wrong
    return MetricsReport(
        total_cases=len(classifications),
        tally=tally,
        confidently_wrong_rate=_rate(confidently_wrong, non_abstained),
        answerable_coverage=_rate(correct_decisive, answerable_cases),
        correct_abstention_rate=_rate(correct_abstention, should_abstain_cases),
        over_abstention_rate=_rate(over_abstention, answerable_cases),
        fault_count=fault_count,
    )
