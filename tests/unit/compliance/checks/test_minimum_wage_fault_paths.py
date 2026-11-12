"""Engine fault paths: missing federal rule and ambiguous federal rules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.checks.minimum_wage import (
    MinimumWageFacts,
    evaluate_minimum_wage,
)
from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import PayBasis, ReviewStatus, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.ranges import EffectiveRange

_FEDERAL = jurisdiction("US")
_PASSAGE = PassageId("fake_src", 1, 0)


def _rule(*, rid: str, jur: str, value: str, start: date, end: date | None = None) -> Rule:
    return Rule(
        rule_id=RuleId(rid),
        jurisdiction=jurisdiction(jur),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal(value),
        unit="USD/hour",
        effective=EffectiveRange(start, end),
        supporting_passages=(_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )


def _facts(state: str = "TESTLAND-A", pay: str = "10.00") -> MinimumWageFacts:
    return MinimumWageFacts(
        work_state=jurisdiction(state),
        work_date=date(2024, 7, 1),
        pay_rate=Money(pay),
        pay_basis=PayBasis.HOURLY,
        worker_category=WorkerCategory.GENERAL,
    )


def test_no_federal_rule_raises_configuration_error() -> None:
    # Only a state rule — no federal rule — on the work date.
    rs = Ruleset.from_rules(
        RulesetVersion("v"),
        (_rule(rid="tla.only", jur="TESTLAND-A", value="10.00", start=date(2020, 1, 1)),),
    )
    with pytest.raises(ConfigurationError, match="no federal"):
        evaluate_minimum_wage(_facts(), rs, federal_code=_FEDERAL)


def test_ambiguous_federal_rules_raises_configuration_error() -> None:
    # Build a Ruleset by hand with two overlapping federal rules —
    # bypass from_rules so the overlap check doesn't catch it first.
    rs = Ruleset.__new__(Ruleset)
    r1 = _rule(rid="us.a", jur="US", value="7.00", start=date(2020, 1, 1), end=None)
    r2 = _rule(rid="us.b", jur="US", value="8.00", start=date(2020, 1, 1), end=None)
    object.__setattr__(rs, "version", RulesetVersion("v"))
    object.__setattr__(rs, "rules", (r1, r2))
    object.__setattr__(rs, "ruleset_hash", "unverified")
    # work_state != US so the state lookup falls through to federal.
    with pytest.raises(ConfigurationError, match="ambiguous federal"):
        evaluate_minimum_wage(_facts(state="TESTLAND-A"), rs, federal_code=_FEDERAL)
