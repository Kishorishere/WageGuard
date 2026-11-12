"""Verifier: eight checks over LLM output (spec §12.4, G-11).

Each check has a distinct reason code. Verifier collects ALL failures
before returning so the fault record is complete.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.domain.reason_codes import ReasonCode
from wageguard.evidence.retrieval import EvidenceBundle
from wageguard.verification.verifier import verify


def _good_draft() -> dict[str, Any]:
    return {
        "asserted_outcome": "FLAG",
        "summary": "Pay of $9.99 falls below the controlling rate of $10.00.",
        "claims": [
            {
                "text": "The controlling rate is $10.00.",
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


class TestHappyPath:
    @pytest.mark.guarantee("G-11")
    def test_valid_output_verifies(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        report = verify(json.dumps(_good_draft()), flagged_engine_result, evidence_bundle)
        assert report.failures == ()
        assert report.draft is not None
        assert report.draft.asserted_outcome == "FLAG"


class TestSchemaCheck:
    def test_malformed_json_yields_schema_failure(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        report = verify("not json", flagged_engine_result, evidence_bundle)
        codes = [f.reason_code for f in report.failures]
        assert ReasonCode.FAULT_LLM_MALFORMED_OUTPUT in codes
        assert report.draft is None

    def test_extra_fields_yields_schema_failure(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["extra"] = True
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(f.reason_code == ReasonCode.FAULT_LLM_MALFORMED_OUTPUT for f in report.failures)


class TestOutcomeConsistency:
    def test_wrong_asserted_outcome_contradicts(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["asserted_outcome"] = "PASS"
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            f.reason_code == ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION
            for f in report.failures
        )


class TestInsufficientEvidence:
    def test_model_flag_fails_the_run(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["insufficient_evidence"] = True
        bad["claims"] = []
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            f.reason_code == ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION
            or "insufficient_evidence" in f.detail
            for f in report.failures
        )


class TestCitationExistence:
    def test_fabricated_passage_id_is_caught(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["claims"][0]["citations"][0]["passage_id"] = "ghost@v1#p999"
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            f.reason_code == ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED
            for f in report.failures
        )


class TestRequiredCitationsPresent:
    def test_missing_required_citation_is_caught(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        # Cite ONLY a supplemental passage; the required passage is missing.
        bad = _good_draft()
        bad["claims"][0]["citations"][0]["passage_id"] = "fed@v1#p001"
        bad["claims"][0]["citations"][0]["quote"] = None
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            f.reason_code == ReasonCode.FAULT_MISSING_REQUIRED_CITATION for f in report.failures
        )


class TestQuoteMatch:
    def test_altered_quote_is_caught(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["claims"][0]["citations"][0]["quote"] = "a different quote not in the passage"
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            f.reason_code == ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH for f in report.failures
        )


class TestClaimCoverage:
    def test_uncited_claim_is_caught(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["claims"].append({"text": "An uncited claim.", "citations": []})
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any(
            "uncited" in f.detail.lower() or "no citation" in f.detail.lower()
            for f in report.failures
        )


class TestNumericAgreement:
    def test_invented_dollar_figure_is_caught(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["summary"] = "Pay of $9.99 is below the controlling rate of $42.00."
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        assert any("42" in f.detail or "$42" in f.detail for f in report.failures)


class TestAllFailuresCollectedBeforeReturning:
    def test_multiple_defects_surface_together(
        self, flagged_engine_result: EngineResult, evidence_bundle: EvidenceBundle
    ) -> None:
        bad = _good_draft()
        bad["asserted_outcome"] = "PASS"  # 1: contradiction
        bad["claims"][0]["citations"][0]["passage_id"] = (
            "ghost@v1#p999"  # 2: citation not retrieved
        )
        bad["claims"][0]["citations"][0]["quote"] = "not in passage"  # 3: (moot because id invalid)
        bad["summary"] = "An amount of $42.00 was found."  # 4: numeric mismatch
        report = verify(json.dumps(bad), flagged_engine_result, evidence_bundle)
        codes = {f.reason_code for f in report.failures}
        # The verifier must not stop at the first; at least 3 distinct
        # reason codes should surface from this single input.
        assert ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION in codes
        assert ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED in codes
        assert len(codes) >= 3
