"""Pure validators: FactValue -> FactStatus (spec §8.3, §8.4).

Each validator is pure, total, and returns a `FactStatus`. `None` maps to
`MISSING`; an unusable value maps to `INVALID`; ambiguity (e.g. a value
that could belong to multiple jurisdictions) maps to `AMBIGUOUS`.
Validators do not raise; they classify.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from wageguard.domain.enums import PayBasis, PayPeriod, WorkerCategory
from wageguard.domain.fact_status import FactStatus

_US_STATE_RE = re.compile(r"[A-Z]{2}")


def validate_us_state(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, str):
        return FactStatus.INVALID
    if v == "" or not _US_STATE_RE.fullmatch(v):
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_work_date(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, date):
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_money(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, Decimal):
        return FactStatus.INVALID
    if v <= 0:
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_pay_basis(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, PayBasis):
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_worker_category(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, WorkerCategory):
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_pay_period(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, PayPeriod):
        return FactStatus.INVALID
    return FactStatus.PRESENT


def validate_bool(v: object) -> FactStatus:
    if v is None:
        return FactStatus.MISSING
    if not isinstance(v, bool):
        return FactStatus.INVALID
    return FactStatus.PRESENT
