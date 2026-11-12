"""Outcome sum type (spec §7.2, G-03).

A closed union of four frozen dataclasses. Consumers use exhaustive
`match` with `assert_never`; adding a variant breaks every unhandled
case under mypy --strict.
"""

from __future__ import annotations

from dataclasses import dataclass

from wageguard.domain.fields import FieldName
from wageguard.domain.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class Passed:
    pass


@dataclass(frozen=True, slots=True)
class Flagged:
    pass


@dataclass(frozen=True, slots=True)
class CannotDetermine:
    reasons: tuple[ReasonCode, ...]
    fields: tuple[FieldName, ...]


@dataclass(frozen=True, slots=True)
class NeedsLegalReview:
    reasons: tuple[ReasonCode, ...]


Outcome = Passed | Flagged | CannotDetermine | NeedsLegalReview
