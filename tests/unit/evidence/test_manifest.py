"""Source manifest YAML loader (spec §10.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wageguard.domain.enums import Topic
from wageguard.domain.errors import ConfigurationError
from wageguard.evidence.manifest import (
    FetchMethod,
    SourceManifest,
    SourceType,
    load_source_manifest,
)

FIXTURE = Path(__file__).resolve().parents[2] / "_fixtures" / "corpus" / "manifest.yaml"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_the_fixture() -> None:
    m = load_source_manifest(FIXTURE)
    assert isinstance(m, SourceManifest)
    assert len(m.sources) == 1
    spec = m.sources[0]
    assert spec.source_key == "synthetic_src"
    assert spec.topics == (Topic.MINIMUM_WAGE,)
    assert spec.source_type is SourceType.AGENCY_GUIDANCE
    assert spec.fetch_method is FetchMethod.HTML


def test_rejects_empty_sources(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="sources"):
        load_source_manifest(_write(tmp_path, "m.yaml", "sources: []\n"))


def test_rejects_duplicate_source_key(tmp_path: Path) -> None:
    body = """\
sources:
  - source_key: "a"
    publisher: "p"
    title: "t"
    url: "u"
    jurisdiction: "US"
    topics: ["minimum_wage"]
    source_type: "agency_guidance"
    fetch_method: "html"
  - source_key: "a"
    publisher: "p"
    title: "t"
    url: "u"
    jurisdiction: "US"
    topics: ["minimum_wage"]
    source_type: "agency_guidance"
    fetch_method: "html"
"""
    with pytest.raises(ConfigurationError, match="duplicate"):
        load_source_manifest(_write(tmp_path, "m.yaml", body))


def test_rejects_unknown_source_type(tmp_path: Path) -> None:
    body = """\
sources:
  - source_key: "a"
    publisher: "p"
    title: "t"
    url: "u"
    jurisdiction: "US"
    topics: ["minimum_wage"]
    source_type: "blog"
    fetch_method: "html"
"""
    with pytest.raises(ConfigurationError, match="source_type"):
        load_source_manifest(_write(tmp_path, "m.yaml", body))


def test_rejects_invalid_jurisdiction(tmp_path: Path) -> None:
    body = """\
sources:
  - source_key: "a"
    publisher: "p"
    title: "t"
    url: "u"
    jurisdiction: "usa"
    topics: ["minimum_wage"]
    source_type: "agency_guidance"
    fetch_method: "html"
"""
    with pytest.raises(ConfigurationError, match="jurisdiction"):
        load_source_manifest(_write(tmp_path, "m.yaml", body))


def test_rejects_unknown_topic(tmp_path: Path) -> None:
    body = """\
sources:
  - source_key: "a"
    publisher: "p"
    title: "t"
    url: "u"
    jurisdiction: "US"
    topics: ["overtime"]
    source_type: "agency_guidance"
    fetch_method: "html"
"""
    with pytest.raises(ConfigurationError, match="topics"):
        load_source_manifest(_write(tmp_path, "m.yaml", body))
