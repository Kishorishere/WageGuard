"""Composition root loads and verifies the prompt registry at startup."""

from __future__ import annotations

import pytest

from wageguard.config import Settings
from wageguard.domain.errors import ConfigurationError


def test_build_check_service_raises_on_bad_prompt_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Prompt-registry load is called inside build_check_service; make
    # it fail and assert the error bubbles out of composition.
    import wageguard.interfaces.composition as composition_mod

    def _boom(*args: object, **kwargs: object) -> object:
        raise ConfigurationError("prompt hash mismatch (injected)")

    monkeypatch.setattr(composition_mod, "load_registry", _boom)

    with pytest.raises(ConfigurationError, match="prompt hash"):
        composition_mod.build_check_service(Settings())


def test_build_check_service_exposes_loaded_prompts() -> None:
    from wageguard.interfaces.composition import build_check_service

    artifacts = build_check_service(Settings())
    record = artifacts.prompts.get("explain_decision", "v1")
    assert record.sha256  # non-empty
    assert record.text
