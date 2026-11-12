"""CheckRequestModel: the trust boundary.

Pydantic v2 strict mode + `extra='forbid'`. Money fields accept only
decimal strings (not JSON floats or ints) per spec §8.2. Dates are ISO
8601. Unknown fields raise `ValidationError`, which the parser converts
to `InputRejected`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from wageguard.domain.enums import CheckType, PayBasis, PayPeriod, WorkerCategory


def _decimal_or_none(v: object) -> object:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, str):
        try:
            return Decimal(v)
        except InvalidOperation as exc:
            raise ValueError(f"not a valid decimal string: {v!r}") from exc
    # Reject bool, int, float, and anything else explicitly (spec §8.2).
    raise ValueError(f"money fields must be decimal strings, got {type(v).__name__}")


def _date_or_none(v: object) -> object:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"not a valid ISO date (YYYY-MM-DD): {v!r}") from exc
    raise ValueError(f"date must be an ISO string, got {type(v).__name__}")


DecimalField = Annotated[Decimal | None, BeforeValidator(_decimal_or_none)]
DateField = Annotated[date | None, BeforeValidator(_date_or_none)]


class CheckRequestModel(BaseModel):
    # extra='forbid' catches typos as Rejection (G-04). Strict primitives
    # are enforced per-field so enum fields can still coerce from their
    # JSON string value, while string/int/bool fields reject coercion
    # from unrelated types.
    model_config = ConfigDict(extra="forbid")

    check: CheckType

    work_state: str | None = Field(default=None, strict=True)
    work_date: DateField = None
    pay_rate: DecimalField = None
    pay_basis: PayBasis | None = None
    worker_category: WorkerCategory | None = None
    employer_size: int | None = Field(default=None, strict=True)
    hours_worked: DecimalField = None
    salary_amount: DecimalField = None
    pay_period: PayPeriod | None = None
    current_exempt_status: bool | None = Field(default=None, strict=True)
    locality: str | None = Field(default=None, strict=True)
    period_start: DateField = None
    period_end: DateField = None
