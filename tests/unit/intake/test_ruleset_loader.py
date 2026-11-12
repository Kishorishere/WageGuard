"""YAML ruleset loader: structural validation (spec §9.3, §9.7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wageguard.compliance.rules import Ruleset
from wageguard.domain.errors import ConfigurationError
from wageguard.intake.ruleset_loader import load_ruleset_from_yaml

_GOOD = """\
ruleset_version: "test.0.0"
rules:
  - rule_id: "us.mw.general"
    jurisdiction: "US"
    topic: "minimum_wage"
    worker_category: "general"
    value: "7.00"
    unit: "USD/hour"
    effective_from: "2020-01-01"
    effective_to: null
    supporting_passages:
      - "fake_src@v1#p000"
    review_status: "not_reviewed_by_counsel"
    notes: "synthetic"
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_loads_a_valid_ruleset(tmp_path: Path) -> None:
    rs = load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", _GOOD))
    assert isinstance(rs, Ruleset)
    assert rs.version == "test.0.0"
    assert len(rs.rules) == 1


def test_rejects_float_value(tmp_path: Path) -> None:
    body = _GOOD.replace('value: "7.00"', "value: 7.00")
    with pytest.raises(ConfigurationError, match="decimal string"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))


def test_rejects_unknown_review_status(tmp_path: Path) -> None:
    body = _GOOD.replace("not_reviewed_by_counsel", "rubber_stamped")
    with pytest.raises(ConfigurationError, match="review_status"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))


def test_rejects_rule_without_supporting_passages(tmp_path: Path) -> None:
    body = _GOOD.replace(
        'supporting_passages:\n      - "fake_src@v1#p000"', "supporting_passages: []"
    )
    with pytest.raises(ConfigurationError, match="supporting_passages"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))


def test_rejects_malformed_passage_id(tmp_path: Path) -> None:
    body = _GOOD.replace('"fake_src@v1#p000"', '"not an id"')
    with pytest.raises(ConfigurationError, match="passage"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))


def test_rejects_missing_ruleset_version(tmp_path: Path) -> None:
    body = _GOOD.replace('ruleset_version: "test.0.0"\n', "")
    with pytest.raises(ConfigurationError, match="ruleset_version"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))


def test_rejects_overlapping_rules(tmp_path: Path) -> None:
    body = (
        _GOOD
        + """\
  - rule_id: "us.mw.general.2"
    jurisdiction: "US"
    topic: "minimum_wage"
    worker_category: "general"
    value: "8.00"
    unit: "USD/hour"
    effective_from: "2020-01-01"
    effective_to: null
    supporting_passages:
      - "fake_src@v1#p000"
    review_status: "not_reviewed_by_counsel"
"""
    )
    with pytest.raises(ConfigurationError, match="overlapping"):
        load_ruleset_from_yaml(_write(tmp_path, "mw.yaml", body))
