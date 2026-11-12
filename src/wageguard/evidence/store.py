"""PassageStore port + in-memory implementation (spec §10.7).

The SQL adapter is Phase 5; Phase 4 ships an in-memory store so unit
tests exercise the full ingest pipeline without a database. Both
implementations honour the same contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import ContentHash, EmbeddingModelId, SourceKey
from wageguard.evidence.chunking import Passage


@dataclass(frozen=True, slots=True)
class SourceVersion:
    source_key: SourceKey
    version_no: int
    content_hash: ContentHash
    retrieved_at: datetime


class PassageStore(Protocol):
    def register_embedding_model(self, model_id: EmbeddingModelId, dimension: int) -> None: ...
    def store_passages(
        self,
        source_version: SourceVersion,
        passages: Sequence[Passage],
        embeddings: Sequence[tuple[float, ...]],
    ) -> None: ...
    def last_version_for(self, source_key: SourceKey) -> SourceVersion | None: ...
    def passage_count_for(self, source_key: SourceKey, version_no: int) -> int: ...


class InMemoryPassageStore:
    def __init__(self) -> None:
        self._model_id: EmbeddingModelId | None = None
        self._dimension: int | None = None
        self._versions: dict[SourceKey, list[SourceVersion]] = {}
        self._passages: dict[tuple[SourceKey, int], list[Passage]] = {}

    @property
    def model_id(self) -> EmbeddingModelId | None:
        return self._model_id

    def register_embedding_model(self, model_id: EmbeddingModelId, dimension: int) -> None:
        if self._model_id is None:
            self._model_id = model_id
            self._dimension = dimension
            return
        if self._model_id != model_id or self._dimension != dimension:
            raise ConfigurationError(
                f"embedding model mismatch: store has "
                f"{self._model_id}@{self._dimension}, received {model_id}@{dimension}"
            )

    def store_passages(
        self,
        source_version: SourceVersion,
        passages: Sequence[Passage],
        embeddings: Sequence[tuple[float, ...]],
    ) -> None:
        if self._model_id is None or self._dimension is None:
            raise ConfigurationError("embedding model must be registered before storing passages")
        if len(passages) != len(embeddings):
            raise ConfigurationError("passages and embeddings have different lengths")
        for emb in embeddings:
            if len(emb) != self._dimension:
                raise ConfigurationError(
                    f"embedding has dimension {len(emb)}, store expects {self._dimension}"
                )
        self._versions.setdefault(source_version.source_key, []).append(source_version)
        self._passages[(source_version.source_key, source_version.version_no)] = list(passages)

    def last_version_for(self, source_key: SourceKey) -> SourceVersion | None:
        versions = self._versions.get(source_key)
        if not versions:
            return None
        return versions[-1]

    def passage_count_for(self, source_key: SourceKey, version_no: int) -> int:
        return len(self._passages.get((source_key, version_no), ()))
