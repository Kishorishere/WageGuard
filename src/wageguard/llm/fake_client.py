"""FakeClient: scripted responses, used for unit tests (spec §12.6)."""

from __future__ import annotations

from dataclasses import dataclass, field

from wageguard.llm.port import LlmRequest, LlmResponse, LlmUsage


class FakeClientCalledError(AssertionError):
    """The fake client was called in a way the test did not script."""


@dataclass
class FakeClient:
    """Scripted LLM client.

    `responses` is a tuple of raw JSON strings; each `generate_structured`
    call pops the next one. If `raises_if_called` is true, every call
    raises `FakeClientCalledError` — used to prove abstention paths
    never call the LLM (G-12).
    """

    responses: tuple[str, ...] = ()
    raises_if_called: bool = False
    _calls: list[LlmRequest] = field(default_factory=list)

    @property
    def calls(self) -> tuple[LlmRequest, ...]:
        return tuple(self._calls)

    def generate_structured(self, req: LlmRequest) -> LlmResponse:
        if self.raises_if_called:
            raise FakeClientCalledError(
                "FakeClient.raises_if_called=True; this path must not call the LLM"
            )
        if len(self._calls) >= len(self.responses):
            raise FakeClientCalledError(
                f"FakeClient scripted responses exhausted after {len(self._calls)} calls"
            )
        self._calls.append(req)
        raw = self.responses[len(self._calls) - 1]
        return LlmResponse(
            raw_text=raw,
            model_id=req.model_id,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=None, completion_tokens=None, total_tokens=None),
            latency_ms=0,
        )
