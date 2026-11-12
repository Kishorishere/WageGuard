"""Required-facts graph and resolver (spec §8.4, G-05).

The resolver reports EVERY missing / invalid / ambiguous field at once,
not just the first encountered. This is tested as a list comparison on
the abstention payload.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.facts import (
    FactResolution,
    RawFacts,
    minimum_wage_facts,
    resolve,
)
from wageguard.domain.enums import CheckType, PayBasis, WorkerCategory
from wageguard.domain.fact_status import FactStatus
from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import CannotDetermine
from wageguard.domain.reason_codes import ReasonCode


def _complete_values() -> dict[FieldName, object]:
    return {
        FieldName.WORK_STATE: "WA",
        FieldName.WORK_DATE: date(2024, 7, 1),
        FieldName.PAY_RATE: Decimal("15.50"),
        FieldName.PAY_BASIS: PayBasis.HOURLY,
        FieldName.WORKER_CATEGORY: WorkerCategory.GENERAL,
    }


def _resolve(values: dict[FieldName, object]) -> FactResolution:
    rf = RawFacts(check=CheckType.MINIMUM_WAGE, values=values)
    return resolve(minimum_wage_facts(), rf)


class TestAllPresent:
    def test_all_present_no_abstention(self) -> None:
        res = _resolve(_complete_values())
        assert res.all_present is True
        assert res.as_abstention() is None


class TestMissingReporting:
    def test_single_missing_field_named(self) -> None:
        values = _complete_values()
        del values[FieldName.PAY_RATE]
        res = _resolve(values)
        abst = res.as_abstention()
        assert isinstance(abst, CannotDetermine)
        assert FieldName.PAY_RATE in abst.fields
        assert ReasonCode.MISSING_REQUIRED_FACT in abst.reasons

    def test_null_is_missing(self) -> None:
        values = _complete_values()
        values[FieldName.WORK_STATE] = None
        res = _resolve(values)
        abst = res.as_abstention()
        assert isinstance(abst, CannotDetermine)
        assert FieldName.WORK_STATE in abst.fields


class TestMultipleOffendersReportedAtOnce:
    @pytest.mark.guarantee("G-05")
    def test_resolver_reports_all_missing_fields(self) -> None:
        # G-05: when multiple fields are missing, ALL of them are named
        # in the same abstention payload (resolver does not stop at the
        # first).
        values: dict[FieldName, object] = {
            FieldName.WORK_DATE: date(2024, 7, 1),
            FieldName.PAY_BASIS: PayBasis.HOURLY,
        }
        res = _resolve(values)
        abst = res.as_abstention()
        assert isinstance(abst, CannotDetermine)
        missing_set = set(abst.fields)
        assert missing_set == {
            FieldName.WORK_STATE,
            FieldName.PAY_RATE,
            FieldName.WORKER_CATEGORY,
        }

    def test_mixed_missing_and_invalid_reported_in_one_shot(self) -> None:
        values = _complete_values()
        values[FieldName.PAY_RATE] = Decimal("-1.00")  # INVALID
        del values[FieldName.WORK_STATE]  # MISSING
        res = _resolve(values)
        abst = res.as_abstention()
        assert isinstance(abst, CannotDetermine)
        assert set(abst.fields) == {FieldName.PAY_RATE, FieldName.WORK_STATE}
        assert ReasonCode.MISSING_REQUIRED_FACT in abst.reasons
        assert ReasonCode.INVALID_FIELD_VALUE in abst.reasons


class TestStableOrdering:
    def test_fields_reported_in_declaration_order(self) -> None:
        # Determinism: same missing set produces the same field tuple.
        values: dict[FieldName, object] = {
            FieldName.WORK_STATE: "WA",
            FieldName.PAY_RATE: Decimal("15.50"),
        }
        a = _resolve(values).as_abstention()
        b = _resolve(values).as_abstention()
        assert isinstance(a, CannotDetermine)
        assert isinstance(b, CannotDetermine)
        assert a.fields == b.fields


class TestInput:
    def test_resolver_signature_takes_raw_facts(self) -> None:
        rf = RawFacts(check=CheckType.MINIMUM_WAGE, values=_complete_values())
        res = resolve(minimum_wage_facts(), rf)
        assert res.statuses[FieldName.PAY_RATE] is FactStatus.PRESENT


class TestAmbiguousStatusMapsToReason:
    def test_ambiguous_fact_surfaces_reason_code(self) -> None:
        # No built-in Phase 2 validator returns AMBIGUOUS, but the
        # FactResolution contract must map the status to a reason when
        # a future check introduces one (e.g. city-name resolving to
        # multiple states, §8.3).
        from wageguard.compliance.facts import FactResolution, RequiredFact
        from wageguard.domain.outcomes import CannotDetermine

        def always_ambiguous(_v: object) -> FactStatus:
            return FactStatus.AMBIGUOUS

        required = (RequiredFact(FieldName.WORK_STATE, always_ambiguous, "test"),)
        rf = RawFacts(check=CheckType.MINIMUM_WAGE, values={FieldName.WORK_STATE: "X"})
        res = resolve(required, rf)
        assert isinstance(res, FactResolution)
        abst = res.as_abstention()
        assert isinstance(abst, CannotDetermine)
        assert ReasonCode.AMBIGUOUS_FIELD_VALUE in abst.reasons
