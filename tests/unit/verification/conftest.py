"""Shared fixtures for verifier tests.

A minimal `(EngineResult, EvidenceBundle)` pair in the FLAG case,
built so test files can mint explanation JSON strings and verify
behaviour without touching the real engine or LLM.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.compliance.rules import Rule
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import ContentHash, PassageId, RuleId
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged
from wageguard.domain.ranges import EffectiveRange
from wageguard.evidence.chunking import Passage
from wageguard.evidence.retrieval import EvidenceBundle, ScoredPassage


def _passage(source_key: str, ordinal: int, text: str) -> Passage:
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


_REQUIRED_PASSAGE = _passage(
    "fed",
    0,
    "The controlling minimum rate is $10.00 per hour.",
)
_SUPPLEMENTAL_PASSAGE = _passage(
    "fed",
    1,
    "Employers subject to this rule must pay at least the stated minimum.",
)
_CONTROLLING_RULE = Rule(
    rule_id=RuleId("fed.mw"),
    jurisdiction=jurisdiction("US"),
    topic=Topic.MINIMUM_WAGE,
    worker_category=WorkerCategory.GENERAL,
    value=Decimal("10.00"),
    unit="USD/hour",
    effective=EffectiveRange(date(2020, 1, 1), None),
    supporting_passages=(_REQUIRED_PASSAGE.passage_id,),
    review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
)


@pytest.fixture
def flagged_engine_result() -> EngineResult:
    return EngineResult(
        verdict=Flagged(),
        controlling_rule=_CONTROLLING_RULE,
        candidate_rules=(_CONTROLLING_RULE,),
        controlling_rate=Money("10.00"),
        actual_rate=Money("9.99"),
        shortfall=Money("0.01"),
        required_passages=(_REQUIRED_PASSAGE.passage_id,),
        reason_codes=(),
    )


@pytest.fixture
def evidence_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        required=(_REQUIRED_PASSAGE,),
        supplemental=(ScoredPassage(_SUPPLEMENTAL_PASSAGE, distance=0.3),),
    )


@pytest.fixture
def required_passage() -> Passage:
    return _REQUIRED_PASSAGE


@pytest.fixture
def supplemental_passage() -> Passage:
    return _SUPPLEMENTAL_PASSAGE
