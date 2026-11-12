"""HTML -> heading-aware extracted units (spec §10.5).

Pure: a function of bytes -> tuple of ExtractedUnits. Preserves heading
hierarchy as a path on each text block so downstream chunking can
cite the right section.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from bs4 import BeautifulSoup, Tag

_HEADING_LEVELS: Mapping[str, int] = MappingProxyType(
    {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
)
_TEXT_TAGS: frozenset[str] = frozenset({"p", "li"})


@dataclass(frozen=True, slots=True)
class ExtractedUnit:
    heading_path: tuple[str, ...]
    text: str
    char_start: int
    char_end: int


def extract_units(html_bytes: bytes) -> tuple[ExtractedUnit, ...]:
    soup = BeautifulSoup(html_bytes, "html.parser")
    root = soup.find("main") or soup.find("article") or soup.find("body") or soup

    heading_stack: list[tuple[int, str]] = []
    units: list[ExtractedUnit] = []
    char_pos = 0
    tag_names = [*_HEADING_LEVELS.keys(), *_TEXT_TAGS]

    for el in root.find_all(tag_names):  # type: ignore[union-attr]
        if not isinstance(el, Tag):
            continue
        text = _collapse_whitespace(el.get_text(separator=" ", strip=True))
        if not text:
            continue
        name = el.name
        if name in _HEADING_LEVELS:
            level = _HEADING_LEVELS[name]
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            continue
        heading_path = tuple(h for _, h in heading_stack)
        start = char_pos
        end = start + len(text)
        units.append(ExtractedUnit(heading_path, text, start, end))
        char_pos = end + 1

    return tuple(units)


def _collapse_whitespace(s: str) -> str:
    return " ".join(s.split())
