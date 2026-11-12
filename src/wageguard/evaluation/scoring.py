"""Per-case classification (spec §14.3).

`CONFIDENTLY_WRONG` includes both "wrong decisive outcome" AND
"emitted decisive when expected was abstention" — a system that
makes a decision when it should abstain is worse than one that
abstains when it should decide.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from wageguard.domain.fields import FieldName
from wageguard.domain.reason_codes import ReasonCode


class Classification(StrEnum):
    CORRECT_DECISIVE = "correct_decisive"
    CONFIDENTLY_WRONG = "confidently_wrong"
    CORRECT_ABSTENTION = "correct_abstention"
    WRONG_ABSTENTION_TYPE = "wrong_abstention_type"
    OVER_ABSTENTION = "over_abstention"
    FAULT = "fault"


class ExpectedKind(StrEnum):
    PASS = "PASS"  # noqa: S105  domain constant, not a password
    FLAG = "FLAG"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"
    NEEDS_LEGAL_REVIEW = "NEEDS_LEGAL_REVIEW"


class ActualKind(StrEnum):
    PASS = "PASS"  # noqa: S105  domain constant, not a password
    FLAG = "FLAG"
    CANNOT_DETERMINE = "CANNOT_DETERMINE"
    NEEDS_LEGAL_REVIEW = "NEEDS_LEGAL_REVIEW"
    FAULT = "FAULT"


_DECISIVE_EXPECTED: frozenset[ExpectedKind] = frozenset({ExpectedKind.PASS, ExpectedKind.FLAG})
_DECISIVE_ACTUAL: frozenset[ActualKind] = frozenset({ActualKind.PASS, ActualKind.FLAG})
_ABSTENTION_EXPECTED: frozenset[ExpectedKind] = frozenset(
    {ExpectedKind.CANNOT_DETERMINE, ExpectedKind.NEEDS_LEGAL_REVIEW}
)
_ABSTENTION_ACTUAL: frozenset[ActualKind] = frozenset(
    {ActualKind.CANNOT_DETERMINE, ActualKind.NEEDS_LEGAL_REVIEW}
)


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    kind: ExpectedKind
    reason_codes: tuple[ReasonCode, ...] = ()
    missing_fields: tuple[FieldName, ...] = ()


@dataclass(frozen=True, slots=True)
class ActualOutcome:
    kind: ActualKind
    reason_codes: tuple[ReasonCode, ...] = ()
    missing_fields: tuple[FieldName, ...] = ()


def classify(
    expected: ExpectedOutcome,
    actual: ActualOutcome,
    *,
    answerable: bool,
) -> Classification:
    if actual.kind is ActualKind.FAULT:
        return Classification.FAULT

    # Expected decisive.
    if expected.kind in _DECISIVE_EXPECTED:
        if actual.kind in _DECISIVE_ACTUAL:
            # Both decisive: matching outcome -> CORRECT; mismatch -> CONFIDENTLY_WRONG.
            if str(actual.kind) == str(expected.kind):
                return Classification.CORRECT_DECISIVE
            return Classification.CONFIDENTLY_WRONG
        # Actual abstained when expected decisive.
        if answerable:
            return Classification.OVER_ABSTENTION
        # Case was not answerable but labeled decisive — labeling bug; still
        # treat as OVER_ABSTENTION since the system abstained.
        return Classification.OVER_ABSTENTION

    # Expected abstention.
    if actual.kind in _DECISIVE_ACTUAL:
        # Emitted decisive when expected was abstention — confidently wrong.
        return Classification.CONFIDENTLY_WRONG

    # Both abstained. Did the types match?
    if str(actual.kind) != str(expected.kind):
        return Classification.WRONG_ABSTENTION_TYPE
    # Same abstention kind. Reasons must match, fields must match.
    if _normalize_codes(actual.reason_codes) != _normalize_codes(expected.reason_codes):
        return Classification.WRONG_ABSTENTION_TYPE
    if _normalize_fields(actual.missing_fields) != _normalize_fields(expected.missing_fields):
        return Classification.WRONG_ABSTENTION_TYPE
    return Classification.CORRECT_ABSTENTION


def _normalize_codes(codes: Sequence[ReasonCode]) -> tuple[str, ...]:
    return tuple(sorted(c.value for c in codes))


def _normalize_fields(fields: Sequence[FieldName]) -> tuple[str, ...]:
    return tuple(sorted(f.value for f in fields))
