"""Typed identifiers. PassageId is structured; others are NewTypes (spec §7.2).

PassageId format: `source_key@v{version_no}#p{ordinal:03d}`. Parsing is
strict so a typo in a rule file becomes a load-time failure, not a
silent miss at retrieval time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NewType, cast

DecisionId = NewType("DecisionId", str)
RuleId = NewType("RuleId", str)
RulesetVersion = NewType("RulesetVersion", str)
SourceVersionId = NewType("SourceVersionId", str)
PromptVersion = NewType("PromptVersion", str)


_SOURCE_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
_PASSAGE_ID_RE = re.compile(r"^(?P<src>[a-z][a-z0-9_]*)@v(?P<ver>\d+)#p(?P<ord>\d+)$")


@dataclass(frozen=True, slots=True)
class PassageId:
    source_key: str
    version_no: int
    ordinal: int

    def __post_init__(self) -> None:
        if not _SOURCE_KEY_RE.fullmatch(self.source_key):
            raise ValueError(
                f"invalid passage id: source_key {self.source_key!r} must match [a-z][a-z0-9_]*"
            )
        if self.version_no < 1:
            raise ValueError(f"invalid passage id: version_no must be >= 1, got {self.version_no}")
        if self.ordinal < 0:
            raise ValueError(f"invalid passage id: ordinal must be >= 0, got {self.ordinal}")

    def __str__(self) -> str:
        return f"{self.source_key}@v{self.version_no}#p{self.ordinal:03d}"

    @classmethod
    def parse(cls, s: str) -> PassageId:
        m = _PASSAGE_ID_RE.match(s)
        if m is None:
            raise ValueError(f"invalid passage id: expected 'source_key@vN#pNNN', got {s!r}")
        # fullmatch guarantees every named group matched; the cast tells
        # mypy the groups are `str`, not `str | Any`.
        return cls(
            source_key=cast(str, m.group("src")),
            version_no=int(cast(str, m.group("ver"))),
            ordinal=int(cast(str, m.group("ord"))),
        )
