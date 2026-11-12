"""Ingest orchestrator: idempotent and transactional (spec §10.4, §10.9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wageguard.domain.errors import ConfigurationError, EvidenceError
from wageguard.domain.identifiers import EmbeddingModelId
from wageguard.evidence.embedder import DeterministicFakeEmbedder
from wageguard.evidence.ingest import IngestResult, ingest
from wageguard.evidence.manifest import load_source_manifest
from wageguard.evidence.snapshot import write_snapshot_for_source
from wageguard.evidence.store import InMemoryPassageStore

MANIFEST = Path(__file__).resolve().parents[2] / "_fixtures" / "corpus" / "manifest.yaml"
HTML = Path(__file__).resolve().parents[2] / "_fixtures" / "corpus" / "synthetic.html"


def _seed_snapshot(tmp_path: Path, data: bytes) -> None:
    # Writes the content-addressed bytes file plus a `<source_key>.current`
    # pointer so the orchestrator can resolve source_key -> snapshot.
    from wageguard.domain.identifiers import SourceKey

    write_snapshot_for_source(tmp_path, SourceKey("synthetic_src"), data, suffix=".html")


def test_initial_ingest_creates_version_one(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path, HTML.read_bytes())
    store = InMemoryPassageStore()
    embedder = DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v1"), dimension=8)
    results = ingest(
        manifest=load_source_manifest(MANIFEST),
        snapshots_dir=tmp_path,
        store=store,
        embedder=embedder,
    )
    assert len(results) == 1
    r = results[0]
    assert isinstance(r, IngestResult)
    assert r.status == "created"
    assert r.version_no == 1
    assert r.passage_count >= 1


def test_re_ingest_unchanged_content_records_unchanged(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path, HTML.read_bytes())
    store = InMemoryPassageStore()
    embedder = DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v1"), dimension=8)
    ingest(load_source_manifest(MANIFEST), tmp_path, store, embedder)
    second = ingest(load_source_manifest(MANIFEST), tmp_path, store, embedder)
    assert second[0].status == "unchanged"
    assert second[0].version_no == 1  # no new version


def test_changed_content_creates_new_version(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path, HTML.read_bytes())
    store = InMemoryPassageStore()
    embedder = DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v1"), dimension=8)
    ingest(load_source_manifest(MANIFEST), tmp_path, store, embedder)
    # Replace the snapshot bytes with a different payload.
    new_bytes = HTML.read_bytes().replace(b"$9.99", b"$10.00")
    _seed_snapshot(tmp_path, new_bytes)
    second = ingest(load_source_manifest(MANIFEST), tmp_path, store, embedder)
    assert second[0].status == "created"
    assert second[0].version_no == 2


def test_missing_snapshot_raises(tmp_path: Path) -> None:
    # Don't seed anything; ingestion should fail cleanly with an
    # EvidenceError, not silently produce an empty corpus.
    store = InMemoryPassageStore()
    embedder = DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v1"), dimension=8)
    with pytest.raises(EvidenceError, match="snapshot"):
        ingest(load_source_manifest(MANIFEST), tmp_path, store, embedder)


def test_switching_embedder_model_raises(tmp_path: Path) -> None:
    _seed_snapshot(tmp_path, HTML.read_bytes())
    store = InMemoryPassageStore()
    ingest(
        load_source_manifest(MANIFEST),
        tmp_path,
        store,
        DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v1"), dimension=8),
    )
    # A second ingest with a different model id must raise -- the index
    # commits to one model (spec §10.6).
    with pytest.raises(ConfigurationError, match="embedding model"):
        ingest(
            load_source_manifest(MANIFEST),
            tmp_path,
            store,
            DeterministicFakeEmbedder(EmbeddingModelId("fake-test-v2"), dimension=8),
        )
