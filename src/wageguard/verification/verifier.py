"""Deterministic verifier over LLM output (spec §12.4, G-11).

Eight checks, in order, each with a distinct reason code. The verifier
runs ALL checks before returning so the fault record names every
defect at once. If the schema check fails, no other check can run —
there is no draft to inspect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from wageguard.compliance.checks.minimum_wage import EngineResult
from wageguard.domain.outcomes import Passed
from wageguard.domain.reason_codes import ReasonCode
from wageguard.evidence.chunking import Passage
from wageguard.evidence.retrieval import EvidenceBundle
from wageguard.llm.schemas import ExplanationDraft
from wageguard.verification.numeric import extract_dollar_figures
from wageguard.verification.quote_match import matches_after_normalize


@dataclass(frozen=True, slots=True)
class VerificationFailure:
    reason_code: ReasonCode
    detail: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    failures: tuple[VerificationFailure, ...]
    draft: ExplanationDraft | None


def verify(
    raw_output: str,
    engine_result: EngineResult,
    evidence: EvidenceBundle,
) -> VerificationReport:
    # Check 1: schema. Can't run any other check if parsing fails.
    try:
        payload = json.loads(raw_output)
        draft = ExplanationDraft.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        return VerificationReport(
            failures=(
                VerificationFailure(
                    reason_code=ReasonCode.FAULT_LLM_MALFORMED_OUTPUT,
                    detail=f"schema validation failed: {exc}",
                ),
            ),
            draft=None,
        )

    failures: list[VerificationFailure] = []

    # Check 2: outcome consistency.
    expected = "PASS" if isinstance(engine_result.verdict, Passed) else "FLAG"
    if draft.asserted_outcome != expected:
        failures.append(
            VerificationFailure(
                reason_code=ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION,
                detail=f"engine said {expected}, model asserted {draft.asserted_outcome}",
            )
        )

    # Check 3: insufficient evidence declared by the model.
    if draft.insufficient_evidence:
        failures.append(
            VerificationFailure(
                reason_code=ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION,
                detail="model flagged insufficient_evidence; outcome not supported",
            )
        )

    # Build the id -> Passage index for later checks.
    passage_by_id: dict[str, Passage] = {str(p.passage_id): p for p in evidence.required}
    for sp in evidence.supplemental:
        passage_by_id[str(sp.passage.passage_id)] = sp.passage
    valid_ids = set(passage_by_id)
    required_ids = {str(p.passage_id) for p in evidence.required}

    # Check 4: citation existence (every cited id is in the bundle).
    cited_ids: set[str] = set()
    for ci, claim in enumerate(draft.claims):
        for cj, citation in enumerate(claim.citations):
            if citation.passage_id not in valid_ids:
                failures.append(
                    VerificationFailure(
                        reason_code=ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED,
                        detail=(
                            f"claim[{ci}].citations[{cj}] references passage "
                            f"{citation.passage_id!r} not in this run's evidence bundle"
                        ),
                    )
                )
            cited_ids.add(citation.passage_id)

    # Check 5: every required passage cited at least once.
    for rid in sorted(required_ids):
        if rid not in cited_ids:
            failures.append(
                VerificationFailure(
                    reason_code=ReasonCode.FAULT_MISSING_REQUIRED_CITATION,
                    detail=f"required passage {rid!r} not cited in any claim",
                )
            )

    # Check 6: quote verification (where a non-null quote was supplied).
    for ci, claim in enumerate(draft.claims):
        for cj, citation in enumerate(claim.citations):
            if citation.quote is None:
                continue
            passage = passage_by_id.get(citation.passage_id)
            if passage is None:
                # Already caught by Check 4; skip to avoid double-counting.
                continue
            if not matches_after_normalize(citation.quote, passage.text):
                failures.append(
                    VerificationFailure(
                        reason_code=ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH,
                        detail=(
                            f"claim[{ci}].citations[{cj}] quote {citation.quote!r} "
                            f"not found in passage {citation.passage_id}"
                        ),
                    )
                )

    # Check 7: claim coverage — every claim has at least one citation.
    for ci, claim in enumerate(draft.claims):
        if not claim.citations:
            failures.append(
                VerificationFailure(
                    reason_code=ReasonCode.FAULT_LLM_MALFORMED_OUTPUT,
                    detail=f"claim[{ci}] has no citations (uncited claim)",
                )
            )

    # For a decisive outcome, the draft must claim something and cite it.
    if not draft.insufficient_evidence and not draft.claims:
        failures.append(
            VerificationFailure(
                reason_code=ReasonCode.FAULT_LLM_MALFORMED_OUTPUT,
                detail="decisive outcome produced no claims / empty citations",
            )
        )

    # Check 8: numeric agreement with engine values.
    engine_figures = {
        _canonical(engine_result.controlling_rate.amount),
        _canonical(engine_result.actual_rate.amount),
    }
    if engine_result.shortfall is not None:
        engine_figures.add(_canonical(engine_result.shortfall.amount))
    texts: list[str] = [draft.summary]
    texts.extend(c.text for c in draft.claims)
    for text in texts:
        for value in extract_dollar_figures(text):
            if _canonical(value) not in engine_figures:
                failures.append(
                    VerificationFailure(
                        reason_code=ReasonCode.FAULT_LLM_MALFORMED_OUTPUT,
                        detail=(
                            f"figure ${value} in explanation text is not in the "
                            f"engine's numeric context (allowed: "
                            f"{sorted(engine_figures)})"
                        ),
                    )
                )

    return VerificationReport(failures=tuple(failures), draft=draft)


_CANONICAL_PLACES = 4


def _canonical(amount: Decimal) -> str:
    """Normalize a Decimal to a canonical string for set membership."""
    try:
        quantum = Decimal(10) ** -_CANONICAL_PLACES
        return format(amount.quantize(quantum), "f")
    except InvalidOperation:  # pragma: no cover
        return str(amount)
