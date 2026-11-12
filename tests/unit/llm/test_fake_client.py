"""FakeClient: scripted responses; raises-if-called mode."""

from __future__ import annotations

import pytest

from wageguard.llm.fake_client import FakeClient, FakeClientCalledError
from wageguard.llm.port import LlmRequest


def _req() -> LlmRequest:
    return LlmRequest(
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


def test_returns_scripted_response_in_order() -> None:
    client = FakeClient(responses=('{"a":1}', '{"b":2}'))
    r1 = client.generate_structured(_req())
    r2 = client.generate_structured(_req())
    assert r1.raw_text == '{"a":1}'
    assert r2.raw_text == '{"b":2}'


def test_exhausted_scripts_raise() -> None:
    client = FakeClient(responses=('{"a":1}',))
    client.generate_structured(_req())
    with pytest.raises(FakeClientCalledError, match="exhausted"):
        client.generate_structured(_req())


def test_raises_if_called_mode() -> None:
    client = FakeClient(responses=(), raises_if_called=True)
    with pytest.raises(FakeClientCalledError, match="raises_if_called"):
        client.generate_structured(_req())
