"""InMemoryPassageStore contract tests (spec §10.6, §10.7)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import (
    ContentHash,
    EmbeddingModelId,
    PassageId,
    SourceKey,
)
from wageguard.evidence.chunking import Passage
from wageguard.evidence.store import InMemoryPassageStore, SourceVersion


def _passage() -> Passage:
    return Passage(
        passage_id=PassageId("s", 1, 0),
        text="t",
        normalized_text="t",
        heading_path=(),
        char_start=0,
        char_end=1,
        token_count=1,
        content_hash=ContentHash("x"),
        chunker_version="v1",  # type: ignore[arg-type]
    )


def _sv() -> SourceVersion:
    return SourceVersion(
        source_key=SourceKey("s"),
        version_no=1,
        content_hash=ContentHash("x"),
        retrieved_at=datetime.now(UTC),
    )


def test_register_embedding_model_is_idempotent() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    assert store.model_id == "m"


def test_registering_different_model_raises() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m1"), dimension=4)
    with pytest.raises(ConfigurationError, match="embedding model"):
        store.register_embedding_model(EmbeddingModelId("m2"), dimension=4)


def test_registering_different_dimension_raises() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    with pytest.raises(ConfigurationError, match="embedding model"):
        store.register_embedding_model(EmbeddingModelId("m"), dimension=8)


def test_store_passages_rejects_without_registered_model() -> None:
    store = InMemoryPassageStore()
    with pytest.raises(ConfigurationError, match="embedding model"):
        store.store_passages(_sv(), (_passage(),), ((0.1, 0.2, 0.3, 0.4),))


def test_store_rejects_mismatched_embedding_count() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    with pytest.raises(ConfigurationError, match="length"):
        store.store_passages(_sv(), (_passage(), _passage()), ((0.0, 0.0, 0.0, 0.0),))


def test_store_rejects_mismatched_embedding_dimension() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    with pytest.raises(ConfigurationError, match="dimension"):
        store.store_passages(_sv(), (_passage(),), ((0.0, 0.0),))


def test_last_version_and_passage_count() -> None:
    store = InMemoryPassageStore()
    store.register_embedding_model(EmbeddingModelId("m"), dimension=4)
    assert store.last_version_for(SourceKey("s")) is None
    sv = _sv()
    store.store_passages(sv, (_passage(),), ((0.1, 0.1, 0.1, 0.1),))
    last = store.last_version_for(SourceKey("s"))
    assert last is not None
    assert last.version_no == 1
    assert store.passage_count_for(SourceKey("s"), version_no=1) == 1
