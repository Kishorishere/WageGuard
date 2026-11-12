"""Explainer orchestration: engine outcome + evidence -> LLM request (spec §12.2)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.compliance.rules import Rule
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import ContentHash, PassageId, RuleId
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged
from wageguard.domain.ranges import EffectiveRange
from wageguard.evidence.chunking import Passage
from wageguard.evidence.retrieval import EvidenceBundle
from wageguard.llm.explainer import build_llm_request, explain_decision
from wageguard.llm.fake_client import FakeClient
from wageguard.llm.prompts import load_registry

REPO_ROOT = Path(__file__).resolve().parents[3]


def _passage() -> Passage:
    return Passage(
        passage_id=PassageId("fed", 1, 0),
        text="The rate is $10.00.",
        normalized_text="The rate is $10.00.",
        heading_path=("Rates",),
        char_start=0,
        char_end=19,
        token_count=5,
        content_hash=ContentHash("x"),
        chunker_version="v1",  # type: ignore[arg-type]
    )


def _engine() -> EngineResult:
    p = _passage()
    rule = Rule(
        rule_id=RuleId("fed.mw"),
        jurisdiction=jurisdiction("US"),
        topic=Topic.MINIMUM_WAGE,
        worker_category=WorkerCategory.GENERAL,
        value=Decimal("10.00"),
        unit="USD/hour",
        effective=EffectiveRange(date(2020, 1, 1), None),
        supporting_passages=(p.passage_id,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )
    return EngineResult(
        verdict=Flagged(),
        controlling_rule=rule,
        candidate_rules=(rule,),
        controlling_rate=Money("10.00"),
        actual_rate=Money("9.99"),
        shortfall=Money("0.01"),
        required_passages=(p.passage_id,),
        reason_codes=(),
    )


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(required=(_passage(),), supplemental=())


def test_build_request_fills_controlled_fields() -> None:
    prompts = load_registry(REPO_ROOT / "prompts", REPO_ROOT / "prompts" / "registry.yaml")
    req = build_llm_request(
        engine_result=_engine(),
        evidence=_evidence(),
        prompts=prompts,
        model_id="gemini-flash-lite-latest",
    )
    assert req.model_id == "gemini-flash-lite-latest"
    assert req.prompt_name == "explain_decision"
    assert req.prompt_version == "v1"
    assert req.temperature == 0.0
    # Passage text must appear inside the delimited DATA block.
    assert "<passage_text_begin>" in req.user_text
    assert "<passage_text_end>" in req.user_text
    assert "The rate is $10.00." in req.user_text
    # Engine numbers surface explicitly.
    assert "10.00" in req.user_text
    assert "9.99" in req.user_text


def test_explain_decision_returns_response_and_request() -> None:
    prompts = load_registry(REPO_ROOT / "prompts", REPO_ROOT / "prompts" / "registry.yaml")
    scripted = json.dumps(
        {
            "asserted_outcome": "FLAG",
            "summary": "Pay below rate.",
            "claims": [{"text": "x", "citations": [{"passage_id": "fed@v1#p000", "quote": None}]}],
            "insufficient_evidence": False,
        }
    )
    client = FakeClient(responses=(scripted,))
    response, req = explain_decision(
        engine_result=_engine(),
        evidence=_evidence(),
        prompts=prompts,
        client=client,
        model_id="gemini-flash-lite-latest",
    )
    assert response.raw_text == scripted
    assert req.model_id == "gemini-flash-lite-latest"


def test_query_text_never_contains_uncontrolled_user_input() -> None:
    # The explainer builds the prompt from engine + evidence only. No
    # user-free-text field is exposed; the architecture test's
    # "controlled text" check is complemented by this behavioural one.
    prompts = load_registry(REPO_ROOT / "prompts", REPO_ROOT / "prompts" / "registry.yaml")
    req = build_llm_request(
        engine_result=_engine(),
        evidence=_evidence(),
        prompts=prompts,
        model_id="gemini-flash-lite-latest",
    )
    # Sanity: no stray "worker_name" or any PII-shaped placeholder leaks in.
    assert "worker_name" not in req.user_text
    assert "email" not in req.user_text
