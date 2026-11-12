"""Engine property invariants (spec §9.7).

These exercise the engine over randomized rulesets built from TESTLAND-A
(synthetic) so correctness does not depend on real legal values.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wageguard.compliance.checks.minimum_wage import (
    MinimumWageFacts,
    evaluate_minimum_wage,
)
from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import PayBasis, ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged, Passed
from wageguard.domain.ranges import EffectiveRange

_FEDERAL = jurisdiction("US")
_PASSAGE = PassageId("fake_src", 1, 0)
_STATE = "TESTLAND-A"


def _rule(value: str, jur: str, rid: str) -> Rule:
    return Rule(
        rule_id=RuleId(rid),
        jurisdiction=jurisdiction(jur),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal(value),
        unit="USD/hour",
        effective=EffectiveRange(date(2020, 1, 1), None),
        supporting_passages=(_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )


def _ruleset(federal: str, state: str) -> Ruleset:
    return Ruleset.from_rules(
        RulesetVersion("v"),
        (_rule(federal, "US", "us.mw"), _rule(state, _STATE, "tla.mw")),
    )


def _facts(pay_rate: Decimal) -> MinimumWageFacts:
    return MinimumWageFacts(
        work_state=jurisdiction(_STATE),
        work_date=date(2024, 7, 1),
        pay_rate=Money(pay_rate),
        pay_basis=PayBasis.HOURLY,
        worker_category=WorkerCategory.GENERAL,
    )


_rates = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100.00"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


@pytest.mark.property
@settings(max_examples=200)
@given(fed=_rates, state=_rates, pay=_rates)
def test_never_pass_below_controlling_rate(fed: Decimal, state: Decimal, pay: Decimal) -> None:
    rs = _ruleset(str(fed), str(state))
    r = evaluate_minimum_wage(_facts(pay), rs, federal_code=_FEDERAL)
    controlling = max(fed, state)
    if pay < controlling:
        assert isinstance(r.verdict, Flagged)
    else:
        assert isinstance(r.verdict, Passed)


@pytest.mark.property
@settings(max_examples=200)
@given(fed=_rates, state=_rates, pay=_rates, bump=_rates)
def test_monotonic_in_pay_rate(fed: Decimal, state: Decimal, pay: Decimal, bump: Decimal) -> None:
    rs = _ruleset(str(fed), str(state))
    r1 = evaluate_minimum_wage(_facts(pay), rs, federal_code=_FEDERAL)
    r2 = evaluate_minimum_wage(_facts(pay + bump), rs, federal_code=_FEDERAL)
    if isinstance(r1.verdict, Passed):
        assert isinstance(r2.verdict, Passed)


@pytest.mark.property
@settings(max_examples=200)
@given(fed=_rates, state=_rates, pay=_rates)
def test_output_is_independent_of_rule_list_order(
    fed: Decimal, state: Decimal, pay: Decimal
) -> None:
    rs1 = Ruleset.from_rules(
        RulesetVersion("v"),
        (_rule(str(fed), "US", "a"), _rule(str(state), _STATE, "b")),
    )
    rs2 = Ruleset.from_rules(
        RulesetVersion("v"),
        (_rule(str(state), _STATE, "b"), _rule(str(fed), "US", "a")),
    )
    r1 = evaluate_minimum_wage(_facts(pay), rs1, federal_code=_FEDERAL)
    r2 = evaluate_minimum_wage(_facts(pay), rs2, federal_code=_FEDERAL)
    assert type(r1.verdict) is type(r2.verdict)
    assert r1.controlling_rate == r2.controlling_rate
