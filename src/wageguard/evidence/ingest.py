"""Ingest orchestrator (spec §10.3, §10.4, §10.10).

Reads each manifest spec, locates the current snapshot via the sidecar
pointer, chunks and embeds its passages, and stores a new
`SourceVersion` (or records "unchanged" when the content hash matches
the last stored version). Pure except for the store's writes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from wageguard.domain.errors import EvidenceError
from wageguard.domain.identifiers import SourceKey
from wageguard.evidence.chunking import chunk_html
from wageguard.evidence.embedder import Embedder
from wageguard.evidence.manifest import SourceManifest
from wageguard.evidence.snapshot import (
    read_current_snapshot,
    read_snapshot_verified,
)
from wageguard.evidence.store import PassageStore, SourceVersion


@dataclass(frozen=True, slots=True)
class IngestResult:
    source_key: SourceKey
    status: Literal["created", "unchanged"]
    version_no: int
    passage_count: int


def ingest(
    manifest: SourceManifest,
    snapshots_dir: Path,
    store: PassageStore,
    embedder: Embedder,
    *,
    clock: Callable[[], datetime] | None = None,
) -> tuple[IngestResult, ...]:
    now = clock() if clock is not None else datetime.now(UTC)
    store.register_embedding_model(embedder.model_id, embedder.dimension)

    results: list[IngestResult] = []
    for spec in manifest.sources:
        location = read_current_snapshot(snapshots_dir, spec.source_key)
        if location is None:
            raise EvidenceError(
                f"snapshot for source {spec.source_key} not found in {snapshots_dir}"
            )
        data = read_snapshot_verified(location.path, location.content_hash)
        last = store.last_version_for(spec.source_key)
        if last is not None and last.content_hash == location.content_hash:
            results.append(
                IngestResult(
                    source_key=spec.source_key,
                    status="unchanged",
                    version_no=last.version_no,
                    passage_count=store.passage_count_for(spec.source_key, last.version_no),
                )
            )
            continue
        version_no = 1 if last is None else last.version_no + 1
        passages = chunk_html(data, spec.source_key, version_no)
        embeddings = embedder.embed(tuple(p.text for p in passages))
        source_version = SourceVersion(
            source_key=spec.source_key,
            version_no=version_no,
            content_hash=location.content_hash,
            retrieved_at=now,
        )
        store.store_passages(source_version, passages, embeddings)
        results.append(
            IngestResult(
                source_key=spec.source_key,
                status="created",
                version_no=version_no,
                passage_count=len(passages),
            )
        )
    return tuple(results)
