"""Synthetic rulesets for engine tests (spec §9.7).

Engine correctness must not depend on real legal values; TESTLAND-A and
TESTLAND-B let us exercise state-above-federal, federal-above-state,
no-state-rule, and effective-date-boundary paths with invented numbers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.ranges import EffectiveRange

# Synthetic federal rate well below the states so the "state controls"
# path is the common case.
_US = jurisdiction("US")
_A = jurisdiction("TESTLAND-A")
_B = jurisdiction("TESTLAND-B")

_FAKE_PASSAGE = PassageId("fake_src", 1, 0)


def _rule(
    *,
    rule_id: str,
    jur: str,
    value: str,
    start: date,
    end: date | None = None,
) -> Rule:
    return Rule(
        rule_id=RuleId(rule_id),
        jurisdiction=jurisdiction(jur),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal(value),
        unit="USD/hour",
        effective=EffectiveRange(start, end),
        supporting_passages=(_FAKE_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
        notes="synthetic",
    )


@pytest.fixture
def us_rate() -> str:
    return "7.00"


@pytest.fixture
def testland_ruleset() -> Ruleset:
    rules = (
        _rule(rule_id="us.mw", jur="US", value="7.00", start=date(2020, 1, 1)),
        _rule(rule_id="tla.mw", jur="TESTLAND-A", value="15.00", start=date(2020, 1, 1)),
        # TESTLAND-B has no state rule (federal controls on that path).
        _rule(
            rule_id="tla.mw.v2",
            jur="TESTLAND-A",
            value="16.00",
            start=date(2024, 7, 1),
        ),
    )
    # Fix overlap: shrink the earlier TESTLAND-A rule to end on 2024-07-01.
    rules = (
        rules[0],
        _rule(
            rule_id="tla.mw",
            jur="TESTLAND-A",
            value="15.00",
            start=date(2020, 1, 1),
            end=date(2024, 7, 1),
        ),
        rules[2],
    )
    return Ruleset.from_rules(RulesetVersion("test.0.0"), rules)
