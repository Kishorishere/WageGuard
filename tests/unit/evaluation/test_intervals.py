"""Wilson 95% interval reference values + edge cases (spec §14.9)."""

from __future__ import annotations

import pytest

from wageguard.evaluation.intervals import Z_95, wilson_score_interval


def test_z_95_matches_normal_critical_value() -> None:
    # Standard normal quantile for two-sided 95% is ~1.959963984540054.
    assert abs(Z_95 - 1.959963984540054) < 1e-12


def test_boundary_x_eq_0_has_strictly_positive_upper() -> None:
    # 0 successes in 10 trials: Wilson upper > 0 (unlike the exact
    # binomial, which can be 0 only in a degenerate sense).
    r = wilson_score_interval(x=0, n=10)
    assert r.lower == 0.0
    assert r.upper > 0.0
    assert r.upper < 1.0


def test_boundary_x_eq_n_has_strictly_less_than_one_lower() -> None:
    r = wilson_score_interval(x=10, n=10)
    # Upper is clamped to 1.0 (within floating-point tolerance).
    assert abs(r.upper - 1.0) < 1e-12
    assert r.lower > 0.0
    assert r.lower < 1.0


def test_n_eq_0_returns_full_zero_one_interval() -> None:
    r = wilson_score_interval(x=0, n=0)
    assert r.lower == 0.0
    assert r.upper == 1.0


def test_n_eq_1_x_eq_0() -> None:
    r = wilson_score_interval(x=0, n=1)
    assert r.lower == 0.0
    assert r.upper > 0.0
    # Reference value from statsmodels.stats.proportion.proportion_confint
    # (method='wilson'); upper ~ 0.793.
    assert 0.7 < r.upper < 0.9


def test_n_eq_1_x_eq_1() -> None:
    r = wilson_score_interval(x=1, n=1)
    assert r.upper == 1.0
    assert 0.1 < r.lower < 0.3


def test_reference_value_p_hat_half() -> None:
    # x=50, n=100: Wilson 95% ~ [0.404, 0.596].
    r = wilson_score_interval(x=50, n=100)
    assert abs(r.lower - 0.4038) < 0.01
    assert abs(r.upper - 0.5962) < 0.01


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="wilson"):
        wilson_score_interval(x=-1, n=10)
    with pytest.raises(ValueError, match="wilson"):
        wilson_score_interval(x=11, n=10)
    with pytest.raises(ValueError, match="wilson"):
        wilson_score_interval(x=1, n=-1)
