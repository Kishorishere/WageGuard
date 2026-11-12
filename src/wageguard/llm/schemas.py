"""ExplanationDraft: Pydantic schema the verifier parses first (spec §12.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_SUMMARY_MAX_LEN = 400


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passage_id: str
    quote: str | None = None


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    citations: tuple[Citation, ...] = ()


class ExplanationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asserted_outcome: Literal["PASS", "FLAG"]
    summary: str = Field(max_length=_SUMMARY_MAX_LEN)
    claims: tuple[Claim, ...] = ()
    insufficient_evidence: bool = False
