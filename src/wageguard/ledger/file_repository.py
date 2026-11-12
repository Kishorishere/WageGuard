"""File-backed ledger repository (NDJSON on disk).

One record per line, written in canonical JSON. Reads the file on
construction and appends in-process. Durable enough for a local
development and prototype demo; the SQL adapter replaces it at
deployment time.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from wageguard.domain.errors import AppendFailed, LedgerError
from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.ledger.canonical import canonical_bytes
from wageguard.ledger.records import LedgerRecord, RecordHeader, RecordKind


def _record_to_dict(record: LedgerRecord) -> dict[str, object]:
    h = record.header
    return {
        "header": {
            "decision_id": str(h.decision_id),
            "sequence_no": h.sequence_no,
            "created_at": h.created_at.isoformat(),
            "app_version": h.app_version,
            "git_commit": h.git_commit,
            "record_kind": h.record_kind.value,
            "canon_version": h.canon_version,
            "check_type_value": h.check_type_value,
            "ruleset_version": str(h.ruleset_version),
            "ruleset_hash": h.ruleset_hash,
            "replay_of": str(h.replay_of) if h.replay_of is not None else None,
        },
        "body": dict(record.body),
        "prev_hash": record.prev_hash,
        "record_hash": record.record_hash,
    }


def _record_from_dict(data: dict[str, object]) -> LedgerRecord:
    header_data = data["header"]
    assert isinstance(header_data, dict)
    replay_of_raw = header_data.get("replay_of")
    header = RecordHeader(
        decision_id=DecisionId(str(header_data["decision_id"])),
        sequence_no=int(header_data["sequence_no"]),  # type: ignore[arg-type]
        created_at=datetime.fromisoformat(str(header_data["created_at"])),
        app_version=str(header_data["app_version"]),
        git_commit=str(header_data["git_commit"]),
        record_kind=RecordKind(str(header_data["record_kind"])),
        canon_version=str(header_data["canon_version"]),
        check_type_value=str(header_data["check_type_value"]),
        ruleset_version=RulesetVersion(str(header_data["ruleset_version"])),
        ruleset_hash=str(header_data["ruleset_hash"]),
        replay_of=DecisionId(str(replay_of_raw)) if replay_of_raw else None,
    )
    body = data["body"]
    assert isinstance(body, dict)
    return LedgerRecord(
        header=header,
        body=body,
        prev_hash=str(data["prev_hash"]),
        record_hash=str(data["record_hash"]),
    )


class FileBackedLedgerRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._records: list[LedgerRecord] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        text = self._path.read_text(encoding="utf-8").strip()
        if not text:
            return
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"malformed ledger line in {self._path}: {exc}") from exc
            self._records.append(_record_from_dict(payload))

    def head(self) -> LedgerRecord | None:
        with self._lock:
            return self._records[-1] if self._records else None

    def append_record(self, record: LedgerRecord) -> None:
        with self._lock:
            if self._records and self._records[-1].record_hash != record.prev_hash:
                raise AppendFailed(
                    f"prev_hash {record.prev_hash!r} does not match head "
                    f"{self._records[-1].record_hash!r}"
                )
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Round-trip the canonical bytes to confirm serializability
            # before we commit anything to disk; a non-canonicalizable
            # body is a bug upstream.
            _ = canonical_bytes(record.body)
            line = json.dumps(_record_to_dict(record), separators=(",", ":"))
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
                f.flush()
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
