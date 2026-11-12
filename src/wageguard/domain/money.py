"""Money: frozen Decimal + Currency pair (spec §7.2, G-01).

Construction rejects `float`. Arithmetic across currencies raises.
Full precision is preserved; rounding happens only at defined
presentation points (see ADR-0005 for quantization policy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

from wageguard.domain.errors import CurrencyMismatchError


class Currency(StrEnum):
    USD = "USD"


_CANONICAL_PLACES: Final = 4  # ADR-0005: canonical serialization places


@dataclass(frozen=True, slots=True, init=False)
class Money:
    amount: Decimal
    currency: Currency = field(default=Currency.USD)

    def __init__(self, amount: Decimal | str, currency: Currency = Currency.USD) -> None:
        # Widen to `object` for defensive runtime checks against callers who
        # ignore the static annotation. The isinstance ladder is the actual
        # guard; mypy sees the narrower declared type.
        raw: object = amount
        if isinstance(raw, bool | float):
            # bool is a subclass of int but conceptually float-ish; the
            # strict rule is Decimal-or-str only (ADR-0005).
            raise TypeError(f"Money rejects {type(raw).__name__}; construct from Decimal or str")
        if isinstance(raw, str):
            try:
                raw = Decimal(raw)
            except InvalidOperation as exc:
                raise ValueError(f"Money string is not a valid decimal: {raw!r}") from exc
        if not isinstance(raw, Decimal):
            raise TypeError(f"Money.amount must be Decimal or str, got {type(raw).__name__}")
        object.__setattr__(self, "amount", raw)
        object.__setattr__(self, "currency", currency)

    # --- arithmetic ------------------------------------------------------

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency!r} with {other.currency!r}")

    # --- ordering --------------------------------------------------------

    def __lt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._require_same_currency(other)
        return self.amount >= other.amount

    # --- canonical serialization (ADR-0005) ------------------------------

    def to_canonical_string(self) -> str:
        """Fixed-precision normalized string for hashing and storage.

        See ADR-0005: trailing zeros are preserved to a fixed number of
        places so `"1.5"` and `"1.50"` serialize identically.
        """
        quantum = Decimal(10) ** -_CANONICAL_PLACES
        return format(self.amount.quantize(quantum), "f")

    @classmethod
    def from_canonical_string(cls, s: str, currency: Currency = Currency.USD) -> Money:
        return cls(s, currency)
