"""Scope guard (spec §8.5): route out-of-scope cases to NEEDS_LEGAL_REVIEW."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from wageguard.compliance.facts import RawFacts
from wageguard.compliance.scope import ScopeVerdict, evaluate_scope
from wageguard.domain.enums import CheckType, PayBasis, WorkerCategory
from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import NeedsLegalReview
from wageguard.domain.reason_codes import ReasonCode


def _rf(**overrides: object) -> RawFacts:
    values: dict[FieldName, object] = {
        FieldName.WORK_STATE: "WA",
        FieldName.WORK_DATE: date(2024, 7, 1),
        FieldName.PAY_RATE: Decimal("15.50"),
        FieldName.PAY_BASIS: PayBasis.HOURLY,
        FieldName.WORKER_CATEGORY: WorkerCategory.GENERAL,
    }
    for k, v in overrides.items():
        values[FieldName(k)] = v
    return RawFacts(check=CheckType.MINIMUM_WAGE, values=values)


class TestInScope:
    def test_general_hourly_us_state_is_in_scope(self) -> None:
        v = evaluate_scope(_rf(), supported_jurisdictions={"WA", "US"})
        assert v.in_scope is True
        assert v.verdict is None


class TestOutOfScope:
    def test_non_general_worker_category_routes_to_legal_review(self) -> None:
        v = evaluate_scope(
            _rf(worker_category=WorkerCategory.TIPPED),
            supported_jurisdictions={"WA", "US"},
        )
        assert isinstance(v.verdict, NeedsLegalReview)
        assert ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY in v.verdict.reasons

    def test_locality_present_routes_to_legal_review(self) -> None:
        v = evaluate_scope(
            _rf(locality="Seattle"),
            supported_jurisdictions={"WA", "US"},
        )
        assert isinstance(v.verdict, NeedsLegalReview)
        assert ReasonCode.LOCAL_RULES_NOT_ENCODED in v.verdict.reasons

    def test_unsupported_state_routes_to_legal_review(self) -> None:
        v = evaluate_scope(
            _rf(work_state="TX"),
            supported_jurisdictions={"WA", "US"},
        )
        assert isinstance(v.verdict, NeedsLegalReview)
        assert ReasonCode.OUT_OF_SCOPE_JURISDICTION in v.verdict.reasons

    def test_period_straddle_fields_route_to_legal_review(self) -> None:
        v = evaluate_scope(
            _rf(period_start=date(2024, 6, 15), period_end=date(2024, 7, 15)),
            supported_jurisdictions={"WA", "US"},
        )
        assert isinstance(v.verdict, NeedsLegalReview)
        assert ReasonCode.PERIOD_STRADDLES_RULE_CHANGE in v.verdict.reasons


class TestMultipleScopeViolations:
    def test_all_offending_scope_reasons_reported(self) -> None:
        v = evaluate_scope(
            _rf(worker_category=WorkerCategory.TIPPED, locality="Seattle"),
            supported_jurisdictions={"WA", "US"},
        )
        assert isinstance(v.verdict, NeedsLegalReview)
        assert ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY in v.verdict.reasons
        assert ReasonCode.LOCAL_RULES_NOT_ENCODED in v.verdict.reasons


class TestVerdictShape:
    def test_scope_verdict_is_a_frozen_value(self) -> None:
        v = evaluate_scope(_rf(), supported_jurisdictions={"WA", "US"})
        assert isinstance(v, ScopeVerdict)
