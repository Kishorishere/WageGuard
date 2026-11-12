"""Templated abstention explanations: no LLM call (spec §12.5, G-12)."""

from __future__ import annotations

from wageguard.domain.outcomes import CannotDetermine, NeedsLegalReview
from wageguard.domain.reason_codes import template_of


def explain_abstention(outcome: CannotDetermine | NeedsLegalReview) -> str:
    reason_text = " ".join(template_of(r) for r in outcome.reasons)
    if isinstance(outcome, CannotDetermine) and outcome.fields:
        fields = ", ".join(f.value for f in outcome.fields)
        return f"{reason_text} Fields: {fields}."
    return reason_text
