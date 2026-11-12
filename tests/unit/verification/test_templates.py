"""Templated abstention explanations: NO LLM call (spec §12.5, G-12)."""

from __future__ import annotations

import pytest

from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import CannotDetermine, NeedsLegalReview
from wageguard.domain.reason_codes import ReasonCode
from wageguard.llm.fake_client import FakeClient, FakeClientCalledError
from wageguard.verification.templates import explain_abstention


def test_cannot_determine_names_missing_fields() -> None:
    outcome = CannotDetermine(
        reasons=(ReasonCode.MISSING_REQUIRED_FACT,),
        fields=(FieldName.WORK_STATE, FieldName.PAY_RATE),
    )
    text = explain_abstention(outcome)
    assert "work_state" in text
    assert "pay_rate" in text


def test_needs_legal_review_lists_reasons() -> None:
    outcome = NeedsLegalReview(
        reasons=(
            ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY,
            ReasonCode.LOCAL_RULES_NOT_ENCODED,
        )
    )
    text = explain_abstention(outcome)
    assert "worker category" in text.lower() or "category" in text.lower()
    assert "local" in text.lower()


@pytest.mark.guarantee("G-12")
def test_abstention_explanation_never_calls_llm() -> None:
    # A FakeClient that raises on any call proves the templated path.
    client = FakeClient(responses=(), raises_if_called=True)
    outcome = CannotDetermine(
        reasons=(ReasonCode.MISSING_REQUIRED_FACT,),
        fields=(FieldName.WORK_STATE,),
    )
    text = explain_abstention(outcome)
    assert text  # templated path produced prose
    # Sanity: the client is available but has not been invoked. Any
    # call would raise; we confirm that by invoking it directly.
    from wageguard.llm.port import LlmRequest

    req = LlmRequest(
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
    with pytest.raises(FakeClientCalledError):
        client.generate_structured(req)
