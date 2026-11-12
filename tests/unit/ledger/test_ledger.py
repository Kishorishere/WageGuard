"""InMemoryLedgerRepository + the append operation (spec §13.5, G-14, G-16)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.ledger import append
from wageguard.ledger.records import PartialHeader, RecordKind
from wageguard.ledger.repository import InMemoryLedgerRepository


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


class TestBasicAppend:
    @pytest.mark.guarantee("G-14")
    def test_first_append_has_sequence_1_and_genesis_prev_hash(self) -> None:
        repo = InMemoryLedgerRepository()
        record = append(repo, _partial("d1"), body={"verdict": "PASS"})
        assert record.header.sequence_no == 1
        assert record.prev_hash == "0" * 64

    def test_second_append_links_to_first(self) -> None:
        repo = InMemoryLedgerRepository()
        r1 = append(repo, _partial("d1"), body={"verdict": "PASS"})
        r2 = append(repo, _partial("d2"), body={"verdict": "FLAG"})
        assert r2.header.sequence_no == 2
        assert r2.prev_hash == r1.record_hash

    def test_records_preserved_in_order(self) -> None:
        repo = InMemoryLedgerRepository()
        ids = [append(repo, _partial(f"d{i}"), body={"i": i}).header.sequence_no for i in range(5)]
        assert ids == [1, 2, 3, 4, 5]

    def test_record_hash_deterministic_from_input(self) -> None:
        repo1 = InMemoryLedgerRepository()
        repo2 = InMemoryLedgerRepository()
        r1 = append(repo1, _partial("d1"), body={"x": Decimal("1.50")})
        r2 = append(repo2, _partial("d1"), body={"x": Decimal("1.5000")})
        assert r1.record_hash == r2.record_hash  # Decimal canonicalization


class TestConcurrentAppend:
    @pytest.mark.guarantee("G-16")
    def test_parallel_appends_produce_linear_chain(self) -> None:
        # Threading-based: many workers append; final chain is linear
        # (sequence 1..N, every prev_hash matches), no forks.
        import threading

        repo = InMemoryLedgerRepository()
        n_workers = 8
        per_worker = 4
        errors: list[BaseException] = []

        def worker(worker_id: int) -> None:
            try:
                for j in range(per_worker):
                    append(repo, _partial(f"w{worker_id}.{j}"), body={"w": worker_id, "j": j})
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        records = repo.all()
        assert len(records) == n_workers * per_worker
        # Sequence_no is 1..N and strictly monotonic.
        for i, r in enumerate(records):
            assert r.header.sequence_no == i + 1
        # Chain linkage holds.
        from wageguard.ledger.chain import verify_chain

        assert verify_chain(records).ok is True


class TestHeadQuery:
    def test_head_returns_none_on_empty_repo(self) -> None:
        repo = InMemoryLedgerRepository()
        assert repo.head() is None

    def test_head_returns_most_recent_record(self) -> None:
        repo = InMemoryLedgerRepository()
        r1 = append(repo, _partial("d1"), body={"v": 1})
        r2 = append(repo, _partial("d2"), body={"v": 2})
        assert repo.head() == r2
        _ = r1
