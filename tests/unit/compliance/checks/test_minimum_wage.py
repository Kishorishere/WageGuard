"""Minimum-wage engine over synthetic TESTLAND rules (spec §9.4, §9.7)."""

from __future__ import annotations

from datetime import date

import pytest

from wageguard.compliance.checks.minimum_wage import (
    EngineResult,
    MinimumWageFacts,
    evaluate_minimum_wage,
)
from wageguard.compliance.rules import Ruleset
from wageguard.domain.enums import PayBasis, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged, Passed
from wageguard.domain.reason_codes import ReasonCode

_FEDERAL = jurisdiction("US")


def _facts(
    *,
    pay_rate: str,
    state: str = "TESTLAND-A",
    work_date: date = date(2024, 7, 1),
) -> MinimumWageFacts:
    return MinimumWageFacts(
        work_state=jurisdiction(state),
        work_date=work_date,
        pay_rate=Money(pay_rate),
        pay_basis=PayBasis.HOURLY,
        worker_category=WorkerCategory.GENERAL,
    )


class TestBoundaryStateAboveFederal:
    """TESTLAND-A rate is $16/hr from 2024-07-01; $15 before; federal $7."""

    def test_pay_one_cent_below_flags(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(_facts(pay_rate="15.99"), testland_ruleset, federal_code=_FEDERAL)
        assert isinstance(r, EngineResult)
        assert isinstance(r.verdict, Flagged)
        assert r.actual_rate == Money("15.99")
        assert r.controlling_rate == Money("16.00")
        assert r.shortfall == Money("0.01")

    def test_pay_exactly_at_passes(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(_facts(pay_rate="16.00"), testland_ruleset, federal_code=_FEDERAL)
        assert isinstance(r.verdict, Passed)
        assert r.shortfall is None

    def test_pay_one_cent_above_passes(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(_facts(pay_rate="16.01"), testland_ruleset, federal_code=_FEDERAL)
        assert isinstance(r.verdict, Passed)


class TestEffectiveDateBoundary:
    def test_day_before_rule_change_uses_old_rate(self, testland_ruleset: Ruleset) -> None:
        # 2024-06-30 is before TESTLAND-A's new $16 rate (effective 2024-07-01),
        # so the controlling rate is the old $15. Pay of $15.00 passes.
        r = evaluate_minimum_wage(
            _facts(pay_rate="15.00", work_date=date(2024, 6, 30)),
            testland_ruleset,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Passed)
        assert r.controlling_rate == Money("15.00")

    def test_day_of_rule_change_uses_new_rate(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(
            _facts(pay_rate="15.00", work_date=date(2024, 7, 1)),
            testland_ruleset,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Flagged)
        assert r.controlling_rate == Money("16.00")


class TestNoStateRulePath:
    def test_no_state_rule_federal_applies(self, testland_ruleset: Ruleset) -> None:
        # TESTLAND-B has no state rule; federal $7 controls.
        r = evaluate_minimum_wage(
            _facts(pay_rate="7.00", state="TESTLAND-B"),
            testland_ruleset,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Passed)
        assert r.controlling_rate == Money("7.00")
        assert ReasonCode.STATE_RULE_ABSENT_FEDERAL_APPLIES in r.reason_codes

    def test_no_state_rule_below_federal_flags(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(
            _facts(pay_rate="6.99", state="TESTLAND-B"),
            testland_ruleset,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Flagged)
        assert r.controlling_rate == Money("7.00")


class TestHighestRateControls:
    def test_candidate_rules_include_federal_and_state(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(_facts(pay_rate="16.00"), testland_ruleset, federal_code=_FEDERAL)
        jurisdictions_in_candidates = {c.jurisdiction for c in r.candidate_rules}
        assert jurisdiction("US") in jurisdictions_in_candidates
        assert jurisdiction("TESTLAND-A") in jurisdictions_in_candidates

    def test_controlling_rule_is_the_higher_rate(self, testland_ruleset: Ruleset) -> None:
        r = evaluate_minimum_wage(_facts(pay_rate="16.00"), testland_ruleset, federal_code=_FEDERAL)
        assert r.controlling_rule.jurisdiction == jurisdiction("TESTLAND-A")


class TestRequiredPassagesComeFromEngine:
    def test_engine_names_the_controlling_rule_passages(self, testland_ruleset: Ruleset) -> None:
        # §9.4: required citations come from the engine, not retrieval.
        r = evaluate_minimum_wage(_facts(pay_rate="16.00"), testland_ruleset, federal_code=_FEDERAL)
        assert r.required_passages != ()


class TestAmbiguousIsFault:
    def test_degenerate_ruleset_raises_configuration_error(self, testland_ruleset: Ruleset) -> None:
        # Construct a degenerate state ruleset with two overlapping
        # applicable rules via direct attr assignment (bypass loader).
        from decimal import Decimal

        from wageguard.compliance.rules import Rule, Ruleset
        from wageguard.domain.enums import ReviewStatus, Topic
        from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
        from wageguard.domain.ranges import EffectiveRange

        def _d(value: str, rid: str) -> Rule:
            return Rule(
                rule_id=RuleId(rid),
                jurisdiction=jurisdiction("TESTLAND-A"),
                topic=Topic.MINIMUM_WAGE,
                worker_category=WorkerCategory.GENERAL,
                value=Decimal(value),
                unit="USD/hour",
                effective=EffectiveRange(date(2020, 1, 1), None),
                supporting_passages=(PassageId("fake_src", 1, 0),),
                review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
            )

        rs = Ruleset.__new__(Ruleset)
        object.__setattr__(rs, "version", RulesetVersion("v"))
        object.__setattr__(rs, "rules", (_d("15.00", "a"), _d("16.00", "b")))
        object.__setattr__(rs, "ruleset_hash", "unverified")

        with pytest.raises(ConfigurationError, match="ambiguous"):
            evaluate_minimum_wage(_facts(pay_rate="16.00"), rs, federal_code=_FEDERAL)
