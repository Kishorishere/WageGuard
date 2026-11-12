"""GeminiClient: request shape + error path coverage, no real network."""

from __future__ import annotations

import json

import httpx
import pytest

from wageguard.domain.errors import LlmMalformedOutput, LlmRefused, LlmTimeout
from wageguard.llm.gemini_client import GeminiClient
from wageguard.llm.port import LlmRequest


def _req() -> LlmRequest:
    return LlmRequest(
        model_id="gemini-flash-lite-latest",
        prompt_name="n",
        prompt_version="v1",
        prompt_sha256="h",
        system_text="",
        user_text="hello",
        temperature=0.0,
        max_tokens=16,
        timeout_seconds=5,
    )


def _ok_body(text: str = "OK") -> dict[str, object]:
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 7,
            "candidatesTokenCount": 1,
            "totalTokenCount": 8,
        },
    }


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    import wageguard.llm.gemini_client as module

    original_post = httpx.post

    def _patched_post(url: str, **kwargs: object) -> httpx.Response:
        with httpx.Client(transport=handler) as client:
            return client.post(url, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(module.httpx, "post", _patched_post)
    _ = original_post  # keep a reference so test teardown restores cleanly


def test_happy_path_returns_text_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "generateContent" in str(request.url)
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["contents"][0]["parts"][0]["text"] == "hello"
        return httpx.Response(200, json=_ok_body("hello back"))

    _install_transport(monkeypatch, httpx.MockTransport(handler))
    client = GeminiClient(api_key="k")
    resp = client.generate_structured(_req())
    assert resp.raw_text == "hello back"
    assert resp.usage.total_tokens == 8
    assert resp.finish_reason == "STOP"


def test_rate_limit_raises_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    _install_transport(monkeypatch, httpx.MockTransport(handler))
    with pytest.raises(LlmTimeout, match="rate limit"):
        GeminiClient(api_key="k").generate_structured(_req())


def test_server_error_raises_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server exploded")

    _install_transport(monkeypatch, httpx.MockTransport(handler))
    with pytest.raises(LlmRefused):
        GeminiClient(api_key="k").generate_structured(_req())


def test_missing_candidates_raises_malformed(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": []})

    _install_transport(monkeypatch, httpx.MockTransport(handler))
    with pytest.raises(LlmMalformedOutput, match="no candidates"):
        GeminiClient(api_key="k").generate_structured(_req())


def test_candidate_without_text_raises_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"content": {"parts": []}}]})

    _install_transport(monkeypatch, httpx.MockTransport(handler))
    with pytest.raises(LlmMalformedOutput, match="no text"):
        GeminiClient(api_key="k").generate_structured(_req())


def test_transport_timeout_raises_llm_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import wageguard.llm.gemini_client as module

    def _boom(*args: object, **kwargs: object) -> object:
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(module.httpx, "post", _boom)
    with pytest.raises(LlmTimeout, match="timeout"):
        GeminiClient(api_key="k").generate_structured(_req())
