"""Fact status enum (spec §8.3).

INVALID vs MISSING matters operationally: missing data needs collection,
invalid data needs correction. AMBIGUOUS flags a value that could mean
more than one thing (e.g. a city name that exists in multiple states).
"""

from __future__ import annotations

from enum import StrEnum


class FactStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"
    AMBIGUOUS = "ambiguous"
