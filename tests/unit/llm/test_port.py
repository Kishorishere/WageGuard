"""LlmRequest / LlmResponse / LlmUsage shape (spec §12.6)."""

from __future__ import annotations

import pytest

from wageguard.llm.port import LlmRequest, LlmResponse, LlmUsage


def test_request_is_frozen() -> None:
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
    with pytest.raises((AttributeError, TypeError)):
        req.model_id = "other"  # type: ignore[misc]


def test_usage_fields_nullable() -> None:
    u = LlmUsage(prompt_tokens=None, completion_tokens=None, total_tokens=None)
    assert u.prompt_tokens is None


def test_response_shape() -> None:
    r = LlmResponse(
        raw_text="{}",
        model_id="m",
        finish_reason="stop",
        usage=LlmUsage(None, None, None),
        latency_ms=42,
    )
    assert r.raw_text == "{}"
