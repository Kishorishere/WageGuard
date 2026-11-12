"""LedgerRecord types (spec §13.2).

`PartialHeader` is what callers supply; `append()` fills in `sequence_no`
and `canon_version`. `LedgerRecord` is the stored shape, with the chain
linkage (`prev_hash`) and derived `record_hash`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from wageguard.domain.identifiers import DecisionId, RulesetVersion


class RecordKind(StrEnum):
    DECISION = "decision"
    ABSTENTION = "abstention"
    FAULT = "fault"
    REJECTION = "rejection"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class PartialHeader:
    decision_id: DecisionId
    created_at: datetime
    app_version: str
    git_commit: str
    record_kind: RecordKind
    check_type_value: str
    ruleset_version: RulesetVersion
    ruleset_hash: str
    replay_of: DecisionId | None = None


@dataclass(frozen=True, slots=True)
class RecordHeader:
    decision_id: DecisionId
    sequence_no: int
    created_at: datetime
    app_version: str
    git_commit: str
    record_kind: RecordKind
    canon_version: str
    check_type_value: str
    ruleset_version: RulesetVersion
    ruleset_hash: str
    replay_of: DecisionId | None = None


@dataclass(frozen=True, slots=True)
class LedgerRecord:
    header: RecordHeader
    body: Mapping[str, object]
    prev_hash: str
    record_hash: str
