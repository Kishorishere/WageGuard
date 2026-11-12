"""Evidence retrieval: hard filters before similarity (spec §11, G-09, G-10).

Hard metadata filters (jurisdiction, topic, source-version validity for
the work date) are applied before any ranking. Required passages come
from the engine by id; supplemental passages come from a bounded
similarity search within the filtered set.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from wageguard.domain.enums import Topic
from wageguard.domain.errors import ConfigurationError, EvidenceError
from wageguard.domain.identifiers import PassageId
from wageguard.domain.jurisdiction import Jurisdiction
from wageguard.evidence.chunking import Passage
from wageguard.evidence.embedder import Embedder
from wageguard.evidence.store import InMemoryPassageStore


@dataclass(frozen=True, slots=True)
class SearchQuery:
    jurisdictions: tuple[Jurisdiction, ...]
    topic: Topic
    as_of: date
    text: str
    k: int
    max_distance: float


@dataclass(frozen=True, slots=True)
class ScoredPassage:
    passage: Passage
    distance: float


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Required + supplemental passages for one decision (spec §11.2).

    `required` are engine-dictated and ordered by the engine's rule
    order. `supplemental` are similarity hits within the filtered set,
    ordered by distance with a stable tiebreak on passage_id. The two
    lists are deduplicated against each other (a passage in `required`
    is never repeated in `supplemental`).
    """

    required: tuple[Passage, ...]
    supplemental: tuple[ScoredPassage, ...]


class EvidenceRetriever(Protocol):
    def fetch_required(self, ids: Sequence[PassageId]) -> tuple[Passage, ...]: ...
    def search(self, q: SearchQuery) -> tuple[ScoredPassage, ...]: ...


def build_evidence_bundle(
    retriever: EvidenceRetriever,
    required_ids: Sequence[PassageId],
    query: SearchQuery,
) -> EvidenceBundle:
    required = retriever.fetch_required(required_ids)
    required_id_strs = {str(p.passage_id) for p in required}
    hits = retriever.search(query)
    supplemental = tuple(h for h in hits if str(h.passage.passage_id) not in required_id_strs)
    return EvidenceBundle(required=tuple(required), supplemental=supplemental)


# ---------------------------------------------------------------------------
# In-memory retriever
# ---------------------------------------------------------------------------


class InMemoryEvidenceRetriever:
    """Read side of `InMemoryPassageStore`. Hard filters first (G-09)."""

    def __init__(self, store: InMemoryPassageStore, embedder: Embedder) -> None:
        if store.model_id is not None and store.model_id != embedder.model_id:
            raise ConfigurationError(
                f"embedding model mismatch at query time: store {store.model_id}, "
                f"retriever {embedder.model_id}"
            )
        if store.dimension is not None and store.dimension != embedder.dimension:
            raise ConfigurationError(
                f"embedding dimension mismatch: store {store.dimension}, "
                f"retriever {embedder.dimension}"
            )
        self._store = store
        self._embedder = embedder

    def fetch_required(self, ids: Sequence[PassageId]) -> tuple[Passage, ...]:
        found: list[Passage] = []
        for pid in ids:
            passage = self._find(pid)
            if passage is None:
                raise EvidenceError(f"required passage not found: {pid}")
            found.append(passage)
        return tuple(found)

    def search(self, q: SearchQuery) -> tuple[ScoredPassage, ...]:
        query_vec = self._embedder.embed((q.text,))[0]
        candidates: list[ScoredPassage] = []
        for source_key in self._store._all_source_keys():
            spec = self._store.spec_for(source_key)
            if spec is None:
                continue
            # Hard filter: jurisdiction, topic, and source-version
            # date validity — all applied BEFORE similarity ranking.
            if spec.jurisdiction not in q.jurisdictions:
                continue
            if q.topic not in spec.topics:
                continue
            if spec.validity is not None and not spec.validity.contains(q.as_of):
                continue
            last = self._store.last_version_for(source_key)
            if last is None:
                continue
            passages, embeddings = self._store._passages_for(source_key, last.version_no)
            for passage, embedding in zip(passages, embeddings, strict=True):
                dist = _cosine_distance(query_vec, embedding)
                candidates.append(ScoredPassage(passage=passage, distance=dist))
        # Stable sort: distance ascending, then passage_id for determinism.
        candidates.sort(key=_scored_order_key)
        filtered = [c for c in candidates if c.distance <= q.max_distance]
        return tuple(filtered[: q.k])

    def _find(self, pid: PassageId) -> Passage | None:
        for source_key in self._store._all_source_keys():
            last = self._store.last_version_for(source_key)
            if last is None:
                continue
            passages, _ = self._store._passages_for(source_key, last.version_no)
            for p in passages:
                if str(p.passage_id) == str(pid):
                    return p
        return None


def _scored_order_key(sp: ScoredPassage) -> tuple[float, str]:
    return (sp.distance, str(sp.passage.passage_id))


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 1.0
    sim = dot / (na * nb)
    return 1.0 - max(min(sim, 1.0), -1.0)
