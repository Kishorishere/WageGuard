"""Scorer classification table (spec §14.3, §14.9)."""

from __future__ import annotations

import pytest

from wageguard.domain.fields import FieldName
from wageguard.domain.reason_codes import ReasonCode
from wageguard.evaluation.scoring import (
    ActualKind,
    ActualOutcome,
    Classification,
    ExpectedKind,
    ExpectedOutcome,
    classify,
)


def _exp(kind: ExpectedKind, **kw: object) -> ExpectedOutcome:
    return ExpectedOutcome(kind=kind, **kw)  # type: ignore[arg-type]


def _act(kind: ActualKind, **kw: object) -> ActualOutcome:
    return ActualOutcome(kind=kind, **kw)  # type: ignore[arg-type]


class TestDecisiveExpected:
    def test_matching_decisive_is_correct(self) -> None:
        assert (
            classify(_exp(ExpectedKind.FLAG), _act(ActualKind.FLAG), answerable=True)
            is Classification.CORRECT_DECISIVE
        )

    def test_opposite_decisive_is_confidently_wrong(self) -> None:
        assert (
            classify(_exp(ExpectedKind.FLAG), _act(ActualKind.PASS), answerable=True)
            is Classification.CONFIDENTLY_WRONG
        )

    def test_abstained_when_decisive_expected_is_over_abstention(self) -> None:
        assert (
            classify(
                _exp(ExpectedKind.FLAG),
                _act(ActualKind.CANNOT_DETERMINE),
                answerable=True,
            )
            is Classification.OVER_ABSTENTION
        )


class TestAbstentionExpected:
    def test_decisive_when_abstention_expected_is_confidently_wrong(self) -> None:
        # Spec §14.3: emitting a decisive result when the expected
        # outcome is an abstention counts as CONFIDENTLY_WRONG.
        assert (
            classify(
                _exp(ExpectedKind.CANNOT_DETERMINE),
                _act(ActualKind.PASS),
                answerable=False,
            )
            is Classification.CONFIDENTLY_WRONG
        )

    def test_correct_abstention_matches_kind_and_codes_and_fields(self) -> None:
        result = classify(
            _exp(
                ExpectedKind.CANNOT_DETERMINE,
                reason_codes=(ReasonCode.MISSING_REQUIRED_FACT,),
                missing_fields=(FieldName.PAY_RATE,),
            ),
            _act(
                ActualKind.CANNOT_DETERMINE,
                reason_codes=(ReasonCode.MISSING_REQUIRED_FACT,),
                missing_fields=(FieldName.PAY_RATE,),
            ),
            answerable=False,
        )
        assert result is Classification.CORRECT_ABSTENTION

    def test_abstained_with_wrong_kind_is_wrong_abstention_type(self) -> None:
        assert (
            classify(
                _exp(ExpectedKind.CANNOT_DETERMINE),
                _act(ActualKind.NEEDS_LEGAL_REVIEW),
                answerable=False,
            )
            is Classification.WRONG_ABSTENTION_TYPE
        )

    def test_abstained_with_wrong_reason_codes_is_wrong_type(self) -> None:
        result = classify(
            _exp(
                ExpectedKind.CANNOT_DETERMINE,
                reason_codes=(ReasonCode.MISSING_REQUIRED_FACT,),
            ),
            _act(
                ActualKind.CANNOT_DETERMINE,
                reason_codes=(ReasonCode.INVALID_FIELD_VALUE,),
            ),
            answerable=False,
        )
        assert result is Classification.WRONG_ABSTENTION_TYPE

    def test_abstained_with_wrong_fields_is_wrong_type(self) -> None:
        result = classify(
            _exp(
                ExpectedKind.CANNOT_DETERMINE,
                missing_fields=(FieldName.PAY_RATE,),
            ),
            _act(
                ActualKind.CANNOT_DETERMINE,
                missing_fields=(FieldName.WORK_STATE,),
            ),
            answerable=False,
        )
        assert result is Classification.WRONG_ABSTENTION_TYPE


class TestFault:
    @pytest.mark.parametrize(
        "expected_kind",
        [
            ExpectedKind.PASS,
            ExpectedKind.FLAG,
            ExpectedKind.CANNOT_DETERMINE,
            ExpectedKind.NEEDS_LEGAL_REVIEW,
        ],
    )
    def test_fault_overrides_everything(self, expected_kind: ExpectedKind) -> None:
        assert (
            classify(_exp(expected_kind), _act(ActualKind.FAULT), answerable=True)
            is Classification.FAULT
        )
