"""Content-addressed snapshot storage (spec §10.3, §10.9).

Snapshots are the raw bytes a fetcher wrote once, keyed by SHA-256 of
those bytes. Reading a snapshot re-hashes the file and compares to the
filename stem; any mismatch raises `EvidenceError` — tampering is
evident.

A sidecar `<source_key>.current` pointer records which hash is the
latest snapshot for a given source. Ingest reads the pointer to resolve
`source_key -> snapshot file`; a snapshot file with no pointer is
inert history.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from wageguard.domain.errors import EvidenceError
from wageguard.domain.identifiers import ContentHash, SourceKey

_MIN_POINTER_LINES = 2


def compute_content_hash(data: bytes) -> ContentHash:
    return ContentHash(hashlib.sha256(data).hexdigest())


def write_snapshot(dir_: Path, data: bytes, *, suffix: str) -> Path:
    """Write bytes to `<sha256><suffix>` under dir_. Idempotent."""
    h = compute_content_hash(data)
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{h}{suffix}"
    if not path.exists():
        path.write_bytes(data)
    return path


def read_snapshot_verified(path: Path, expected: ContentHash) -> bytes:
    data = path.read_bytes()
    actual = compute_content_hash(data)
    if actual != expected:
        raise EvidenceError(
            f"content hash mismatch at {path.name}: expected {expected}, got {actual}"
        )
    return data


@dataclass(frozen=True, slots=True)
class SnapshotLocation:
    source_key: SourceKey
    path: Path
    content_hash: ContentHash
    suffix: str


def write_snapshot_for_source(
    dir_: Path, source_key: SourceKey, data: bytes, *, suffix: str
) -> SnapshotLocation:
    path = write_snapshot(dir_, data, suffix=suffix)
    content_hash = compute_content_hash(data)
    pointer = dir_ / f"{source_key}.current"
    pointer.write_text(f"{content_hash}\n{suffix}\n", encoding="utf-8")
    return SnapshotLocation(source_key, path, content_hash, suffix)


def read_current_snapshot(dir_: Path, source_key: SourceKey) -> SnapshotLocation | None:
    pointer = dir_ / f"{source_key}.current"
    if not pointer.exists():
        return None
    lines = pointer.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < _MIN_POINTER_LINES:
        raise EvidenceError(f"malformed snapshot pointer at {pointer}")
    content_hash = ContentHash(lines[0])
    suffix = lines[1]
    path = dir_ / f"{content_hash}{suffix}"
    return SnapshotLocation(source_key, path, content_hash, suffix)
