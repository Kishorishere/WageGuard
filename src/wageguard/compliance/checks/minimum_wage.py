"""Minimum-wage engine (spec §9.4).

Pure. Returns an `EngineResult` with the controlling rule, the
candidate rules considered, the exact Decimal comparison values, and
the required passage IDs that must appear in the explanation's
citations. Raises `ConfigurationError` on Ambiguous rule-lookups —
these are ruleset defects, never abstentions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from wageguard.compliance.rules import (
    Ambiguous,
    Found,
    NoRule,
    Rule,
    Ruleset,
    applicable_rule,
)
from wageguard.domain.enums import PayBasis, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId
from wageguard.domain.jurisdiction import Jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged, Passed
from wageguard.domain.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class MinimumWageFacts:
    """Typed subset of RawFacts the engine consumes directly."""

    work_state: Jurisdiction
    work_date: date
    pay_rate: Money
    pay_basis: PayBasis
    worker_category: WorkerCategory


@dataclass(frozen=True, slots=True)
class EngineResult:
    verdict: Passed | Flagged
    controlling_rule: Rule
    candidate_rules: tuple[Rule, ...]
    controlling_rate: Money
    actual_rate: Money
    shortfall: Money | None
    required_passages: tuple[PassageId, ...]
    reason_codes: tuple[ReasonCode, ...]


def evaluate_minimum_wage(
    facts: MinimumWageFacts,
    rules: Ruleset,
    *,
    federal_code: Jurisdiction,
) -> EngineResult:
    reason_codes: list[ReasonCode] = []
    candidates: list[Rule] = []

    state_lookup = applicable_rule(
        rules,
        jurisdiction=facts.work_state,
        topic=Topic.MINIMUM_WAGE,
        category=facts.worker_category,
        on=facts.work_date,
    )
    match state_lookup:
        case Found(rule=state_rule):
            candidates.append(state_rule)
        case NoRule():
            # Legitimate "federal controls" path (spec §9.4 step 3).
            reason_codes.append(ReasonCode.STATE_RULE_ABSENT_FEDERAL_APPLIES)
        case Ambiguous(rules=amb):
            ids = ", ".join(str(r.rule_id) for r in amb)
            raise ConfigurationError(f"ambiguous state rules for {facts.work_state}: {ids}")

    federal_lookup = applicable_rule(
        rules,
        jurisdiction=federal_code,
        topic=Topic.MINIMUM_WAGE,
        category=facts.worker_category,
        on=facts.work_date,
    )
    match federal_lookup:
        case Found(rule=fed_rule):
            candidates.append(fed_rule)
        case NoRule():
            raise ConfigurationError(f"no federal minimum-wage rule covers {facts.work_date}")
        case Ambiguous(rules=amb):
            ids = ", ".join(str(r.rule_id) for r in amb)
            raise ConfigurationError(f"ambiguous federal rules: {ids}")

    # Highest applicable rate controls (ADR-0007).
    def _rate_key(r: Rule) -> Decimal:
        return r.value

    controlling = max(candidates, key=_rate_key)
    controlling_rate = Money(controlling.value)

    if facts.pay_rate >= controlling_rate:
        verdict: Passed | Flagged = Passed()
        shortfall: Money | None = None
    else:
        verdict = Flagged()
        shortfall = controlling_rate - facts.pay_rate

    return EngineResult(
        verdict=verdict,
        controlling_rule=controlling,
        candidate_rules=tuple(candidates),
        controlling_rate=controlling_rate,
        actual_rate=facts.pay_rate,
        shortfall=shortfall,
        required_passages=controlling.supporting_passages,
        reason_codes=tuple(reason_codes),
    )
