"""Bounded retry with fake clock (spec §16.4)."""

from __future__ import annotations

import pytest

from wageguard.domain.errors import LlmTimeout, VerificationFailed
from wageguard.resilience.clock import FakeClock
from wageguard.resilience.retry import (
    RetryBudgetExceeded,
    RetryPolicy,
    with_bounded_retry,
)

_POLICY = RetryPolicy(
    max_attempts=3,
    initial_backoff_seconds=0.1,
    backoff_multiplier=2.0,
    total_budget_seconds=1.0,
    retry_on=(LlmTimeout,),
)


def test_success_on_first_attempt_no_sleep() -> None:
    clock = FakeClock()
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        return "ok"

    assert with_bounded_retry(fn, policy=_POLICY, clock=clock) == "ok"
    assert clock.sleeps == []


def test_retries_within_budget_and_eventually_succeeds() -> None:
    clock = FakeClock()
    calls: list[int] = []

    def fn() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise LlmTimeout("nope")
        return "ok"

    assert with_bounded_retry(fn, policy=_POLICY, clock=clock) == "ok"
    assert len(calls) == 3
    # First retry sleeps 0.1, second sleeps 0.2 (backoff * multiplier).
    assert clock.sleeps == [0.1, 0.2]


def test_raises_after_max_attempts_with_cause_chain() -> None:
    clock = FakeClock()

    def fn() -> str:
        raise LlmTimeout("always")

    with pytest.raises(RetryBudgetExceeded) as exc:
        with_bounded_retry(fn, policy=_POLICY, clock=clock)
    assert isinstance(exc.value.__cause__, LlmTimeout)


def test_total_budget_short_circuits_before_last_attempt() -> None:
    clock = FakeClock()
    tight = RetryPolicy(
        max_attempts=10,
        initial_backoff_seconds=0.5,
        backoff_multiplier=2.0,
        total_budget_seconds=0.6,
        retry_on=(LlmTimeout,),
    )

    def fn() -> str:
        raise LlmTimeout("always")

    with pytest.raises(RetryBudgetExceeded):
        with_bounded_retry(fn, policy=tight, clock=clock)
    # Must not have attempted a 10th call.
    assert len(clock.sleeps) < 10


def test_does_not_retry_non_whitelisted_errors() -> None:
    # VerificationFailed is NOT in retry_on; bubbles up on first failure.
    clock = FakeClock()

    def fn() -> str:
        raise VerificationFailed("do not retry me")

    with pytest.raises(VerificationFailed):
        with_bounded_retry(fn, policy=_POLICY, clock=clock)
    assert clock.sleeps == []


def test_invalid_max_attempts_raises() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        with_bounded_retry(lambda: 1, policy=RetryPolicy(0, 0.1, 2.0, 1.0, ()), clock=FakeClock())
