"""Prompt registry: SHA-256 hash verified at load (spec §12.3, G-13)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from wageguard.domain.errors import ConfigurationError
from wageguard.llm.prompts import PromptRecord, load_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"
REGISTRY_PATH = REPO_ROOT / "prompts" / "registry.yaml"


def test_loads_the_committed_registry() -> None:
    reg = load_registry(PROMPTS_DIR, REGISTRY_PATH)
    rec = reg.get("explain_decision", "v1")
    assert isinstance(rec, PromptRecord)
    assert (
        rec.sha256
        == hashlib.sha256((PROMPTS_DIR / "explain_decision" / "v1.txt").read_bytes()).hexdigest()
    )
    assert "ENGINE OUTCOME" in rec.text


@pytest.mark.guarantee("G-13")
def test_hash_mismatch_raises(tmp_path: Path) -> None:
    (tmp_path / "foo").mkdir()
    prompt = tmp_path / "foo" / "v1.txt"
    prompt.write_text("the real prompt\n", encoding="utf-8")
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "prompts:\n"
        "  - name: foo\n"
        '    version: "v1"\n'
        "    path: foo/v1.txt\n"
        '    sha256: "' + "0" * 64 + '"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="hash"):
        load_registry(tmp_path, registry)


def test_missing_prompt_file_raises(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "prompts:\n"
        "  - name: missing\n"
        '    version: "v1"\n'
        "    path: missing/v1.txt\n"
        '    sha256: "' + "0" * 64 + '"\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_registry(tmp_path, registry)


def test_unknown_prompt_lookup_raises() -> None:
    reg = load_registry(PROMPTS_DIR, REGISTRY_PATH)
    with pytest.raises(ConfigurationError, match="unknown prompt"):
        reg.get("not_a_prompt", "v1")
