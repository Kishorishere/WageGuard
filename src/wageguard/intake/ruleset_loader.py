"""YAML ruleset loader (spec §9.3).

Strict by design: every structural defect surfaces as
`ConfigurationError`, so a bad rule file keeps the process from
starting rather than quietly degrading at runtime.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import TypeVar

import yaml

from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.ranges import EffectiveRange

_E = TypeVar("_E", bound=Enum)


def load_ruleset_from_yaml(path: Path) -> Ruleset:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"malformed YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: top-level must be a mapping")

    version = raw.get("ruleset_version")
    if not isinstance(version, str) or not version:
        raise ConfigurationError(
            f"{path}: ruleset_version is required and must be a non-empty string"
        )

    rule_rows = raw.get("rules")
    if not isinstance(rule_rows, list) or not rule_rows:
        raise ConfigurationError(f"{path}: rules must be a non-empty list")

    parsed = tuple(_parse_rule(i, row) for i, row in enumerate(rule_rows))
    return Ruleset.from_rules(RulesetVersion(version), parsed)


def _require_str(row: dict[str, object], key: str, idx: int) -> str:
    v = row.get(key)
    if not isinstance(v, str) or not v:
        raise ConfigurationError(f"rule[{idx}].{key}: required, must be a non-empty string")
    return v


def _parse_decimal(row: dict[str, object], idx: int) -> Decimal:
    value = row.get("value")
    if not isinstance(value, str):
        raise ConfigurationError(
            f"rule[{idx}].value: must be a decimal string (got {type(value).__name__})"
        )
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ConfigurationError(f"rule[{idx}].value: not a valid decimal: {value!r}") from exc


def _parse_effective_range(row: dict[str, object], idx: int) -> EffectiveRange:
    effective_from = _require_str(row, "effective_from", idx)
    try:
        start = date.fromisoformat(effective_from)
    except ValueError as exc:
        raise ConfigurationError(f"rule[{idx}].effective_from: {exc}") from exc

    effective_to_raw = row.get("effective_to")
    end: date | None
    if effective_to_raw is None:
        end = None
    elif isinstance(effective_to_raw, str):
        try:
            end = date.fromisoformat(effective_to_raw)
        except ValueError as exc:
            raise ConfigurationError(f"rule[{idx}].effective_to: {exc}") from exc
    else:
        raise ConfigurationError(f"rule[{idx}].effective_to: must be null or an ISO date string")

    try:
        return EffectiveRange(start, end)
    except ValueError as exc:
        raise ConfigurationError(f"rule[{idx}].effective: {exc}") from exc


def _parse_passages(row: dict[str, object], idx: int) -> tuple[PassageId, ...]:
    passage_strings = row.get("supporting_passages")
    if not isinstance(passage_strings, list) or not passage_strings:
        raise ConfigurationError(
            f"rule[{idx}].supporting_passages: required, must be a non-empty list"
        )
    out: list[PassageId] = []
    for p in passage_strings:
        if not isinstance(p, str):
            raise ConfigurationError(f"rule[{idx}].supporting_passages: entries must be strings")
        try:
            out.append(PassageId.parse(p))
        except ValueError as exc:
            raise ConfigurationError(f"rule[{idx}].supporting_passages: {exc}") from exc
    return tuple(out)


def _parse_enum_field(row: dict[str, object], key: str, idx: int, cls: type[_E]) -> _E:
    raw = _require_str(row, key, idx)
    try:
        return cls(raw)
    except ValueError as exc:
        raise ConfigurationError(f"rule[{idx}].{key}: {exc}") from exc


def _parse_rule(idx: int, row: object) -> Rule:
    if not isinstance(row, dict):
        raise ConfigurationError(f"rule[{idx}]: must be a mapping")

    rule_id_str = _require_str(row, "rule_id", idx)
    unit = _require_str(row, "unit", idx)
    value_decimal = _parse_decimal(row, idx)

    try:
        jur = jurisdiction(_require_str(row, "jurisdiction", idx))
    except ValueError as exc:
        raise ConfigurationError(f"rule[{idx}].jurisdiction: {exc}") from exc

    topic = _parse_enum_field(row, "topic", idx, Topic)
    category = _parse_enum_field(row, "worker_category", idx, WorkerCategory)
    review_status = _parse_enum_field(row, "review_status", idx, ReviewStatus)
    effective = _parse_effective_range(row, idx)
    passages = _parse_passages(row, idx)

    notes_raw = row.get("notes", "")
    if not isinstance(notes_raw, str):
        raise ConfigurationError(f"rule[{idx}].notes: must be a string")

    return Rule(
        rule_id=RuleId(rule_id_str),
        jurisdiction=jur,
        topic=topic,
        worker_category=category,
        value=value_decimal,
        unit=unit,
        effective=effective,
        supporting_passages=tuple(passages),
        review_status=review_status,
        notes=notes_raw,
    )
