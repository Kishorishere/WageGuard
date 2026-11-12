"""Extract $-prefixed dollar figures from text (spec §12.4 check 8)."""

from __future__ import annotations

import re
from decimal import Decimal

# $1,234.56 | $15.00 | $15 ; whole + optional cents; comma as thousands.
_DOLLAR_RE = re.compile(r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)")


def extract_dollar_figures(text: str) -> tuple[Decimal, ...]:
    return tuple(Decimal(m.group(1).replace(",", "")) for m in _DOLLAR_RE.finditer(text))
