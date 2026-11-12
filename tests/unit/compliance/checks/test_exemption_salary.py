"""Exemption salary engine over synthetic rules (spec §15.6, G-21)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wageguard.compliance.checks.exemption_salary import (
    ExemptionEngineResult,
    ExemptionSalaryFacts,
    evaluate_exemption_salary,
)
from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import PayBasis, PayPeriod, ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged, NeedsLegalReview, Passed
from wageguard.domain.ranges import EffectiveRange
from wageguard.domain.reason_codes import ReasonCode

_FEDERAL = jurisdiction("US")
_PASSAGE = PassageId("testland_exempt", 1, 0)

# Synthetic threshold: $1,000 weekly (invented; not a real figure).
_THRESHOLD_VALUE = Decimal("1000.00")


def _threshold_rule(value: str = "1000.00") -> Rule:
    return Rule(
        rule_id=RuleId("us.exempt.testland"),
        jurisdiction=_FEDERAL,
        topic=Topic.EXEMPTION_SALARY_LEVEL,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal(value),
        unit="USD/week",
        effective=EffectiveRange(date(2020, 1, 1), None),
        supporting_passages=(_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )


def _ruleset(*, threshold: str = "1000.00") -> Ruleset:
    return Ruleset.from_rules(RulesetVersion("exempt-test"), (_threshold_rule(threshold),))


def _facts(
    *,
    salary: str,
    basis: PayBasis = PayBasis.SALARY,
    state: str = "US",
    current_exempt_status: bool = False,
) -> ExemptionSalaryFacts:
    return ExemptionSalaryFacts(
        work_state=jurisdiction(state),
        work_date=date(2024, 7, 1),
        salary_amount=Money(salary),
        pay_basis=basis,
        pay_period=PayPeriod.WEEKLY,
        worker_category=WorkerCategory.GENERAL,
        current_exempt_status=current_exempt_status,
    )


class TestBoundaries:
    def test_salary_one_cent_below_flags_level(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(_facts(salary="999.99"), rs, federal_code=_FEDERAL)
        assert isinstance(r, ExemptionEngineResult)
        assert isinstance(r.verdict, Flagged)
        assert ReasonCode.EXEMPT_SALARY_LEVEL_NOT_MET in r.reason_codes

    def test_salary_at_threshold_routes_to_legal_review(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(_facts(salary="1000.00"), rs, federal_code=_FEDERAL)
        assert isinstance(r.verdict, NeedsLegalReview)
        assert ReasonCode.EXEMPT_DUTIES_NOT_EVALUATED in r.reason_codes

    def test_salary_one_cent_above_also_routes_to_legal_review(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(_facts(salary="1000.01"), rs, federal_code=_FEDERAL)
        assert isinstance(r.verdict, NeedsLegalReview)


class TestBasisFailure:
    def test_hourly_pay_flagged_regardless_of_amount(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(
            _facts(salary="10000.00", basis=PayBasis.HOURLY),
            rs,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Flagged)
        assert ReasonCode.EXEMPT_SALARY_BASIS_NOT_MET in r.reason_codes


class TestEmployerLabelDoesNotOverride:
    def test_current_exempt_status_true_with_insufficient_salary_still_flags(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(
            _facts(salary="500.00", current_exempt_status=True),
            rs,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, Flagged)
        assert ReasonCode.EXEMPT_SALARY_LEVEL_NOT_MET in r.reason_codes

    def test_current_exempt_status_true_with_sufficient_salary_routes_to_review(
        self,
    ) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(
            _facts(salary="1500.00", current_exempt_status=True),
            rs,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, NeedsLegalReview)
        assert ReasonCode.EXEMPT_DUTIES_NOT_EVALUATED in r.reason_codes


class TestStateScope:
    def test_state_route_adds_state_rules_not_encoded(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(
            _facts(salary="1500.00", state="TESTLAND-A"),
            rs,
            federal_code=_FEDERAL,
        )
        assert isinstance(r.verdict, NeedsLegalReview)
        assert ReasonCode.STATE_EXEMPTION_RULES_NOT_ENCODED in r.reason_codes


class TestRefusalToCertify:
    @pytest.mark.guarantee("G-21")
    @settings(max_examples=200)
    @given(
        salary_cents=st.integers(min_value=0, max_value=1_000_000),
        current_exempt_status=st.booleans(),
    )
    def test_no_input_produces_pass_when_opted_out(
        self, salary_cents: int, current_exempt_status: bool
    ) -> None:
        rs = _ruleset()
        salary = str(Decimal(salary_cents) / Decimal(100))
        # Choose basis uniformly to exercise every path.
        for basis in (PayBasis.HOURLY, PayBasis.SALARY):
            r = evaluate_exemption_salary(
                _facts(
                    salary=salary,
                    basis=basis,
                    current_exempt_status=current_exempt_status,
                ),
                rs,
                federal_code=_FEDERAL,
            )
            assert not isinstance(r.verdict, Passed), (
                f"PASS leaked with salary={salary}, basis={basis}, "
                f"current_exempt_status={current_exempt_status}"
            )


class TestOptInStillRequiresDuties:
    def test_opt_in_still_routes_to_review_because_duties_are_not_evaluated(self) -> None:
        rs = _ruleset()
        r = evaluate_exemption_salary(
            _facts(salary="2000.00"),
            rs,
            federal_code=_FEDERAL,
            allow_certify_exemption=True,
        )
        assert isinstance(r.verdict, NeedsLegalReview)
        assert ReasonCode.EXEMPT_NEEDS_HUMAN_CONFIRMATION in r.reason_codes
