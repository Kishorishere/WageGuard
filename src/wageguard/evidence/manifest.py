"""Source manifest: declarative list of official sources to ingest (spec §10.2).

Every source carries publisher, canonical URL, jurisdiction, topics, and
fetch metadata. The manifest is the single source of truth for what the
corpus contains; `data/snapshots/` holds the bytes and
`docs/source-register.md` is regenerated from both.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import yaml

from wageguard.domain.enums import Topic
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import SourceKey
from wageguard.domain.jurisdiction import Jurisdiction, jurisdiction
from wageguard.domain.ranges import EffectiveRange


class SourceType(StrEnum):
    STATUTE = "statute"
    REGULATION = "regulation"
    AGENCY_GUIDANCE = "agency_guidance"
    STATE_AGENCY = "state_agency"


class FetchMethod(StrEnum):
    HTML = "html"
    PDF = "pdf"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_key: SourceKey
    publisher: str
    title: str
    url: str
    jurisdiction: Jurisdiction
    topics: tuple[Topic, ...]
    source_type: SourceType
    fetch_method: FetchMethod
    notes: str = ""
    # Validity window for date-based retrieval filtering. None means
    # "assumed valid at any date", which is the default for the
    # prototype's single-snapshot corpus.
    validity: EffectiveRange | None = None


@dataclass(frozen=True, slots=True)
class SourceManifest:
    sources: tuple[SourceSpec, ...]


def load_source_manifest(path: Path) -> SourceManifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: top-level must be a mapping")
    rows = raw.get("sources")
    if not isinstance(rows, list) or not rows:
        raise ConfigurationError(f"{path}: sources must be a non-empty list")
    specs = tuple(_parse_source(idx, row) for idx, row in enumerate(rows))
    _check_unique_keys(specs)
    return SourceManifest(sources=specs)


def _check_unique_keys(specs: tuple[SourceSpec, ...]) -> None:
    seen: set[str] = set()
    for s in specs:
        if s.source_key in seen:
            raise ConfigurationError(f"duplicate source_key: {s.source_key}")
        seen.add(s.source_key)


def _require_str(row: Mapping[str, object], key: str, idx: int) -> str:
    v = row.get(key)
    if not isinstance(v, str) or not v:
        raise ConfigurationError(f"source[{idx}].{key}: required, must be a non-empty string")
    return v


def _parse_source(idx: int, row: object) -> SourceSpec:
    if not isinstance(row, dict):
        raise ConfigurationError(f"source[{idx}]: must be a mapping")

    source_key = _require_str(row, "source_key", idx)
    publisher = _require_str(row, "publisher", idx)
    title = _require_str(row, "title", idx)
    url = _require_str(row, "url", idx)

    try:
        jur = jurisdiction(_require_str(row, "jurisdiction", idx))
    except ValueError as exc:
        raise ConfigurationError(f"source[{idx}].jurisdiction: {exc}") from exc

    topics_raw = row.get("topics")
    if not isinstance(topics_raw, list) or not topics_raw:
        raise ConfigurationError(f"source[{idx}].topics: required non-empty list")
    topics: list[Topic] = []
    for t in topics_raw:
        if not isinstance(t, str):
            raise ConfigurationError(f"source[{idx}].topics: entries must be strings")
        try:
            topics.append(Topic(t))
        except ValueError as exc:
            raise ConfigurationError(f"source[{idx}].topics: {exc}") from exc

    try:
        source_type = SourceType(_require_str(row, "source_type", idx))
    except ValueError as exc:
        raise ConfigurationError(f"source[{idx}].source_type: {exc}") from exc

    try:
        fetch_method = FetchMethod(_require_str(row, "fetch_method", idx))
    except ValueError as exc:
        raise ConfigurationError(f"source[{idx}].fetch_method: {exc}") from exc

    notes_raw = row.get("notes", "")
    if not isinstance(notes_raw, str):
        raise ConfigurationError(f"source[{idx}].notes: must be a string")

    validity_raw = row.get("validity")
    validity: EffectiveRange | None = None
    if isinstance(validity_raw, dict):
        start_raw = validity_raw.get("start")
        end_raw = validity_raw.get("end")
        if not isinstance(start_raw, str):
            raise ConfigurationError(f"source[{idx}].validity.start: required ISO date string")
        try:
            start = date.fromisoformat(start_raw)
        except ValueError as exc:
            raise ConfigurationError(f"source[{idx}].validity.start: {exc}") from exc
        if end_raw is None:
            end: date | None = None
        elif isinstance(end_raw, str):
            try:
                end = date.fromisoformat(end_raw)
            except ValueError as exc:
                raise ConfigurationError(f"source[{idx}].validity.end: {exc}") from exc
        else:
            raise ConfigurationError(
                f"source[{idx}].validity.end: must be null or an ISO date string"
            )
        validity = EffectiveRange(start, end)
    elif validity_raw is not None:
        raise ConfigurationError(f"source[{idx}].validity: must be a mapping or null")

    return SourceSpec(
        source_key=SourceKey(source_key),
        publisher=publisher,
        title=title,
        url=url,
        jurisdiction=jur,
        topics=tuple(topics),
        source_type=source_type,
        fetch_method=fetch_method,
        notes=notes_raw,
        validity=validity,
    )
