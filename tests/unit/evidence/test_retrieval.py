"""Retrieval contract + adversarial tests (spec §11, G-09, G-10)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import cast

import pytest

from wageguard.domain.enums import Topic
from wageguard.domain.errors import ConfigurationError, EvidenceError
from wageguard.domain.identifiers import (
    ContentHash,
    EmbeddingModelId,
    PassageId,
    SourceKey,
)
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.evidence.chunking import Passage
from wageguard.evidence.embedder import DeterministicFakeEmbedder
from wageguard.evidence.manifest import FetchMethod, SourceSpec, SourceType
from wageguard.evidence.retrieval import (
    EvidenceBundle,
    InMemoryEvidenceRetriever,
    ScoredPassage,
    SearchQuery,
    build_evidence_bundle,
)
from wageguard.evidence.store import InMemoryPassageStore, SourceVersion


def _spec(
    source_key: str,
    jur: str,
    topic: Topic = Topic.MINIMUM_WAGE,
    *,
    validity: object | None = None,
) -> SourceSpec:
    return SourceSpec(
        source_key=SourceKey(source_key),
        publisher="p",
        title="t",
        url="https://example.invalid/",
        jurisdiction=jurisdiction(jur),
        topics=(topic,),
        source_type=SourceType.AGENCY_GUIDANCE,
        fetch_method=FetchMethod.HTML,
        validity=validity,  # type: ignore[arg-type]
    )


def _passage(source_key: str, ordinal: int, text: str) -> Passage:
    import hashlib

    normalized = text.strip()
    return Passage(
        passage_id=PassageId(source_key, 1, ordinal),
        text=text,
        normalized_text=normalized,
        heading_path=("Section",),
        char_start=0,
        char_end=len(text),
        token_count=len(normalized.split()),
        content_hash=ContentHash(hashlib.sha256(normalized.encode("utf-8")).hexdigest()),
        chunker_version="v1",  # type: ignore[arg-type]
    )


def _seed(
    store: InMemoryPassageStore, specs_and_texts: list[tuple[SourceSpec, list[str]]], dim: int = 8
) -> DeterministicFakeEmbedder:
    embedder = DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), dimension=dim)
    store.register_embedding_model(embedder.model_id, embedder.dimension)
    for spec, texts in specs_and_texts:
        store.register_source_spec(spec)
        passages = tuple(_passage(spec.source_key, i, t) for i, t in enumerate(texts))
        embeddings = embedder.embed(tuple(p.text for p in passages))
        sv = SourceVersion(
            source_key=spec.source_key,
            version_no=1,
            content_hash=ContentHash("h"),
            retrieved_at=datetime.now(UTC),
        )
        store.store_passages(sv, passages, embeddings)
    return embedder


def _default_query(text: str, jurs: Sequence[str]) -> SearchQuery:
    return SearchQuery(
        jurisdictions=tuple(jurisdiction(j) for j in jurs),
        topic=Topic.MINIMUM_WAGE,
        as_of=date(2024, 7, 1),
        text=text,
        k=5,
        max_distance=1.0,
    )


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class TestFetchRequired:
    def test_returns_passages_by_id_in_input_order(self) -> None:
        store = InMemoryPassageStore()
        _seed(store, [(_spec("fed", "US"), ["fed text"])])
        retriever = InMemoryEvidenceRetriever(
            store,
            DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), dimension=8),
        )
        got = retriever.fetch_required((PassageId("fed", 1, 0),))
        assert len(got) == 1
        assert got[0].passage_id == PassageId("fed", 1, 0)

    def test_missing_required_passage_raises_fault(self) -> None:
        store = InMemoryPassageStore()
        _seed(store, [(_spec("fed", "US"), ["fed text"])])
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        with pytest.raises(EvidenceError, match="required passage"):
            retriever.fetch_required((PassageId("ghost", 1, 0),))


class TestHardFiltersBeforeRanking:
    @pytest.mark.guarantee("G-09")
    def test_wrong_jurisdiction_never_returned(self) -> None:
        # Seed a source in TESTLAND-A that is a near-perfect textual
        # match for the query, and query only for US. The TESTLAND-A
        # passage must not appear, regardless of its similarity.
        store = InMemoryPassageStore()
        _seed(
            store,
            [
                (_spec("fed", "US"), ["something unrelated"]),
                (_spec("state", "TESTLAND-A"), ["exact query text"]),
            ],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        hits = retriever.search(_default_query("exact query text", ["US"]))
        for h in hits:
            assert "state" not in str(h.passage.passage_id)

    def test_source_outside_validity_never_returned(self) -> None:
        # A source valid only 2020..2023 must not appear for an
        # as_of in 2024.
        from wageguard.domain.ranges import EffectiveRange

        store = InMemoryPassageStore()
        _seed(
            store,
            [
                (
                    _spec(
                        "old",
                        "US",
                        validity=EffectiveRange(date(2020, 1, 1), date(2024, 1, 1)),
                    ),
                    ["old passage"],
                ),
            ],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        hits = retriever.search(_default_query("old passage", ["US"]))
        assert hits == ()

    def test_wrong_topic_never_returned(self) -> None:
        store = InMemoryPassageStore()
        _seed(
            store,
            [
                (_spec("fed", "US", topic=Topic.MINIMUM_WAGE), ["wage text"]),
                (
                    _spec("exempt", "US", topic=Topic.EXEMPTION_SALARY_LEVEL),
                    ["exemption text"],
                ),
            ],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        hits = retriever.search(_default_query("anything", ["US"]))
        for h in hits:
            assert "exempt" not in str(h.passage.passage_id)


class TestBoundsAndOrdering:
    def test_k_caps_result_count(self) -> None:
        store = InMemoryPassageStore()
        _seed(
            store,
            [(_spec("fed", "US"), [f"p{i}" for i in range(10)])],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        hits = retriever.search(
            SearchQuery(
                jurisdictions=(jurisdiction("US"),),
                topic=Topic.MINIMUM_WAGE,
                as_of=date(2024, 7, 1),
                text="query",
                k=3,
                max_distance=2.0,
            )
        )
        assert len(hits) == 3

    def test_max_distance_excludes_far_passages(self) -> None:
        store = InMemoryPassageStore()
        _seed(store, [(_spec("fed", "US"), ["anything"])])
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        # Max distance 0.0 excludes everything except a perfect match
        # to the query text, which this seed does not provide.
        hits = retriever.search(
            SearchQuery(
                jurisdictions=(jurisdiction("US"),),
                topic=Topic.MINIMUM_WAGE,
                as_of=date(2024, 7, 1),
                text="query",
                k=10,
                max_distance=0.0,
            )
        )
        assert hits == ()

    def test_deterministic_ordering(self) -> None:
        store = InMemoryPassageStore()
        _seed(
            store,
            [(_spec("fed", "US"), ["alpha", "beta", "gamma"])],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        q = _default_query("alpha", ["US"])
        assert retriever.search(q) == retriever.search(q)


class TestEmbeddingModelMismatch:
    def test_retriever_rejects_different_model_id(self) -> None:
        store = InMemoryPassageStore()
        _seed(store, [(_spec("fed", "US"), ["text"])])
        with pytest.raises(ConfigurationError, match="embedding model"):
            InMemoryEvidenceRetriever(
                store, DeterministicFakeEmbedder(EmbeddingModelId("other"), 8)
            )

    def test_retriever_rejects_different_dimension(self) -> None:
        store = InMemoryPassageStore()
        _seed(store, [(_spec("fed", "US"), ["text"])])
        with pytest.raises(ConfigurationError, match="dimension"):
            InMemoryEvidenceRetriever(
                store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 16)
            )


class TestBundle:
    @pytest.mark.guarantee("G-10")
    def test_required_passages_lead_the_bundle(self) -> None:
        # G-10: required citations come from the engine, not retrieval.
        # The bundle preserves the required order and never duplicates
        # a required passage into supplemental.
        store = InMemoryPassageStore()
        _seed(
            store,
            [(_spec("fed", "US"), ["required text", "supplemental text"])],
        )
        retriever = InMemoryEvidenceRetriever(
            store, DeterministicFakeEmbedder(EmbeddingModelId("fake-r-v1"), 8)
        )
        bundle = build_evidence_bundle(
            retriever,
            required_ids=(PassageId("fed", 1, 0),),
            query=_default_query("required text", ["US"]),
        )
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.required[0].passage_id == PassageId("fed", 1, 0)
        required_ids = {str(p.passage_id) for p in bundle.required}
        for sp in bundle.supplemental:
            assert str(sp.passage.passage_id) not in required_ids
        _ = cast(ScoredPassage, bundle.supplemental[0]) if bundle.supplemental else None


class TestQueryTextIsControlled:
    def test_query_text_is_controlled_not_free_form(self) -> None:
        # Regression documentation: SearchQuery.text is built by the
        # engine from check type + rule identifiers, not from
        # user-supplied free text (spec §11.2). This test pins the
        # signature so a future refactor cannot sneak in a user string
        # parameter.
        import inspect

        sig = inspect.signature(SearchQuery.__init__)
        assert set(sig.parameters) == {
            "self",
            "jurisdictions",
            "topic",
            "as_of",
            "text",
            "k",
            "max_distance",
        }
