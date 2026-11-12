"""Hash chain: compute + verify + tamper detection (spec §13.4, G-15)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.chain import (
    GENESIS_PREV_HASH,
    compute_record_hash,
    verify_chain,
)
from wageguard.ledger.records import LedgerRecord, RecordHeader, RecordKind


def _header(seq: int, decision_id: str = "d") -> RecordHeader:
    return RecordHeader(
        decision_id=DecisionId(decision_id),
        sequence_no=seq,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="deadbeef",
        record_kind=RecordKind.DECISION,
        canon_version="canon_v1",
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )


def _record(
    seq: int, prev: str, body: dict[str, object] | None = None, decision_id: str = "d"
) -> LedgerRecord:
    header = _header(seq, decision_id)
    body = body if body is not None else {"verdict": "PASS"}
    record_hash = compute_record_hash(header=header, body=body, prev_hash=prev)
    return LedgerRecord(header=header, body=body, prev_hash=prev, record_hash=record_hash)


class TestGenesisHash:
    def test_genesis_prev_hash_is_64_zeros(self) -> None:
        assert GENESIS_PREV_HASH == "0" * 64


class TestRecordHashIsDeterministic:
    def test_same_input_same_hash(self) -> None:
        h = _header(1)
        body = {"x": 1}
        a = compute_record_hash(header=h, body=body, prev_hash=GENESIS_PREV_HASH)
        b = compute_record_hash(header=h, body=body, prev_hash=GENESIS_PREV_HASH)
        assert a == b

    def test_different_body_different_hash(self) -> None:
        h = _header(1)
        a = compute_record_hash(header=h, body={"x": 1}, prev_hash=GENESIS_PREV_HASH)
        b = compute_record_hash(header=h, body={"x": 2}, prev_hash=GENESIS_PREV_HASH)
        assert a != b


class TestChainVerification:
    def test_empty_chain_verifies(self) -> None:
        report = verify_chain(())
        assert report.ok is True

    def test_single_record_chain_verifies(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        report = verify_chain((r1,))
        assert report.ok is True

    def test_multi_record_chain_verifies(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        r2 = _record(2, r1.record_hash)
        r3 = _record(3, r2.record_hash)
        report = verify_chain((r1, r2, r3))
        assert report.ok is True

    def test_prev_hash_mismatch_detected(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        # Build r2 with the WRONG prev_hash.
        r2 = _record(2, "wronghash" + "0" * (64 - len("wronghash")))
        report = verify_chain((r1, r2))
        assert report.ok is False
        assert report.break_at == 1

    def test_sequence_gap_detected(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        r3 = _record(3, r1.record_hash)  # skips sequence 2
        report = verify_chain((r1, r3))
        assert report.ok is False
        assert report.break_at == 1

    @pytest.mark.guarantee("G-15")
    def test_single_byte_tamper_in_middle_detected(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        r2 = _record(2, r1.record_hash)
        r3 = _record(3, r2.record_hash)
        # Tamper with r2's body (change one byte) without recomputing hash.
        import dataclasses

        tampered_r2 = dataclasses.replace(r2, body={"verdict": "FLAG"})
        report = verify_chain((r1, tampered_r2, r3))
        assert report.ok is False
        assert report.break_at == 1  # tamper is at index 1

    def test_missing_middle_record_detected(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        r2 = _record(2, r1.record_hash)
        r3 = _record(3, r2.record_hash)
        # Drop r2 from the chain.
        report = verify_chain((r1, r3))
        assert report.ok is False
        assert report.break_at == 1

    def test_reordered_chain_detected(self) -> None:
        r1 = _record(1, GENESIS_PREV_HASH)
        r2 = _record(2, r1.record_hash)
        report = verify_chain((r2, r1))
        assert report.ok is False
        assert report.break_at == 0
