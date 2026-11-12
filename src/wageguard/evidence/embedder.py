"""Embedder port + deterministic fake (spec §10.6).

The fake embedder lets retrieval logic be tested without a network or a
real model. Real adapters implement the same protocol and are swapped
in at the composition root.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from wageguard.domain.identifiers import EmbeddingModelId

_BYTE_MAX = 255.0


class Embedder(Protocol):
    @property
    def model_id(self) -> EmbeddingModelId: ...
    @property
    def dimension(self) -> int: ...
    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


@dataclass(frozen=True, slots=True)
class DeterministicFakeEmbedder:
    """Hash-based embedder: SHA-256(text) -> normalized float vector.

    Deterministic across runs and processes. Not meaningful semantically;
    just enough structure for retrieval tests (identical text produces
    identical vectors; different text produces different vectors).
    """

    model_id: EmbeddingModelId
    dimension: int

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._embed_one(t) for t in texts)

    def _embed_one(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [digest[i % len(digest)] / _BYTE_MAX for i in range(self.dimension)]
        norm = math.sqrt(sum(v * v for v in raw))
        if norm == 0:
            return tuple(raw)
        return tuple(v / norm for v in raw)
