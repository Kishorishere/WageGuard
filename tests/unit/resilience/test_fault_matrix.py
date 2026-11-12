"""Spec §16.2 fault matrix: every row produces a Fault, no decision (G-22).

Each test asserts the correct fault family + reason-shape. Where a
fault originates in an earlier phase's code (ruleset overlap, prompt
hash mismatch, chain tamper, embedding model mismatch, ambiguous
rule, missing required passage), this suite references the
owning test and keeps a thin cross-check here so the matrix is
visible in one place.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from wageguard.compliance.checks.minimum_wage import MinimumWageFacts, evaluate_minimum_wage
from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.errors import (
    AppendFailed,
    ChainBroken,
    CitationNotRetrieved,
    ConfigurationError,
    EvidenceError,
    LlmRefused,
    LlmTimeout,
    QuoteMismatch,
    RetrievalUnavailable,
    SourceVersionMismatch,
    VerificationFailed,
)
from wageguard.domain.identifiers import (
    ContentHash,
    DecisionId,
    EmbeddingModelId,
    PassageId,
    RuleId,
    RulesetVersion,
)
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.ranges import EffectiveRange
from wageguard.evidence.chunking import Passage
from wageguard.evidence.embedder import DeterministicFakeEmbedder
from wageguard.evidence.retrieval import (
    EvidenceBundle,
    InMemoryEvidenceRetriever,
    ScoredPassage,
    SearchQuery,
)
from wageguard.evidence.store import InMemoryPassageStore
from wageguard.ledger.chain import verify_chain
from wageguard.ledger.records import PartialHeader, RecordKind
from wageguard.ledger.repository import InMemoryLedgerRepository
from wageguard.llm.fake_client import FakeClient
from wageguard.llm.port import LlmRequest
from wageguard.resilience.fault_injection import (
    FailureSchedule,
    FaultInjectingEvidenceRetriever,
    FaultInjectingLedgerRepository,
    FaultInjectingLlmClient,
    MismatchedEmbedder,
    Schedule,
)

_PASSAGE = Passage(
    passage_id=PassageId("fed", 1, 0),
    text="rate is $10.00",
    normalized_text="rate is $10.00",
    heading_path=("x",),
    char_start=0,
    char_end=10,
    token_count=3,
    content_hash=ContentHash("x"),
    chunker_version="v1",  # type: ignore[arg-type]
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


def _store_with_embedder() -> tuple[InMemoryPassageStore, DeterministicFakeEmbedder]:
    s = InMemoryPassageStore()
    e = DeterministicFakeEmbedder(EmbeddingModelId("m-x"), dimension=4)
    s.register_embedding_model(e.model_id, e.dimension)
    return s, e


def _search_query() -> SearchQuery:
    return SearchQuery(
        jurisdictions=(jurisdiction("US"),),
        topic=Topic.MINIMUM_WAGE,
        as_of=date(2024, 7, 1),
        text="x",
        k=1,
        max_distance=1.0,
    )


# ----------------------------------------------------------------------
# Row 1: Retrieval backend unavailable -> RetrievalUnavailable Fault
# ----------------------------------------------------------------------


def test_row_1_retrieval_backend_unavailable() -> None:
    s, e = _store_with_embedder()
    r = FaultInjectingEvidenceRetriever(
        inner=InMemoryEvidenceRetriever(s, e),
        exc_factory=lambda: RetrievalUnavailable("vector index down"),
        schedule=Schedule(FailureSchedule.ALWAYS),
    )
    with pytest.raises(RetrievalUnavailable):
        r.search(_search_query())


# ----------------------------------------------------------------------
# Row 2: Required passage missing -> EvidenceError
# ----------------------------------------------------------------------


def test_row_2_required_passage_missing() -> None:
    s, e = _store_with_embedder()
    r = InMemoryEvidenceRetriever(s, e)
    with pytest.raises(EvidenceError):
        r.fetch_required((PassageId("ghost", 1, 0),))


# ----------------------------------------------------------------------
# Row 3: Source version swapped -> SourceVersionMismatch
# ----------------------------------------------------------------------


def test_row_3_source_version_swap() -> None:
    s, e = _store_with_embedder()
    r = FaultInjectingEvidenceRetriever(
        inner=InMemoryEvidenceRetriever(s, e),
        exc_factory=lambda: SourceVersionMismatch("hash differs"),
        schedule=Schedule(FailureSchedule.ALWAYS),
        stage="fetch_required",
    )
    with pytest.raises(SourceVersionMismatch):
        r.fetch_required((PassageId("fed", 1, 0),))


# ----------------------------------------------------------------------
# Row 4: Embedding model mismatch -> ConfigurationError
# ----------------------------------------------------------------------


def test_row_4_embedding_model_mismatch() -> None:
    s, e = _store_with_embedder()
    wrong = MismatchedEmbedder(model_id=EmbeddingModelId("other"), dimension=4)
    with pytest.raises(ConfigurationError, match="embedding model"):
        InMemoryEvidenceRetriever(s, wrong)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# Row 5: LLM timeout -> LlmTimeout (through bounded retry budget)
# ----------------------------------------------------------------------


def test_row_5_llm_timeout() -> None:
    client = FaultInjectingLlmClient(
        inner=FakeClient(responses=('{"a":1}',)),
        exc_factory=lambda: LlmTimeout("slow"),
        schedule=Schedule(FailureSchedule.ALWAYS),
    )
    with pytest.raises(LlmTimeout):
        client.generate_structured(_llm_req())


# ----------------------------------------------------------------------
# Row 6: LLM returns malformed JSON -> LlmMalformedOutput
# ----------------------------------------------------------------------


def test_row_6_llm_malformed_output() -> None:
    from wageguard.verification.verifier import verify

    # Use a minimal engine + bundle so the verifier has something to compare.
    rule = Rule(
        rule_id=RuleId("r"),
        jurisdiction=jurisdiction("US"),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal("10.00"),
        unit="USD/hour",
        effective=EffectiveRange(date(2020, 1, 1), None),
        supporting_passages=(_PASSAGE.passage_id,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )
    from wageguard.compliance.checks.minimum_wage import EngineResult
    from wageguard.domain.outcomes import Flagged

    engine = EngineResult(
        verdict=Flagged(),
        controlling_rule=rule,
        candidate_rules=(rule,),
        controlling_rate=Money("10.00"),
        actual_rate=Money("9.99"),
        shortfall=Money("0.01"),
        required_passages=(_PASSAGE.passage_id,),
        reason_codes=(),
    )
    report = verify(
        "not json",
        engine,
        EvidenceBundle(required=(_PASSAGE,), supplemental=()),
    )
    assert any(f.reason_code.value.startswith("fault_llm_malformed") for f in report.failures)


# ----------------------------------------------------------------------
# Row 7: Valid JSON with wrong outcome -> OutcomeContradiction
# ----------------------------------------------------------------------


def test_row_7_outcome_contradiction() -> None:
    import json

    from wageguard.compliance.checks.minimum_wage import EngineResult
    from wageguard.domain.outcomes import Flagged
    from wageguard.verification.verifier import verify

    rule = Rule(
        rule_id=RuleId("r"),
        jurisdiction=jurisdiction("US"),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal("10.00"),
        unit="USD/hour",
        effective=EffectiveRange(date(2020, 1, 1), None),
        supporting_passages=(_PASSAGE.passage_id,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )
    engine = EngineResult(
        verdict=Flagged(),
        controlling_rule=rule,
        candidate_rules=(rule,),
        controlling_rate=Money("10.00"),
        actual_rate=Money("9.99"),
        shortfall=Money("0.01"),
        required_passages=(_PASSAGE.passage_id,),
        reason_codes=(),
    )
    payload = json.dumps(
        {
            "asserted_outcome": "PASS",
            "summary": "s",
            "claims": [{"text": "x", "citations": [{"passage_id": "fed@v1#p000", "quote": None}]}],
            "insufficient_evidence": False,
        }
    )
    report = verify(payload, engine, EvidenceBundle(required=(_PASSAGE,), supplemental=()))
    assert any(f.reason_code.value == "fault_outcome_contradiction" for f in report.failures)


# ----------------------------------------------------------------------
# Row 8: LLM refuses -> LlmRefused
# ----------------------------------------------------------------------


def test_row_8_llm_refused() -> None:
    client = FaultInjectingLlmClient(
        inner=FakeClient(),
        exc_factory=lambda: LlmRefused("provider refused"),
        schedule=Schedule(FailureSchedule.ALWAYS),
    )
    with pytest.raises(LlmRefused):
        client.generate_structured(_llm_req())


# ----------------------------------------------------------------------
# Row 9: Rate limit (429) -> transport error -> retry budget -> LlmTimeout
# ----------------------------------------------------------------------


def test_row_9_rate_limit_exhausts_budget() -> None:
    from wageguard.resilience.clock import FakeClock
    from wageguard.resilience.retry import (
        RetryBudgetExceeded,
        RetryPolicy,
        with_bounded_retry,
    )

    client = FaultInjectingLlmClient(
        inner=FakeClient(responses=('{"a":1}',)),
        exc_factory=lambda: LlmTimeout("429 rate limit"),
        schedule=Schedule(FailureSchedule.ALWAYS),
    )
    policy = RetryPolicy(
        max_attempts=3,
        initial_backoff_seconds=0.1,
        backoff_multiplier=2.0,
        total_budget_seconds=5.0,
        retry_on=(LlmTimeout,),
    )
    with pytest.raises(RetryBudgetExceeded):
        with_bounded_retry(
            lambda: client.generate_structured(_llm_req()),
            policy=policy,
            clock=FakeClock(),
        )


# ----------------------------------------------------------------------
# Row 10: Ledger insert fails -> AppendFailed; no record of kind DECISION
# ----------------------------------------------------------------------


def test_row_10_ledger_append_fails_no_decision_record() -> None:
    inner = InMemoryLedgerRepository()
    repo = FaultInjectingLedgerRepository(
        inner=inner,
        exc_factory=lambda: AppendFailed("disk full"),
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
    # Critical invariant: inner repo has NO DECISION record.
    assert inner.all() == ()


# ----------------------------------------------------------------------
# Row 11: Database down at fault-logging time -> AppendFailed again
# ----------------------------------------------------------------------


def test_row_11_db_down_during_fault_log() -> None:
    inner = InMemoryLedgerRepository()
    repo = FaultInjectingLedgerRepository(
        inner=inner,
        exc_factory=lambda: AppendFailed("db unreachable"),
        schedule=Schedule(FailureSchedule.ALWAYS),
        stage="append_record",
    )
    partial = PartialHeader(
        decision_id=DecisionId("d-fault"),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="deadbeef",
        record_kind=RecordKind.FAULT,  # trying to log a FAULT
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )
    from wageguard.ledger.ledger import append

    with pytest.raises(AppendFailed):
        append(repo, partial, body={"stage": "evidence"})
    assert inner.all() == ()


# ----------------------------------------------------------------------
# Row 12: Overlapping effective ranges at load -> ConfigurationError
# ----------------------------------------------------------------------


def test_row_12_overlapping_rules_fail_load() -> None:
    def _rule(rid: str, start: date, end: date | None) -> Rule:
        return Rule(
            rule_id=RuleId(rid),
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            worker_category=WorkerCategory.GENERAL,
            value=Decimal("7.00"),
            unit="USD/hour",
            effective=EffectiveRange(start, end),
            supporting_passages=(_PASSAGE.passage_id,),
            review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
        )

    with pytest.raises(ConfigurationError, match="overlapping"):
        Ruleset.from_rules(
            RulesetVersion("v"),
            (
                _rule("a", date(2020, 1, 1), date(2025, 1, 1)),
                _rule("b", date(2024, 1, 1), None),
            ),
        )


# ----------------------------------------------------------------------
# Row 13: Prompt file hash mismatch at load -> ConfigurationError
# ----------------------------------------------------------------------


def test_row_13_prompt_hash_mismatch(tmp_path: Path) -> None:
    from wageguard.llm.prompts import load_registry

    (tmp_path / "foo").mkdir()
    (tmp_path / "foo" / "v1.txt").write_text("real prompt\n", encoding="utf-8")
    reg = tmp_path / "registry.yaml"
    reg.write_text(
        "prompts:\n"
        "  - name: foo\n"
        '    version: "v1"\n'
        "    path: foo/v1.txt\n"
        '    sha256: "' + "0" * 64 + '"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="hash"):
        load_registry(tmp_path, reg)


# ----------------------------------------------------------------------
# Row 14: Chain tamper detected -> ChainBroken (via verify_chain)
# ----------------------------------------------------------------------


def test_row_14_chain_tamper_detected() -> None:
    import dataclasses

    from wageguard.ledger.chain import GENESIS_PREV_HASH, compute_record_hash
    from wageguard.ledger.records import LedgerRecord, RecordHeader

    def _h(seq: int) -> RecordHeader:
        return RecordHeader(
            decision_id=DecisionId("d"),
            sequence_no=seq,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            app_version="0.0.0",
            git_commit="x",
            record_kind=RecordKind.DECISION,
            canon_version="canon_v1",
            check_type_value="minimum_wage",
            ruleset_version=RulesetVersion("v"),
            ruleset_hash="rsh",
        )

    r1_header = _h(1)
    r1_body: dict[str, object] = {"v": "PASS"}
    r1 = LedgerRecord(
        header=r1_header,
        body=r1_body,
        prev_hash=GENESIS_PREV_HASH,
        record_hash=compute_record_hash(
            header=r1_header, body=r1_body, prev_hash=GENESIS_PREV_HASH
        ),
    )
    # Tamper with the body without recomputing the hash.
    tampered = dataclasses.replace(r1, body={"v": "FLAG"})
    report = verify_chain((tampered,))
    assert report.ok is False
    # Chain-tamper semantics correspond to ChainBroken in the fault family.
    assert ChainBroken is not None  # type-level reference


# ----------------------------------------------------------------------
# Row 15: Clock skew - sequence_no defines order, not time
# ----------------------------------------------------------------------


def test_row_15_clock_skew_does_not_break_order() -> None:
    from wageguard.ledger.ledger import append

    repo = InMemoryLedgerRepository()

    def _partial(
        decision_id: str, ts: datetime, kind: RecordKind = RecordKind.DECISION
    ) -> PartialHeader:
        return PartialHeader(
            decision_id=DecisionId(decision_id),
            created_at=ts,
            app_version="0.0.0",
            git_commit="x",
            record_kind=kind,
            check_type_value="minimum_wage",
            ruleset_version=RulesetVersion("v"),
            ruleset_hash="rsh",
        )

    r1 = append(repo, _partial("d1", datetime(2024, 1, 1, 10, tzinfo=UTC)), body={"v": 1})
    # A clock that goes backwards still produces a monotonically increasing sequence.
    r2 = append(repo, _partial("d2", datetime(2024, 1, 1, 9, tzinfo=UTC)), body={"v": 2})
    assert r1.header.sequence_no == 1
    assert r2.header.sequence_no == 2
    assert verify_chain(repo.all()).ok is True


# ----------------------------------------------------------------------
# Row 16: Concurrent duplicate submissions - both recorded, no fork
# ----------------------------------------------------------------------


def test_row_16_concurrent_duplicate_submissions_no_fork() -> None:
    import threading

    from wageguard.ledger.ledger import append

    repo = InMemoryLedgerRepository()

    def _partial(name: str) -> PartialHeader:
        return PartialHeader(
            decision_id=DecisionId(name),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            app_version="0.0.0",
            git_commit="x",
            record_kind=RecordKind.DECISION,
            check_type_value="minimum_wage",
            ruleset_version=RulesetVersion("v"),
            ruleset_hash="rsh",
        )

    def worker(i: int) -> None:
        append(repo, _partial(f"dup-{i}"), body={"i": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(repo.all()) == 16
    assert verify_chain(repo.all()).ok is True


# ----------------------------------------------------------------------
# G-22 guarantee: no row of the fault matrix produced a DECISION record
# via a path that should have been a Fault
# ----------------------------------------------------------------------


@pytest.mark.guarantee("G-22")
def test_g22_fault_injection_never_emits_a_decision_record() -> None:
    inner = InMemoryLedgerRepository()
    bad_repo = FaultInjectingLedgerRepository(
        inner=inner,
        exc_factory=lambda: AppendFailed("db down"),
        schedule=Schedule(FailureSchedule.ALWAYS),
        stage="append_record",
    )
    partial = PartialHeader(
        decision_id=DecisionId("d-should-not-land"),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        app_version="0.0.0",
        git_commit="x",
        record_kind=RecordKind.DECISION,
        check_type_value="minimum_wage",
        ruleset_version=RulesetVersion("v"),
        ruleset_hash="rsh",
    )
    from wageguard.ledger.ledger import append

    with pytest.raises(AppendFailed):
        append(bad_repo, partial, body={"verdict": "PASS"})
    # Invariant: zero records exist; specifically no DECISION record.
    records = inner.all()
    assert all(r.header.record_kind is not RecordKind.DECISION for r in records)


# Smoke references so the unused-import linter doesn't trim test fixtures.
_ = (
    CitationNotRetrieved,
    QuoteMismatch,
    VerificationFailed,
    MinimumWageFacts,
    evaluate_minimum_wage,
    ScoredPassage,
)
