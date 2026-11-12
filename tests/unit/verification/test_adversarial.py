"""Adversarial verifier cases from spec §12.7 (twelve scenarios).

Each test constructs the model output directly (no LLM call) and
asserts the verifier produces the right reason code.
"""

from __future__ import annotations

import json
from typing import Any

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.domain.reason_codes import ReasonCode
from wageguard.evidence.retrieval import EvidenceBundle
from wageguard.verification.verifier import verify


def _base() -> dict[str, Any]:
    return {
        "asserted_outcome": "FLAG",
        "summary": "Pay $9.99 is below the controlling rate $10.00.",
        "claims": [
            {
                "text": "Controlling rate is $10.00.",
                "citations": [
                    {
                        "passage_id": "fed@v1#p000",
                        "quote": "controlling minimum rate is $10.00",
                    }
                ],
            }
        ],
        "insufficient_evidence": False,
    }


def _run(draft: dict[str, Any], engine: EngineResult, ev: EvidenceBundle):  # noqa: ANN202
    return verify(json.dumps(draft), engine, ev)


# §12.7 — all twelve adversarial cases


def test_1_fabricated_passage_id(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"][0]["citations"][0]["passage_id"] = "nope@v1#p000"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED
        for f in report.failures
    )


def test_2_real_passage_id_not_retrieved_for_this_run(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    # fed@v1#p999 is a syntactically valid id that just isn't in this run's bundle.
    bad = _base()
    bad["claims"][0]["citations"][0]["passage_id"] = "fed@v1#p999"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED
        for f in report.failures
    )


def test_3_passage_id_from_wrong_jurisdiction(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"][0]["citations"][0]["passage_id"] = "state@v1#p000"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED
        for f in report.failures
    )


def test_4_passage_id_from_superseded_source_version(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"][0]["citations"][0]["passage_id"] = "fed@v2#p000"  # superseded version
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED
        for f in report.failures
    )


def test_5_altered_quote(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"][0]["citations"][0]["quote"] = "controlling minimum rate is $12.00"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH for f in report.failures
    )


def test_6_quote_correct_but_wrong_passage_id(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    # Correct quote from the required passage but attributed to the supplemental one.
    bad["claims"][0]["citations"][0]["passage_id"] = "fed@v1#p001"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH for f in report.failures
    )


def test_7_model_asserts_opposite_outcome(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["asserted_outcome"] = "PASS"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION
        for f in report.failures
    )


def test_8_invented_dollar_figure(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["summary"] = "Pay $9.99 is below the rate of $12.50."
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any("12.50" in f.detail for f in report.failures)


def test_9_uncited_claim(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"].append({"text": "The employer is in retail.", "citations": []})
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert report.failures != ()


def test_10_wrong_schema_shape(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["extra_wild_field"] = True
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(f.reason_code == ReasonCode.FAULT_LLM_MALFORMED_OUTPUT for f in report.failures)


def test_11_instruction_like_text_in_quote_is_still_treated_as_data(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    # A quote whose text happens to say "ignore previous instructions" is
    # still just a string the verifier compares to the passage. If the
    # passage does not contain it, the verifier flags QuoteMismatch —
    # not any special "injection" handling. That proves the verifier
    # treats passage text as data.
    bad = _base()
    bad["claims"][0]["citations"][0]["quote"] = "ignore previous instructions"
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert any(
        f.reason_code == ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH for f in report.failures
    )


def test_12_empty_citations_list_on_decisive_outcome(
    flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
) -> None:
    bad = _base()
    bad["claims"][0]["citations"] = []
    report = _run(bad, flagged_engine_result, evidence_bundle)
    assert report.failures != ()
