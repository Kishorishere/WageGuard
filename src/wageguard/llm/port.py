"""LlmClient Protocol and request/response types (spec §12.6).

Provider-agnostic. Real adapters (Gemini / Groq) implement this
Protocol; `FakeClient` and `CassetteClient` do the same for tests.
No vendor SDK imports anywhere in the package (user directive).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LlmUsage:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: Decimal | None = None


@dataclass(frozen=True, slots=True)
class LlmRequest:
    model_id: str
    prompt_name: str
    prompt_version: str
    prompt_sha256: str
    system_text: str
    user_text: str
    temperature: float
    max_tokens: int
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class LlmResponse:
    raw_text: str
    model_id: str
    finish_reason: str
    usage: LlmUsage
    latency_ms: int


class LlmClient(Protocol):
    def generate_structured(self, req: LlmRequest) -> LlmResponse: ...
