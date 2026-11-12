"""The append operation (spec §13.5).

One transaction: lock head, read previous hash and sequence_no,
compute hash, insert record, release lock. In-memory this is a
threading.RLock; the SQL adapter uses `SELECT … FOR UPDATE` on the
ledger_head row.
"""

from __future__ import annotations

from collections.abc import Mapping

from wageguard.ledger.canonical import CANON_VERSION
from wageguard.ledger.chain import GENESIS_PREV_HASH, compute_record_hash
from wageguard.ledger.records import LedgerRecord, PartialHeader, RecordHeader
from wageguard.ledger.repository import LedgerRepository


def append(
    repo: LedgerRepository,
    partial: PartialHeader,
    body: Mapping[str, object],
) -> LedgerRecord:
    with repo.with_append_lock():
        last = repo.head()
        prev_hash = last.record_hash if last is not None else GENESIS_PREV_HASH
        sequence_no = (last.header.sequence_no + 1) if last is not None else 1
        header = RecordHeader(
            decision_id=partial.decision_id,
            sequence_no=sequence_no,
            created_at=partial.created_at,
            app_version=partial.app_version,
            git_commit=partial.git_commit,
            record_kind=partial.record_kind,
            canon_version=CANON_VERSION,
            check_type_value=partial.check_type_value,
            ruleset_version=partial.ruleset_version,
            ruleset_hash=partial.ruleset_hash,
            replay_of=partial.replay_of,
        )
        record_hash = compute_record_hash(header=header, body=body, prev_hash=prev_hash)
        record = LedgerRecord(
            header=header, body=body, prev_hash=prev_hash, record_hash=record_hash
        )
        repo.append_record(record)
        return record
