"""Metamorphic tests: structured transformations with known outcome shifts (spec §9.7)."""

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


def _ruleset_ab(a: str, b: str) -> Ruleset:
    return Ruleset.from_rules(
        RulesetVersion("v"),
        (
            _rule("7.00", "US", "us.mw"),
            _rule(a, "TESTLAND-A", "tla.mw"),
            _rule(b, "TESTLAND-B", "tlb.mw"),
        ),
    )


def _facts(pay: str, state: str) -> MinimumWageFacts:
    return MinimumWageFacts(
        work_state=jurisdiction(state),
        work_date=date(2024, 7, 1),
        pay_rate=Money(pay),
        pay_basis=PayBasis.HOURLY,
        worker_category=WorkerCategory.GENERAL,
    )


_cents = st.integers(min_value=1_00, max_value=100_00)


@pytest.mark.property
@settings(max_examples=100)
@given(cents=_cents)
def test_state_swap_changes_controlling_rule_predictably(cents: int) -> None:
    # Two states with different rates; pay sits in the middle. Swapping
    # the state changes the controlling rule exactly as the data says.
    rs = _ruleset_ab(a="10.00", b="20.00")
    pay = Decimal(cents) / Decimal(100)
    # In TESTLAND-A, controlling is 10.00; in TESTLAND-B, 20.00.
    for state, controlling in (("TESTLAND-A", "10.00"), ("TESTLAND-B", "20.00")):
        r = evaluate_minimum_wage(_facts(str(pay), state), rs, federal_code=_FEDERAL)
        assert r.controlling_rate == Money(controlling)


@pytest.mark.property
@settings(max_examples=50)
@given(cents=st.integers(min_value=10_00, max_value=10_00))
def test_one_cent_shift_across_threshold_flips_outcome(cents: int) -> None:
    # Controlling rate is exactly $10.00; $9.99 FLAG and $10.00 PASS.
    rs = _ruleset_ab(a="10.00", b="10.00")
    below = evaluate_minimum_wage(_facts("9.99", "TESTLAND-A"), rs, federal_code=_FEDERAL)
    at = evaluate_minimum_wage(_facts("10.00", "TESTLAND-A"), rs, federal_code=_FEDERAL)
    assert isinstance(below.verdict, Flagged)
    assert isinstance(at.verdict, Passed)
    _ = cents  # keep hypothesis interface uniform
