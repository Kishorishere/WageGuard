"""ExplanationDraft Pydantic schema (spec §12.2)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from wageguard.llm.schemas import ExplanationDraft


def _valid_draft() -> dict[str, object]:
    return {
        "asserted_outcome": "FLAG",
        "summary": "Pay is below the controlling rate.",
        "claims": [
            {
                "text": "Controlling rate was $10.00.",
                "citations": [{"passage_id": "fed@v1#p000", "quote": "ten dollars"}],
            }
        ],
        "insufficient_evidence": False,
    }


def test_valid_draft_parses() -> None:
    draft = ExplanationDraft.model_validate(_valid_draft())
    assert draft.asserted_outcome == "FLAG"
    assert len(draft.claims) == 1


def test_json_roundtrip_via_model_validate_json() -> None:
    draft = ExplanationDraft.model_validate_json(json.dumps(_valid_draft()))
    assert draft.insufficient_evidence is False


def test_extra_fields_rejected() -> None:
    bad = _valid_draft()
    bad["unexpected"] = True
    with pytest.raises(ValidationError):
        ExplanationDraft.model_validate(bad)


def test_asserted_outcome_closed_set() -> None:
    bad = _valid_draft()
    bad["asserted_outcome"] = "MAYBE"
    with pytest.raises(ValidationError):
        ExplanationDraft.model_validate(bad)


def test_summary_length_cap() -> None:
    bad = _valid_draft()
    bad["summary"] = "x" * 1000
    with pytest.raises(ValidationError):
        ExplanationDraft.model_validate(bad)


def test_null_quote_is_allowed() -> None:
    d = _valid_draft()
    d["claims"] = [{"text": "t", "citations": [{"passage_id": "p", "quote": None}]}]
    draft = ExplanationDraft.model_validate(d)
    assert draft.claims[0].citations[0].quote is None
