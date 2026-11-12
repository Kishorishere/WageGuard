"""Required-facts graph and resolution (spec §8.4, G-04, G-05).

The resolver walks the per-check required-facts tuple and classifies
every field at once. When any field is not `PRESENT`, the resolver emits
a `CannotDetermine` listing **all** offending fields — the engine never
stops at the first miss.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from wageguard.compliance.validators import (
    validate_bool,
    validate_money,
    validate_pay_basis,
    validate_pay_period,
    validate_us_state,
    validate_work_date,
    validate_worker_category,
)
from wageguard.domain.enums import CheckType
from wageguard.domain.fact_status import FactStatus
from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import CannotDetermine
from wageguard.domain.reason_codes import ReasonCode

Validator = Callable[[object], FactStatus]


@dataclass(frozen=True, slots=True)
class RawFacts:
    """Typed facts handed from intake to compliance.

    `values` is a mapping from field name to the already-coerced domain
    value (Decimal, date, StrEnum member, str, int, bool) or `None`
    when the field is absent.
    """

    check: CheckType
    values: Mapping[FieldName, object]


@dataclass(frozen=True, slots=True)
class RequiredFact:
    name: FieldName
    validator: Validator
    why: str


@dataclass(frozen=True, slots=True)
class FactResolution:
    statuses: Mapping[FieldName, FactStatus]

    @property
    def all_present(self) -> bool:
        return all(s is FactStatus.PRESENT for s in self.statuses.values())

    def offending_fields(self) -> tuple[FieldName, ...]:
        # Declaration order is preserved by the resolver's dict.
        return tuple(f for f, s in self.statuses.items() if s is not FactStatus.PRESENT)

    def as_abstention(self) -> CannotDetermine | None:
        if self.all_present:
            return None
        statuses_seen = {s for s in self.statuses.values() if s is not FactStatus.PRESENT}
        reasons: list[ReasonCode] = []
        if FactStatus.MISSING in statuses_seen:
            reasons.append(ReasonCode.MISSING_REQUIRED_FACT)
        if FactStatus.INVALID in statuses_seen:
            reasons.append(ReasonCode.INVALID_FIELD_VALUE)
        if FactStatus.AMBIGUOUS in statuses_seen:
            reasons.append(ReasonCode.AMBIGUOUS_FIELD_VALUE)
        return CannotDetermine(reasons=tuple(reasons), fields=self.offending_fields())


def resolve(required: Sequence[RequiredFact], facts: RawFacts) -> FactResolution:
    statuses: dict[FieldName, FactStatus] = {}
    for req in required:
        v = facts.values.get(req.name)
        statuses[req.name] = req.validator(v)
    return FactResolution(MappingProxyType(statuses))


def exemption_salary_facts() -> tuple[RequiredFact, ...]:
    """Required-facts graph for the `exemption_salary` check."""
    return (
        RequiredFact(FieldName.WORK_STATE, validate_us_state, "Determines applicable rules."),
        RequiredFact(FieldName.WORK_DATE, validate_work_date, "Thresholds are effective-dated."),
        RequiredFact(
            FieldName.SALARY_AMOUNT,
            validate_money,
            "Compared against the controlling threshold.",
        ),
        RequiredFact(
            FieldName.PAY_BASIS,
            validate_pay_basis,
            "Hourly pay cannot satisfy the salary-basis requirement.",
        ),
        RequiredFact(
            FieldName.PAY_PERIOD,
            validate_pay_period,
            "The pay period pins the threshold's unit of comparison.",
        ),
        RequiredFact(
            FieldName.WORKER_CATEGORY,
            validate_worker_category,
            "Non-general categories route to legal review.",
        ),
        RequiredFact(
            FieldName.CURRENT_EXEMPT_STATUS,
            validate_bool,
            "Employer-recorded assertion; treated as input, not evidence.",
        ),
    )


def minimum_wage_facts() -> tuple[RequiredFact, ...]:
    """Required-facts graph for the `minimum_wage` check (spec §8.4)."""
    return (
        RequiredFact(
            FieldName.WORK_STATE,
            validate_us_state,
            "Determines which jurisdiction's rule applies.",
        ),
        RequiredFact(
            FieldName.WORK_DATE,
            validate_work_date,
            "Rules are effective-dated; the applicable rate depends on the date.",
        ),
        RequiredFact(
            FieldName.PAY_RATE,
            validate_money,
            "Pay rate is compared against the controlling minimum.",
        ),
        RequiredFact(
            FieldName.PAY_BASIS,
            validate_pay_basis,
            "MVP evaluates hourly pay only; other bases route elsewhere.",
        ),
        RequiredFact(
            FieldName.WORKER_CATEGORY,
            validate_worker_category,
            "Non-general categories (tipped, youth, etc.) are out of scope.",
        ),
    )
