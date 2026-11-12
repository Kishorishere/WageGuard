"""Metrics aggregation + undefined-rate edge case (spec §14.3, §14.9, G-19)."""

from __future__ import annotations

import pytest

from wageguard.evaluation.metrics import compute_metrics
from wageguard.evaluation.scoring import Classification


@pytest.mark.guarantee("G-19")
def test_non_abstained_zero_yields_undefined_confidently_wrong_rate() -> None:
    # System abstained on everything. Confidently-wrong rate must be
    # UNDEFINED, not zero — spec §14.3 edge case.
    tally = [Classification.CORRECT_ABSTENTION] * 5
    report = compute_metrics(tally, answerable_cases=0, should_abstain_cases=5)
    assert report.confidently_wrong_rate.rate is None
    assert report.confidently_wrong_rate.denominator == 0


def test_perfect_decisive_rates() -> None:
    tally = [Classification.CORRECT_DECISIVE] * 10
    r = compute_metrics(tally, answerable_cases=10, should_abstain_cases=0)
    assert r.confidently_wrong_rate.rate == 0.0
    assert r.answerable_coverage.rate == 1.0
    assert r.over_abstention_rate.rate == 0.0
    assert r.fault_count == 0


def test_all_confidently_wrong() -> None:
    tally = [Classification.CONFIDENTLY_WRONG] * 7
    r = compute_metrics(tally, answerable_cases=7, should_abstain_cases=0)
    assert r.confidently_wrong_rate.numerator == 7
    assert r.confidently_wrong_rate.denominator == 7
    assert r.confidently_wrong_rate.rate == 1.0


def test_mix_tally_counts_each_class() -> None:
    tally = [
        Classification.CORRECT_DECISIVE,
        Classification.CORRECT_DECISIVE,
        Classification.CONFIDENTLY_WRONG,
        Classification.CORRECT_ABSTENTION,
        Classification.OVER_ABSTENTION,
        Classification.FAULT,
    ]
    r = compute_metrics(tally, answerable_cases=3, should_abstain_cases=1)
    tally_map = dict(r.tally)
    assert tally_map[Classification.CORRECT_DECISIVE] == 2
    assert tally_map[Classification.CONFIDENTLY_WRONG] == 1
    assert tally_map[Classification.FAULT] == 1
    assert r.fault_count == 1
    assert r.confidently_wrong_rate.numerator == 1
    assert r.confidently_wrong_rate.denominator == 3


def test_intervals_present_for_defined_rates() -> None:
    tally = [Classification.CORRECT_DECISIVE] * 5 + [Classification.CONFIDENTLY_WRONG] * 5
    r = compute_metrics(tally, answerable_cases=10, should_abstain_cases=0)
    assert r.confidently_wrong_rate.interval is not None
    assert 0.0 <= r.confidently_wrong_rate.interval.lower <= r.confidently_wrong_rate.rate  # type: ignore[operator]
    assert r.confidently_wrong_rate.rate <= r.confidently_wrong_rate.interval.upper <= 1.0  # type: ignore[operator]
