"""RecordKind and header shape."""

from __future__ import annotations

from wageguard.ledger.records import RecordKind


def test_record_kinds_are_closed() -> None:
    assert set(RecordKind) == {
        RecordKind.DECISION,
        RecordKind.ABSTENTION,
        RecordKind.FAULT,
        RecordKind.REJECTION,
        RecordKind.REPLAY,
    }


def test_values_are_snake_case() -> None:
    for r in RecordKind:
        assert r.value == r.value.lower()
        assert " " not in r.value
