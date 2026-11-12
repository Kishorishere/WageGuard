"""Golden-case schema + loader (spec §14.2).

A case file states its own label basis (rule_id, passage_ids,
rationale), its split (`dev` | `heldout`), and whether the case is
answerable. The split is assigned BEFORE tuning and is never
reassigned (spec §14.2, G-20).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from wageguard.domain.errors import ConfigurationError


class Split(StrEnum):
    DEV = "dev"
    HELDOUT = "heldout"


@dataclass(frozen=True, slots=True)
class ExpectedSpec:
    outcome: str
    reason_codes: tuple[str, ...]
    missing_fields: tuple[str, ...]
    required_citations: tuple[str, ...]
    forbidden_citations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LabelBasis:
    rule_id: str | None
    passage_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class GoldenCase:
    case_id: str
    split: Split
    category: str
    description: str
    input_payload: Mapping[str, object]
    expected: ExpectedSpec
    label_basis: LabelBasis
    answerable: bool


def load_case(path: Path) -> GoldenCase:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: case must be a mapping")
    return _parse(path, raw)


def load_cases(dir_: Path) -> tuple[GoldenCase, ...]:
    if not dir_.exists():
        return ()
    return tuple(sorted((load_case(p) for p in dir_.glob("*.yaml")), key=lambda c: c.case_id))


def _require(row: Mapping[str, object], key: str, path: Path) -> object:
    if key not in row:
        raise ConfigurationError(f"{path}: missing required key {key!r}")
    return row[key]


def _require_str(row: Mapping[str, object], key: str, path: Path) -> str:
    v = _require(row, key, path)
    if not isinstance(v, str) or not v:
        raise ConfigurationError(f"{path}: {key!r} must be a non-empty string")
    return v


def _str_list(row: Mapping[str, object], key: str, path: Path) -> tuple[str, ...]:
    v = row.get(key, [])
    if not isinstance(v, list):
        raise ConfigurationError(f"{path}: {key!r} must be a list")
    for item in v:
        if not isinstance(item, str):
            raise ConfigurationError(f"{path}: {key!r} items must be strings")
    return tuple(v)


def _parse(path: Path, row: Mapping[str, object]) -> GoldenCase:
    case_id = _require_str(row, "case_id", path)
    split_raw = _require_str(row, "split", path)
    try:
        split = Split(split_raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"{path}: split must be 'dev' or 'heldout', got {split_raw!r}"
        ) from exc
    category = _require_str(row, "category", path)
    description = _require_str(row, "description", path)
    input_payload = _require(row, "input", path)
    if not isinstance(input_payload, dict):
        raise ConfigurationError(f"{path}: input must be a mapping")

    expected_raw = _require(row, "expected", path)
    if not isinstance(expected_raw, dict):
        raise ConfigurationError(f"{path}: expected must be a mapping")
    expected = ExpectedSpec(
        outcome=_require_str(expected_raw, "outcome", path),
        reason_codes=_str_list(expected_raw, "reason_codes", path),
        missing_fields=_str_list(expected_raw, "missing_fields", path),
        required_citations=_str_list(expected_raw, "required_citations", path),
        forbidden_citations=_str_list(expected_raw, "forbidden_citations", path),
    )

    label_raw = _require(row, "label_basis", path)
    if not isinstance(label_raw, dict):
        raise ConfigurationError(f"{path}: label_basis must be a mapping")
    rule_id = label_raw.get("rule_id")
    if rule_id is not None and not isinstance(rule_id, str):
        raise ConfigurationError(f"{path}: label_basis.rule_id must be a string or null")
    label_basis = LabelBasis(
        rule_id=rule_id,
        passage_ids=_str_list(label_raw, "passage_ids", path),
        rationale=_require_str(label_raw, "rationale", path),
    )

    answerable_raw = row.get("answerable")
    if not isinstance(answerable_raw, bool):
        raise ConfigurationError(f"{path}: answerable must be a boolean")

    return GoldenCase(
        case_id=case_id,
        split=split,
        category=category,
        description=description,
        input_payload=dict(input_payload),
        expected=expected,
        label_basis=label_basis,
        answerable=answerable_raw,
    )


def check_split_integrity(cases: tuple[GoldenCase, ...]) -> None:
    """Every case has a split; no case_id appears in both splits (G-20)."""
    seen: set[tuple[str, Split]] = set()
    by_id: dict[str, set[Split]] = {}
    for c in cases:
        seen.add((c.case_id, c.split))
        by_id.setdefault(c.case_id, set()).add(c.split)
    duplicates = [cid for cid, splits in by_id.items() if len(splits) > 1]
    if duplicates:
        raise ConfigurationError(f"case_id(s) appear in multiple splits: {sorted(duplicates)}")
