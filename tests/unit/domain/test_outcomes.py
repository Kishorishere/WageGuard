"""Outcomes are a closed sum type. Faults are NOT representable as outcomes (G-03).

The compiler guards against forgotten cases. Adding a variant must break
every consumer that does not update its exhaustive match.
"""

from __future__ import annotations

from typing import assert_never

import pytest

from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import (
    CannotDetermine,
    Flagged,
    NeedsLegalReview,
    Outcome,
    Passed,
)
from wageguard.domain.reason_codes import ReasonCode


def classify(outcome: Outcome) -> str:
    """Exhaustive match — compilers reject missing cases under mypy --strict."""
    match outcome:
        case Passed():
            return "passed"
        case Flagged():
            return "flagged"
        case CannotDetermine():
            return "cannot_determine"
        case NeedsLegalReview():
            return "needs_legal_review"
        case _:  # pragma: no cover
            assert_never(outcome)


class TestOutcomeShape:
    def test_passed_is_a_singleton_like_instance(self) -> None:
        assert classify(Passed()) == "passed"

    def test_flagged(self) -> None:
        assert classify(Flagged()) == "flagged"

    def test_cannot_determine_carries_reasons_and_fields(self) -> None:
        c = CannotDetermine(
            reasons=(ReasonCode.MISSING_REQUIRED_FACT,),
            fields=(FieldName.WORK_STATE, FieldName.WORK_DATE),
        )
        assert c.reasons == (ReasonCode.MISSING_REQUIRED_FACT,)
        assert c.fields == (FieldName.WORK_STATE, FieldName.WORK_DATE)

    def test_needs_legal_review_carries_reasons(self) -> None:
        n = NeedsLegalReview(reasons=(ReasonCode.OUT_OF_SCOPE_JURISDICTION,))
        assert n.reasons == (ReasonCode.OUT_OF_SCOPE_JURISDICTION,)


class TestOutcomeImmutability:
    def test_cannot_determine_is_frozen(self) -> None:
        c = CannotDetermine(reasons=(ReasonCode.MISSING_REQUIRED_FACT,), fields=())
        with pytest.raises((AttributeError, TypeError)):
            c.reasons = ()  # type: ignore[misc]


class TestDisjointFromFault:
    @pytest.mark.guarantee("G-03")
    def test_fault_types_are_not_outcome_types(self) -> None:
        # G-03: a Fault (exception type) is never representable as an Outcome.
        # The architecture test enforces this at the type level; this test
        # documents the intent at runtime by asserting the error hierarchy
        # does not inherit from any outcome dataclass.
        from wageguard.domain.errors import WageGuardError

        for variant in (Passed, Flagged, CannotDetermine, NeedsLegalReview):
            assert not issubclass(WageGuardError, variant)
            assert not issubclass(variant, WageGuardError)
