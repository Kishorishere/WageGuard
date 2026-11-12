"""Quote normalization (spec §12.4 check 6).

Normalization is documented and limited: NFC, collapsed whitespace,
straight quote/dash characters. Matching is exact substring after
normalisation — no fuzzy matching.
"""

from __future__ import annotations

import re
import unicodedata
from types import MappingProxyType

_CURLY_TO_STRAIGHT = MappingProxyType(
    {
        0x2018: "'",  # LEFT SINGLE QUOTATION MARK
        0x2019: "'",  # RIGHT SINGLE QUOTATION MARK
        0x201C: '"',  # LEFT DOUBLE QUOTATION MARK
        0x201D: '"',  # RIGHT DOUBLE QUOTATION MARK
        0x2013: "-",  # EN DASH
        0x2014: "-",  # EM DASH
    }
)
_WS_RE = re.compile(r"\s+")


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = s.translate(_CURLY_TO_STRAIGHT)
    s = _WS_RE.sub(" ", s).strip()
    return s


def matches_after_normalize(quote: str, passage_text: str) -> bool:
    nq = _normalize(quote)
    if not nq:
        return False
    return nq in _normalize(passage_text)
