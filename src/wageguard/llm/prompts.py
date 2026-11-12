"""Prompt registry with SHA-256 verification at load (spec §12.3, G-13).

Prompts live in `prompts/<name>/<version>.txt`. `prompts/registry.yaml`
lists every expected prompt with its SHA-256; loading recomputes the
hash of each file and raises `ConfigurationError` on any mismatch —
editing a released prompt without bumping the version is impossible.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import yaml

from wageguard.domain.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class PromptRecord:
    name: str
    version: str
    sha256: str
    text: str


@dataclass(frozen=True, slots=True)
class PromptRegistry:
    records: Mapping[tuple[str, str], PromptRecord]

    def get(self, name: str, version: str) -> PromptRecord:
        record = self.records.get((name, version))
        if record is None:
            raise ConfigurationError(f"unknown prompt: {name!r} version {version!r}")
        return record


def load_registry(prompts_dir: Path, registry_path: Path) -> PromptRegistry:
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"malformed YAML in {registry_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{registry_path}: top-level must be a mapping")
    rows = raw.get("prompts")
    if not isinstance(rows, list) or not rows:
        raise ConfigurationError(f"{registry_path}: prompts must be a non-empty list")

    records: dict[tuple[str, str], PromptRecord] = {}
    for idx, row in enumerate(rows):
        records[_record_key(idx, row, prompts_dir)] = _parse_record(idx, row, prompts_dir)
    return PromptRegistry(records=MappingProxyType(records))


def _record_key(idx: int, row: object, _prompts_dir: Path) -> tuple[str, str]:
    if not isinstance(row, dict):
        raise ConfigurationError(f"prompts[{idx}]: must be a mapping")
    name = row.get("name")
    version = row.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ConfigurationError(f"prompts[{idx}]: name and version are required strings")
    return (name, version)


def _parse_record(idx: int, row: object, prompts_dir: Path) -> PromptRecord:
    if not isinstance(row, dict):
        raise ConfigurationError(f"prompts[{idx}]: must be a mapping")

    def _req(key: str) -> str:
        v = row.get(key)
        if not isinstance(v, str) or not v:
            raise ConfigurationError(f"prompts[{idx}].{key}: required string")
        return v

    name = _req("name")
    version = _req("version")
    rel_path = _req("path")
    expected_sha = _req("sha256")

    path = prompts_dir / rel_path
    if not path.exists():
        raise ConfigurationError(f"prompts[{idx}]: file {path} not found")

    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha:
        raise ConfigurationError(
            f"prompts[{idx}] ({name}/{version}): registry hash does not match file at {path}; "
            f"expected {expected_sha}, got {actual_sha}"
        )
    return PromptRecord(
        name=name,
        version=version,
        sha256=actual_sha,
        text=data.decode("utf-8"),
    )
