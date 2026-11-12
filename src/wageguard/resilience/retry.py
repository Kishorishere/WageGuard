"""Bounded retry with exponential backoff and a total time budget (spec §16.4).

Policy (spec §16.4):
  * Retry only idempotent transport errors (the `retry_on` whitelist).
  * Hard attempt cap and total time budget.
  * NO retries for verification failures, validation errors, or any
    other non-transport class (`no_silent_fallbacks` — ADR-0021).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from wageguard.resilience.clock import Clock

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    initial_backoff_seconds: float
    backoff_multiplier: float
    total_budget_seconds: float
    retry_on: tuple[type[BaseException], ...]


class RetryBudgetExceeded(Exception):  # noqa: N818  policy name from spec §16.4
    """Retry budget exhausted without success; the last exception is chained."""


def with_bounded_retry(
    func: Callable[[], _T],
    *,
    policy: RetryPolicy,
    clock: Clock,
) -> _T:
    if policy.max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {policy.max_attempts}")
    start = clock.monotonic_seconds()
    backoff = policy.initial_backoff_seconds
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func()
        except policy.retry_on as exc:
            last_exc = exc
            elapsed = clock.monotonic_seconds() - start
            if attempt >= policy.max_attempts or elapsed + backoff > policy.total_budget_seconds:
                raise RetryBudgetExceeded(
                    f"retry budget exhausted after {attempt} attempt(s), " f"elapsed={elapsed:.3f}s"
                ) from exc
            clock.sleep(backoff)
            backoff *= policy.backoff_multiplier
    # Unreachable: loop either returns or raises.
    raise RuntimeError("unreachable") from last_exc  # pragma: no cover
