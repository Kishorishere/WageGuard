"""Exact replay (spec §13.7, G-17, G-18): byte-identical; never mutates the original."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.ledger import append
from wageguard.ledger.records import PartialHeader, RecordKind
from wageguard.ledger.replay import ReplayVerdict, replay_exact
from wageguard.ledger.repository import InMemoryLedgerRepository


def _partial(decision_id: str = "d1", kind: RecordKind = RecordKind.DECISION) -> PartialHeader:
    return PartialHeader(
        decision_id=DecisionId(decision_id),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="deadbeef",
        record_kind=kind,
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )


@pytest.mark.guarantee("G-17")
def test_exact_replay_byte_identical_for_engine_only() -> None:
    repo = InMemoryLedgerRepository()
    original = append(repo, _partial("d1"), body={"verdict": "FLAG", "actual_rate": "9.99"})
    result = replay_exact(repo, original.header.decision_id)
    assert result.verdict is ReplayVerdict.MATCH
    assert result.replay_record is not None
    # The replay record's BODY is byte-identical to the original's.
    from wageguard.ledger.canonical import canonical_bytes

    assert canonical_bytes(result.replay_record.body) == canonical_bytes(original.body)


@pytest.mark.guarantee("G-18")
def test_replay_writes_a_new_record_and_never_mutates_original() -> None:
    repo = InMemoryLedgerRepository()
    original = append(repo, _partial("d1"), body={"verdict": "FLAG"})
    original_record_hash = original.record_hash
    replay_exact(repo, original.header.decision_id)

    found = next(
        r
        for r in repo.all()
        if r.header.decision_id == "d1" and r.header.record_kind is RecordKind.DECISION
    )
    assert found.record_hash == original_record_hash  # never mutated
    # A new record with kind == REPLAY exists.
    replay_records = [r for r in repo.all() if r.header.record_kind is RecordKind.REPLAY]
    assert len(replay_records) == 1
    assert replay_records[0].header.replay_of == "d1"


def test_replay_of_unknown_decision_returns_cannot_replay() -> None:
    repo = InMemoryLedgerRepository()
    result = replay_exact(repo, DecisionId("ghost"))
    assert result.verdict is ReplayVerdict.CANNOT_REPLAY
    assert "ghost" in result.reason or "not found" in result.reason.lower()


def test_replay_of_a_rejection_record_cannot_replay() -> None:
    repo = InMemoryLedgerRepository()
    append(repo, _partial("d1", kind=RecordKind.REJECTION), body={"error": "malformed"})
    result = replay_exact(repo, DecisionId("d1"))
    assert result.verdict is ReplayVerdict.CANNOT_REPLAY
