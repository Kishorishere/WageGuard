"""InMemoryLedgerRepository shape (spec §13.5)."""

from __future__ import annotations

import pytest

from wageguard.domain.errors import AppendFailed
from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.canonical import CANON_VERSION
from wageguard.ledger.chain import GENESIS_PREV_HASH, compute_record_hash
from wageguard.ledger.records import LedgerRecord, RecordHeader, RecordKind
from wageguard.ledger.repository import InMemoryLedgerRepository


def _header(seq: int) -> RecordHeader:
    from datetime import UTC, datetime

    return RecordHeader(
        decision_id=DecisionId("d"),
        sequence_no=seq,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="deadbeef",
        record_kind=RecordKind.DECISION,
        canon_version=CANON_VERSION,
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )


def _record(seq: int, prev: str) -> LedgerRecord:
    header = _header(seq)
    body: dict[str, object] = {"x": 1}
    return LedgerRecord(
        header=header,
        body=body,
        prev_hash=prev,
        record_hash=compute_record_hash(header=header, body=body, prev_hash=prev),
    )


def test_append_record_rejects_bad_prev_hash() -> None:
    repo = InMemoryLedgerRepository()
    repo.append_record(_record(1, GENESIS_PREV_HASH))
    # Try to append a record whose prev_hash does not match current head.
    bogus = _record(2, prev="0" * 64)
    with pytest.raises(AppendFailed, match="prev_hash"):
        repo.append_record(bogus)


def test_find_by_decision_id_filters_correctly() -> None:
    repo = InMemoryLedgerRepository()
    r1 = _record(1, GENESIS_PREV_HASH)
    repo.append_record(r1)
    assert repo.find_by_decision_id(DecisionId("d")) == (r1,)
    assert repo.find_by_decision_id(DecisionId("other")) == ()


def test_all_returns_defensive_copy() -> None:
    repo = InMemoryLedgerRepository()
    r1 = _record(1, GENESIS_PREV_HASH)
    repo.append_record(r1)
    snap = repo.all()
    assert snap == (r1,)
    # Mutating the returned tuple cannot happen (tuple is immutable);
    # make sure it's not sharing identity with the internal list.
    assert isinstance(snap, tuple)
