"""Content-addressed snapshot storage with tamper detection (spec §10.3, §10.9)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from wageguard.domain.errors import EvidenceError
from wageguard.evidence.snapshot import (
    compute_content_hash,
    read_snapshot_verified,
    write_snapshot,
)


def test_write_snapshot_returns_content_addressed_path(tmp_path: Path) -> None:
    data = b"<html><body>hello</body></html>"
    path = write_snapshot(tmp_path, data, suffix=".html")
    expected = hashlib.sha256(data).hexdigest()
    assert path.name == f"{expected}.html"
    assert path.read_bytes() == data


def test_write_is_idempotent(tmp_path: Path) -> None:
    data = b"same bytes"
    p1 = write_snapshot(tmp_path, data, suffix=".html")
    p2 = write_snapshot(tmp_path, data, suffix=".html")
    assert p1 == p2


def test_read_verified_returns_bytes(tmp_path: Path) -> None:
    data = b"roundtrip me"
    path = write_snapshot(tmp_path, data, suffix=".bin")
    expected = compute_content_hash(data)
    assert read_snapshot_verified(path, expected) == data


def test_read_detects_tampered_bytes(tmp_path: Path) -> None:
    data = b"original"
    path = write_snapshot(tmp_path, data, suffix=".bin")
    # Rewrite the file's contents with different bytes; the hash in the
    # filename now lies about what the file contains.
    path.write_bytes(b"tampered!")
    with pytest.raises(EvidenceError, match="content hash"):
        read_snapshot_verified(path, compute_content_hash(data))


def test_compute_content_hash_matches_sha256() -> None:
    data = b"some bytes"
    assert compute_content_hash(data) == hashlib.sha256(data).hexdigest()
