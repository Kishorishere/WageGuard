"""Jurisdiction type and syntactic validator (spec §9.2).

A Jurisdiction is either `"US"` (federal) or a 2-letter US state code.
The scope guard decides supported-ness; this module only pins the shape.
Synthetic test jurisdictions (`"TESTLAND-A"`, etc.) are also accepted —
they let the engine's correctness be tested without real legal values.
"""

from __future__ import annotations

import re
from typing import NewType

Jurisdiction = NewType("Jurisdiction", str)

_JURISDICTION_RE = re.compile(r"US|[A-Z]{2}|TESTLAND-[A-Z]")


def is_valid_jurisdiction_code(s: str) -> bool:
    return bool(_JURISDICTION_RE.fullmatch(s))


def jurisdiction(s: str) -> Jurisdiction:
    """Constructor with validation. Raises ValueError on an invalid code."""
    if not is_valid_jurisdiction_code(s):
        raise ValueError(f"invalid jurisdiction code: {s!r}")
    return Jurisdiction(s)
