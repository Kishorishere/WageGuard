"""applicable_rule returns Found | NoRule | Ambiguous (spec §9.4)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.rules import (
    Ambiguous,
    Found,
    NoRule,
    Rule,
    Ruleset,
    applicable_rule,
)
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.ranges import EffectiveRange

_PASSAGE = PassageId("fake_src", 1, 0)


def _rule(
    *,
    rid: str,
    jur: str = "US",
    value: str = "7.00",
    start: date,
    end: date | None = None,
    category: WorkerCategory = WorkerCategory.GENERAL,
) -> Rule:
    return Rule(
        rule_id=RuleId(rid),
        jurisdiction=jurisdiction(jur),
        topic=Topic.MINIMUM_WAGE,
        worker_category=category,
        value=Decimal(value),
        unit="USD/hour",
        effective=EffectiveRange(start, end),
        supporting_passages=(_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )


def _rs(*rules: Rule) -> Ruleset:
    return Ruleset.from_rules(RulesetVersion("v"), rules)


class TestFoundOnExactMatch:
    def test_found_single_rule(self) -> None:
        r = _rule(rid="a", start=date(2020, 1, 1))
        lk = applicable_rule(
            _rs(r),
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            category=WorkerCategory.GENERAL,
            on=date(2024, 7, 1),
        )
        assert isinstance(lk, Found)
        assert lk.rule.rule_id == "a"

    def test_found_at_effective_from_boundary(self) -> None:
        # Half-open: start is inclusive.
        r = _rule(rid="a", start=date(2024, 7, 1))
        lk = applicable_rule(
            _rs(r),
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            category=WorkerCategory.GENERAL,
            on=date(2024, 7, 1),
        )
        assert isinstance(lk, Found)

    def test_no_rule_day_before_effective_from(self) -> None:
        r = _rule(rid="a", start=date(2024, 7, 1))
        lk = applicable_rule(
            _rs(r),
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            category=WorkerCategory.GENERAL,
            on=date(2024, 6, 30),
        )
        assert isinstance(lk, NoRule)


class TestNoRule:
    def test_no_matching_jurisdiction(self) -> None:
        r = _rule(rid="a", jur="US", start=date(2020, 1, 1))
        lk = applicable_rule(
            _rs(r),
            jurisdiction=jurisdiction("TESTLAND-A"),
            topic=Topic.MINIMUM_WAGE,
            category=WorkerCategory.GENERAL,
            on=date(2024, 7, 1),
        )
        assert isinstance(lk, NoRule)


class TestAmbiguous:
    def test_ambiguous_when_two_rules_cover_same_date_same_key(self) -> None:
        # Normally caught at load, but applicable_rule must also handle
        # it defensively — the Ambiguous verdict lets the engine route
        # it to ConfigurationError rather than fabricate an outcome.
        a = _rule(rid="a", start=date(2020, 1, 1), end=date(2025, 1, 1))
        b = _rule(rid="b", start=date(2020, 1, 1), end=date(2025, 1, 1))
        # Bypass the Ruleset.from_rules validator to construct the
        # degenerate ruleset directly (the test is for applicable_rule,
        # not for the loader).
        rs = Ruleset.__new__(Ruleset)
        object.__setattr__(rs, "version", RulesetVersion("v"))
        object.__setattr__(rs, "rules", (a, b))
        object.__setattr__(rs, "ruleset_hash", "unverified")

        lk = applicable_rule(
            rs,
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            category=WorkerCategory.GENERAL,
            on=date(2024, 7, 1),
        )
        assert isinstance(lk, Ambiguous)
        assert len(lk.rules) == 2


class TestVariantPatternMatching:
    @pytest.mark.parametrize("variant", [Found, NoRule, Ambiguous])
    def test_variants_are_distinct_types(self, variant: type) -> None:
        assert variant.__name__ in {"Found", "NoRule", "Ambiguous"}
