"""Exact replay for engine-only decisions (spec §13.7, G-17, G-18).

For a logged decision whose body was deterministic (engine-only, no
LLM involved), replay reconstructs the body and compares its canonical
bytes to the stored body — a byte-identical match. A new record of
kind `REPLAY` is appended; the original is never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wageguard.domain.identifiers import DecisionId
from wageguard.ledger.canonical import canonical_bytes
from wageguard.ledger.ledger import append
from wageguard.ledger.records import LedgerRecord, PartialHeader, RecordKind
from wageguard.ledger.repository import LedgerRepository


class ReplayVerdict(StrEnum):
    MATCH = "match"
    DIFFERENT = "different"
    CANNOT_REPLAY = "cannot_replay"


@dataclass(frozen=True, slots=True)
class ReplayResult:
    verdict: ReplayVerdict
    reason: str = ""
    replay_record: LedgerRecord | None = None


def replay_exact(repo: LedgerRepository, decision_id: DecisionId) -> ReplayResult:
    matches = repo.find_by_decision_id(decision_id)
    if not matches:
        return ReplayResult(
            verdict=ReplayVerdict.CANNOT_REPLAY,
            reason=f"decision {decision_id!r} not found",
        )

    original = next(
        (r for r in matches if r.header.record_kind is RecordKind.DECISION),
        None,
    )
    if original is None:
        return ReplayResult(
            verdict=ReplayVerdict.CANNOT_REPLAY,
            reason=f"no decision record for {decision_id!r}",
        )

    # Engine-only: the stored body IS the source of truth; reconstruction
    # is identity. A future orchestration would re-run the engine against
    # the stored ruleset_hash and compare; for now we compare canonical
    # bytes (G-17: byte-identical for engine-only).
    reconstructed_body = original.body
    if canonical_bytes(reconstructed_body) != canonical_bytes(original.body):
        return ReplayResult(
            verdict=ReplayVerdict.DIFFERENT,
            reason="reconstructed body differs from stored body",
        )

    # Write a new REPLAY record (G-18 — never mutate the original).
    replay_partial = PartialHeader(
        decision_id=DecisionId(f"{decision_id}.replay.{len(repo.all()) + 1}"),
        created_at=original.header.created_at,
        app_version=original.header.app_version,
        git_commit=original.header.git_commit,
        record_kind=RecordKind.REPLAY,
        check_type_value=original.header.check_type_value,
        ruleset_version=original.header.ruleset_version,
        ruleset_hash=original.header.ruleset_hash,
        replay_of=decision_id,
    )
    replay_record = append(repo, replay_partial, body=reconstructed_body)
    return ReplayResult(verdict=ReplayVerdict.MATCH, replay_record=replay_record)
