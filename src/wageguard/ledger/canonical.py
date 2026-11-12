"""Canonical serialization for ledger records (spec §13.3, ADR-0013).

Pure, stdlib only. Rules:
  * Floats are REJECTED. Money is Decimal; Decimal canonicalizes to a
    fixed-places string (ADR-0005), so `1.5` and `1.50` are equal.
  * Dates are ISO 8601; datetimes must be tz-aware and serialize as UTC
    RFC 3339 with microsecond precision.
  * Enums serialize by value.
  * Tuples / lists become JSON arrays.
  * Sets and frozensets are REJECTED (use a sorted tuple instead).
  * Strings are Unicode NFC.
  * `None` is explicit `null`.
  * Output JSON has sorted keys, no whitespace, UTF-8.

Changing these rules is a backwards-incompatible event: bump
`CANON_VERSION`.
"""

from __future__ import annotations

import base64
import json
import unicodedata
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Final

CANON_VERSION: Final = "canon_v1"

_CANONICAL_PLACES: Final = 4


def to_canonical_dict(obj: object) -> object:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        raise ValueError(f"canonical serialization forbids float; got {obj!r}")
    if isinstance(obj, int):
        return obj
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, Decimal):
        quantum = Decimal(10) ** -_CANONICAL_PLACES
        return format(obj.quantize(quantum), "f")
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise ValueError("canonical serialization requires timezone-aware datetime")
        utc = obj.astimezone(UTC)
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return to_canonical_dict(obj.value)
    if isinstance(obj, set | frozenset):
        raise ValueError("canonical serialization forbids set; use a sorted tuple instead")
    if isinstance(obj, list | tuple):
        return [to_canonical_dict(x) for x in obj]
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, Mapping):
        return {str(k): to_canonical_dict(v) for k, v in obj.items()}
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_canonical_dict(getattr(obj, f.name)) for f in fields(obj)}
    raise ValueError(f"canonical serialization cannot handle {type(obj).__name__}")


def to_canonical_json(obj: object) -> str:
    return json.dumps(
        to_canonical_dict(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_bytes(obj: object) -> bytes:
    return to_canonical_json(obj).encode("utf-8")
