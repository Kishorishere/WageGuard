"""Normalization: trim, NFC, uppercase 2-letter state codes (spec §8.2).

Idempotent: `normalize(normalize(x)) == normalize(x)`. Never invents
data; only reshapes equivalent representations into a canonical one.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping

_STATE_FIELD = "work_state"
_US_STATE_LEN = 2


def normalize_check_request(payload: Mapping[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in payload.items():
        out[key] = _normalize_value(key, value)
    return out


def _normalize_value(key: str, value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    v = unicodedata.normalize("NFC", value.strip())
    if key == _STATE_FIELD and len(v) == _US_STATE_LEN and v.isalpha():
        v = v.upper()
    return v
