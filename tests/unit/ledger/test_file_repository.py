"""FileBackedLedgerRepository: persistence + round-trip + append safety."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from wageguard.domain.errors import AppendFailed
from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.canonical import CANON_VERSION
from wageguard.ledger.chain import GENESIS_PREV_HASH, compute_record_hash, verify_chain
from wageguard.ledger.file_repository import FileBackedLedgerRepository
from wageguard.ledger.ledger import append
from wageguard.ledger.records import LedgerRecord, PartialHeader, RecordHeader, RecordKind


def _partial(decision_id: str = "d1") -> PartialHeader:
    return PartialHeader(
        decision_id=DecisionId(decision_id),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="deadbeef",
        record_kind=RecordKind.DECISION,
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )


def _hand_record(seq: int, prev: str) -> LedgerRecord:
    header = RecordHeader(
        decision_id=DecisionId("d-hand"),
        sequence_no=seq,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="x",
        record_kind=RecordKind.DECISION,
        canon_version=CANON_VERSION,
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )
    body: dict[str, object] = {"verdict": "PASS"}
    return LedgerRecord(
        header=header,
        body=body,
        prev_hash=prev,
        record_hash=compute_record_hash(header=header, body=body, prev_hash=prev),
    )


def test_fresh_file_starts_empty(tmp_path: Path) -> None:
    repo = FileBackedLedgerRepository(tmp_path / "ledger.ndjson")
    assert repo.head() is None
    assert repo.all() == ()


def test_append_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "ledger.ndjson"
    repo1 = FileBackedLedgerRepository(path)
    r1 = append(repo1, _partial("d1"), body={"verdict": "PASS"})

    # Second repo reading the same file should see the record.
    repo2 = FileBackedLedgerRepository(path)
    assert repo2.head() is not None
    assert repo2.head().record_hash == r1.record_hash  # type: ignore[union-attr]
    assert len(repo2.all()) == 1


def test_chain_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "ledger.ndjson"
    repo1 = FileBackedLedgerRepository(path)
    append(repo1, _partial("d1"), body={"i": 1})
    append(repo1, _partial("d2"), body={"i": 2})
    append(repo1, _partial("d3"), body={"i": 3})

    repo2 = FileBackedLedgerRepository(path)
    records = repo2.all()
    assert [r.header.sequence_no for r in records] == [1, 2, 3]
    assert verify_chain(records).ok is True


def test_find_by_decision_id_filters(tmp_path: Path) -> None:
    repo = FileBackedLedgerRepository(tmp_path / "ledger.ndjson")
    append(repo, _partial("d1"), body={"i": 1})
    append(repo, _partial("d2"), body={"i": 2})
    assert len(repo.find_by_decision_id(DecisionId("d1"))) == 1
    assert repo.find_by_decision_id(DecisionId("missing")) == ()


def test_append_rejects_wrong_prev_hash(tmp_path: Path) -> None:
    repo = FileBackedLedgerRepository(tmp_path / "ledger.ndjson")
    append(repo, _partial("d1"), body={"i": 1})
    bogus = _hand_record(seq=2, prev=GENESIS_PREV_HASH)
    with pytest.raises(AppendFailed, match="prev_hash"):
        repo.append_record(bogus)
