"""Fault-injecting port wrappers (spec §16.3).

Each wrapper schedules failures by rule (always, first N calls, Nth
call) and raises a caller-supplied exception. No monkey-patching, no
reaching into real adapters' internals — faults arrive through the
ports, exactly as production errors would.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from wageguard.domain.identifiers import DecisionId, EmbeddingModelId, PassageId
from wageguard.evidence.chunking import Passage
from wageguard.evidence.retrieval import EvidenceRetriever, ScoredPassage, SearchQuery
from wageguard.ledger.records import LedgerRecord
from wageguard.ledger.repository import LedgerRepository
from wageguard.llm.port import LlmClient, LlmRequest, LlmResponse


class _Schedule(Protocol):
    def should_fail(self, call_no: int) -> bool: ...


class FailureSchedule(StrEnum):
    """How the wrapper decides to fail."""

    ALWAYS = "always"
    FIRST_N = "first_n"
    NTH_CALL = "nth_call"


@dataclass(frozen=True, slots=True)
class Schedule:
    kind: FailureSchedule
    n: int = 0

    def should_fail(self, call_no: int) -> bool:
        if self.kind is FailureSchedule.ALWAYS:
            return True
        if self.kind is FailureSchedule.FIRST_N:
            return call_no <= self.n
        if self.kind is FailureSchedule.NTH_CALL:
            return call_no == self.n
        raise ValueError(f"unknown FailureSchedule: {self.kind}")  # pragma: no cover


# ---------------------------------------------------------------------------
# LLM client wrapper
# ---------------------------------------------------------------------------


@dataclass
class FaultInjectingLlmClient:
    inner: LlmClient
    exc_factory: Callable[[], BaseException]
    schedule: Schedule = field(default_factory=lambda: Schedule(FailureSchedule.ALWAYS))
    _calls: int = 0

    def generate_structured(self, req: LlmRequest) -> LlmResponse:
        self._calls += 1
        if self.schedule.should_fail(self._calls):
            raise self.exc_factory()
        return self.inner.generate_structured(req)


# ---------------------------------------------------------------------------
# EvidenceRetriever wrapper
# ---------------------------------------------------------------------------


@dataclass
class FaultInjectingEvidenceRetriever:
    inner: EvidenceRetriever
    exc_factory: Callable[[], BaseException]
    schedule: Schedule = field(default_factory=lambda: Schedule(FailureSchedule.ALWAYS))
    stage: str = "search"  # "search" | "fetch_required" | "both"
    _calls: int = 0

    def fetch_required(self, ids: Sequence[PassageId]) -> tuple[Passage, ...]:
        if self.stage in {"fetch_required", "both"}:
            self._calls += 1
            if self.schedule.should_fail(self._calls):
                raise self.exc_factory()
        return self.inner.fetch_required(ids)

    def search(self, q: SearchQuery) -> tuple[ScoredPassage, ...]:
        if self.stage in {"search", "both"}:
            self._calls += 1
            if self.schedule.should_fail(self._calls):
                raise self.exc_factory()
        return self.inner.search(q)


# ---------------------------------------------------------------------------
# LedgerRepository wrapper
# ---------------------------------------------------------------------------


@dataclass
class FaultInjectingLedgerRepository:
    inner: LedgerRepository
    exc_factory: Callable[[], BaseException]
    schedule: Schedule = field(default_factory=lambda: Schedule(FailureSchedule.ALWAYS))
    stage: str = "append_record"  # "head" | "append_record" | "both"
    _calls: int = 0

    def head(self) -> LedgerRecord | None:
        if self.stage in {"head", "both"}:
            self._calls += 1
            if self.schedule.should_fail(self._calls):
                raise self.exc_factory()
        return self.inner.head()

    def append_record(self, record: LedgerRecord) -> None:
        if self.stage in {"append_record", "both"}:
            self._calls += 1
            if self.schedule.should_fail(self._calls):
                raise self.exc_factory()
        self.inner.append_record(record)

    def all(self) -> tuple[LedgerRecord, ...]:
        return self.inner.all()

    def find_by_decision_id(self, decision_id: DecisionId) -> tuple[LedgerRecord, ...]:
        return self.inner.find_by_decision_id(decision_id)

    def with_append_lock(self) -> object:
        return self.inner.with_append_lock()


# ---------------------------------------------------------------------------
# Fault-injecting embedder (for model-mismatch at query time)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MismatchedEmbedder:
    """An embedder whose model_id / dimension are deliberately different
    from the store's registered values; constructing a retriever against
    the store must raise ConfigurationError at construction time."""

    model_id: EmbeddingModelId
    dimension: int

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.0,) * self.dimension for _ in texts)
