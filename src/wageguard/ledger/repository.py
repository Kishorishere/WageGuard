"""LedgerRepository: Protocol + in-memory implementation (spec §13.5).

The SQL adapter lands with the real deployment. The in-memory impl
serves unit tests and exercises the same contract.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol

from wageguard.domain.errors import AppendFailed
from wageguard.domain.identifiers import DecisionId
from wageguard.ledger.records import LedgerRecord


class LedgerRepository(Protocol):
    def head(self) -> LedgerRecord | None: ...
    def append_record(self, record: LedgerRecord) -> None: ...
    def all(self) -> tuple[LedgerRecord, ...]: ...
    def find_by_decision_id(self, decision_id: DecisionId) -> tuple[LedgerRecord, ...]: ...
    def with_append_lock(self) -> AbstractContextManager[None]: ...


class InMemoryLedgerRepository:
    def __init__(self) -> None:
        self._records: list[LedgerRecord] = []
        self._lock = threading.RLock()

    def head(self) -> LedgerRecord | None:
        with self._lock:
            return self._records[-1] if self._records else None

    def append_record(self, record: LedgerRecord) -> None:
        with self._lock:
            if self._records and self._records[-1].record_hash != record.prev_hash:
                raise AppendFailed(
                    f"prev_hash {record.prev_hash!r} does not match current head "
                    f"{self._records[-1].record_hash!r}"
                )
            self._records.append(record)

    def all(self) -> tuple[LedgerRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def find_by_decision_id(self, decision_id: DecisionId) -> tuple[LedgerRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records if r.header.decision_id == decision_id)

    @contextmanager
    def with_append_lock(self) -> Iterator[None]:
        with self._lock:
            yield
