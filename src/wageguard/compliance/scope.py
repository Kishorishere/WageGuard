"""Scope guard (spec §8.5): route out-of-scope cases to NEEDS_LEGAL_REVIEW.

Runs after required-facts resolution. Scope here means categorical
support (worker category, jurisdiction) plus structural scope
(local-ordinance locality, period straddling a rule change).
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from wageguard.compliance.facts import RawFacts
from wageguard.domain.enums import WorkerCategory
from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import NeedsLegalReview
from wageguard.domain.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class ScopeVerdict:
    in_scope: bool
    verdict: NeedsLegalReview | None


def evaluate_scope(
    facts: RawFacts,
    supported_jurisdictions: AbstractSet[str],
) -> ScopeVerdict:
    reasons: list[ReasonCode] = []

    worker_category = facts.values.get(FieldName.WORKER_CATEGORY)
    if (
        isinstance(worker_category, WorkerCategory)
        and worker_category is not WorkerCategory.GENERAL
    ):
        reasons.append(ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY)

    work_state = facts.values.get(FieldName.WORK_STATE)
    if (
        isinstance(work_state, str)
        and work_state != ""
        and work_state not in supported_jurisdictions
    ):
        reasons.append(ReasonCode.OUT_OF_SCOPE_JURISDICTION)

    locality = facts.values.get(FieldName.LOCALITY)
    if isinstance(locality, str) and locality.strip() != "":
        reasons.append(ReasonCode.LOCAL_RULES_NOT_ENCODED)

    period_start = facts.values.get(FieldName.PERIOD_START)
    period_end = facts.values.get(FieldName.PERIOD_END)
    if period_start is not None and period_end is not None:
        # The MVP evaluates a single work_date; any pay period that
        # spans days routes to legal review until the engine supports it.
        reasons.append(ReasonCode.PERIOD_STRADDLES_RULE_CHANGE)

    if reasons:
        return ScopeVerdict(in_scope=False, verdict=NeedsLegalReview(reasons=tuple(reasons)))
    return ScopeVerdict(in_scope=True, verdict=None)
