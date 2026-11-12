"""Fault-injection wrappers: schedule + exception propagation (spec §16.3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from wageguard.domain.errors import (
    AppendFailed,
    LlmTimeout,
    RetrievalUnavailable,
)
from wageguard.domain.identifiers import DecisionId, PassageId, RulesetVersion
from wageguard.evidence.retrieval import InMemoryEvidenceRetriever, SearchQuery
from wageguard.evidence.store import InMemoryPassageStore
from wageguard.ledger.records import PartialHeader, RecordKind
from wageguard.ledger.repository import InMemoryLedgerRepository
from wageguard.llm.fake_client import FakeClient
from wageguard.llm.port import LlmRequest
from wageguard.resilience.fault_injection import (
    FailureSchedule,
    FaultInjectingEvidenceRetriever,
    FaultInjectingLedgerRepository,
    FaultInjectingLlmClient,
    Schedule,
)


def _llm_req() -> LlmRequest:
    return LlmRequest(
        model_id="m",
        prompt_name="n",
        prompt_version="v1",
        prompt_sha256="h",
        system_text="",
        user_text="u",
        temperature=0.0,
        max_tokens=16,
        timeout_seconds=5,
    )


class TestLlmWrapper:
    def test_always_schedule_fails_every_call(self) -> None:
        client = FaultInjectingLlmClient(
            inner=FakeClient(responses=('{"a":1}',)),
            exc_factory=lambda: LlmTimeout("down"),
            schedule=Schedule(FailureSchedule.ALWAYS),
        )
        with pytest.raises(LlmTimeout):
            client.generate_structured(_llm_req())
        with pytest.raises(LlmTimeout):
            client.generate_structured(_llm_req())

    def test_first_n_fails_then_succeeds(self) -> None:
        client = FaultInjectingLlmClient(
            inner=FakeClient(responses=('{"a":1}',)),
            exc_factory=lambda: LlmTimeout("flaky"),
            schedule=Schedule(FailureSchedule.FIRST_N, n=1),
        )
        with pytest.raises(LlmTimeout):
            client.generate_structured(_llm_req())
        # Second call hits the real FakeClient.
        r = client.generate_structured(_llm_req())
        assert r.raw_text == '{"a":1}'

    def test_nth_call_only_that_call_fails(self) -> None:
        client = FaultInjectingLlmClient(
            inner=FakeClient(responses=('{"a":1}', '{"b":2}')),
            exc_factory=lambda: LlmTimeout("sporadic"),
            schedule=Schedule(FailureSchedule.NTH_CALL, n=2),
        )
        r1 = client.generate_structured(_llm_req())
        assert r1.raw_text == '{"a":1}'
        with pytest.raises(LlmTimeout):
            client.generate_structured(_llm_req())


class TestLedgerWrapper:
    def test_append_failure_surfaces_as_append_failed(self) -> None:
        repo = FaultInjectingLedgerRepository(
            inner=InMemoryLedgerRepository(),
            exc_factory=lambda: AppendFailed("db down"),
            schedule=Schedule(FailureSchedule.ALWAYS),
            stage="append_record",
        )
        partial = PartialHeader(
            decision_id=DecisionId("d1"),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            app_version="0.0.0",
            git_commit="deadbeef",
            record_kind=RecordKind.DECISION,
            check_type_value="minimum_wage",
            ruleset_version=RulesetVersion("v"),
            ruleset_hash="rsh",
        )
        from wageguard.ledger.ledger import append

        with pytest.raises(AppendFailed):
            append(repo, partial, body={"verdict": "PASS"})


class TestRetrieverWrapper:
    def test_search_failure_surfaces(self) -> None:
        inner_store = InMemoryPassageStore()
        from wageguard.domain.identifiers import EmbeddingModelId
        from wageguard.evidence.embedder import DeterministicFakeEmbedder

        emb = DeterministicFakeEmbedder(EmbeddingModelId("m"), dimension=4)
        inner_store.register_embedding_model(emb.model_id, emb.dimension)
        retriever = InMemoryEvidenceRetriever(inner_store, emb)

        from wageguard.domain.enums import Topic
        from wageguard.domain.jurisdiction import jurisdiction

        wrapped = FaultInjectingEvidenceRetriever(
            inner=retriever,
            exc_factory=lambda: RetrievalUnavailable("vector index down"),
            schedule=Schedule(FailureSchedule.ALWAYS),
            stage="search",
        )
        q = SearchQuery(
            jurisdictions=(jurisdiction("US"),),
            topic=Topic.MINIMUM_WAGE,
            as_of=datetime(2024, 7, 1, tzinfo=UTC).date(),
            text="x",
            k=5,
            max_distance=1.0,
        )
        with pytest.raises(RetrievalUnavailable):
            wrapped.search(q)

    def test_fetch_required_failure_surfaces(self) -> None:
        inner_store = InMemoryPassageStore()
        from wageguard.domain.identifiers import EmbeddingModelId
        from wageguard.evidence.embedder import DeterministicFakeEmbedder

        emb = DeterministicFakeEmbedder(EmbeddingModelId("m"), dimension=4)
        inner_store.register_embedding_model(emb.model_id, emb.dimension)
        retriever = InMemoryEvidenceRetriever(inner_store, emb)
        wrapped = FaultInjectingEvidenceRetriever(
            inner=retriever,
            exc_factory=lambda: RetrievalUnavailable("missing passage"),
            schedule=Schedule(FailureSchedule.ALWAYS),
            stage="fetch_required",
        )
        with pytest.raises(RetrievalUnavailable):
            wrapped.fetch_required((PassageId("a", 1, 0),))
