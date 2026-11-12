"""DeterministicFakeEmbedder: hash-based, deterministic, fixed-dimension."""

from __future__ import annotations

import math

from wageguard.domain.identifiers import EmbeddingModelId
from wageguard.evidence.embedder import DeterministicFakeEmbedder


def _embedder(dim: int = 8) -> DeterministicFakeEmbedder:
    return DeterministicFakeEmbedder(model_id=EmbeddingModelId("fake-test-v1"), dimension=dim)


def test_dimension_matches_configured() -> None:
    e = _embedder(dim=16)
    out = e.embed(("hello",))
    assert len(out) == 1
    assert len(out[0]) == 16


def test_embedding_is_deterministic() -> None:
    e = _embedder()
    assert e.embed(("alpha", "beta")) == e.embed(("alpha", "beta"))


def test_different_text_different_embedding() -> None:
    e = _embedder()
    a = e.embed(("alpha",))[0]
    b = e.embed(("beta",))[0]
    assert a != b


def test_embedding_is_unit_length() -> None:
    e = _embedder(dim=32)
    v = e.embed(("something non-empty",))[0]
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-9
