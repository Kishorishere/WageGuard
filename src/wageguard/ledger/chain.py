"""Hash chain: compute + verify (spec §13.4, G-15).

Pure. The record hash is SHA-256 over the canonical serialization of
`{header, body, prev_hash}`; the stored `record_hash` is never part of
the hashed content (otherwise verification would be circular).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from wageguard.ledger.canonical import canonical_bytes
from wageguard.ledger.records import LedgerRecord, RecordHeader

GENESIS_PREV_HASH: Final = "0" * 64


def compute_record_hash(
    *,
    header: RecordHeader,
    body: Mapping[str, object],
    prev_hash: str,
) -> str:
    payload = {"header": header, "body": body, "prev_hash": prev_hash}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class VerifyReport:
    ok: bool
    break_at: int | None = None
    reason: str = ""


def verify_chain(records: Sequence[LedgerRecord]) -> VerifyReport:
    prev = GENESIS_PREV_HASH
    for i, r in enumerate(records):
        expected_seq = i + 1
        if r.header.sequence_no != expected_seq:
            return VerifyReport(
                ok=False,
                break_at=i,
                reason=(f"sequence_no {r.header.sequence_no} != expected {expected_seq}"),
            )
        if r.prev_hash != prev:
            return VerifyReport(
                ok=False,
                break_at=i,
                reason=f"prev_hash {r.prev_hash!r} != previous record_hash {prev!r}",
            )
        recomputed = compute_record_hash(header=r.header, body=r.body, prev_hash=r.prev_hash)
        if r.record_hash != recomputed:
            return VerifyReport(
                ok=False,
                break_at=i,
                reason=(
                    f"record_hash mismatch: stored {r.record_hash!r}, " f"recomputed {recomputed!r}"
                ),
            )
        prev = r.record_hash
    return VerifyReport(ok=True)
