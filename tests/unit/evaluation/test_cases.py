"""Case schema loader + split integrity (spec §14.2, §14.9, G-20)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wageguard.domain.errors import ConfigurationError
from wageguard.evaluation.cases import (
    GoldenCase,
    Split,
    check_split_integrity,
    load_case,
    load_cases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEV_DIR = PROJECT_ROOT / "data" / "golden" / "dev"
HELDOUT_DIR = PROJECT_ROOT / "data" / "golden" / "heldout"


def _good_body() -> str:
    return """\
case_id: "mw-x-001"
split: "dev"
category: "threshold_boundary"
description: "..."
input:
  check: "minimum_wage"
  work_state: "US"
  pay_rate: "7.25"
expected:
  outcome: "PASS"
  reason_codes: []
  missing_fields: []
  required_citations: []
  forbidden_citations: []
label_basis:
  rule_id: "r1"
  passage_ids: []
  rationale: "ok"
answerable: true
"""


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_load_committed_dev_cases() -> None:
    cases = load_cases(DEV_DIR)
    assert len(cases) >= 2
    for c in cases:
        assert isinstance(c, GoldenCase)
        assert c.split is Split.DEV


def test_load_committed_heldout_cases() -> None:
    cases = load_cases(HELDOUT_DIR)
    assert len(cases) >= 1
    for c in cases:
        assert c.split is Split.HELDOUT


def test_loader_rejects_missing_split(tmp_path: Path) -> None:
    body = _good_body().replace('split: "dev"\n', "")
    with pytest.raises(ConfigurationError, match="split"):
        load_case(_write(tmp_path, "a.yaml", body))


def test_loader_rejects_unknown_split(tmp_path: Path) -> None:
    body = _good_body().replace('split: "dev"', 'split: "staging"')
    with pytest.raises(ConfigurationError, match="split"):
        load_case(_write(tmp_path, "a.yaml", body))


def test_loader_rejects_answerable_not_boolean(tmp_path: Path) -> None:
    body = _good_body().replace("answerable: true", 'answerable: "yes"')
    with pytest.raises(ConfigurationError, match="answerable"):
        load_case(_write(tmp_path, "a.yaml", body))


@pytest.mark.guarantee("G-20")
def test_committed_splits_have_no_overlap() -> None:
    cases = load_cases(DEV_DIR) + load_cases(HELDOUT_DIR)
    # No case_id in both dev and heldout.
    check_split_integrity(cases)


def test_duplicate_case_id_across_splits_is_rejected() -> None:
    from wageguard.evaluation.cases import ExpectedSpec, GoldenCase, LabelBasis

    def _case(split: Split) -> GoldenCase:
        return GoldenCase(
            case_id="dup-1",
            split=split,
            category="x",
            description="x",
            input_payload={},
            expected=ExpectedSpec("PASS", (), (), (), ()),
            label_basis=LabelBasis(None, (), "r"),
            answerable=True,
        )

    with pytest.raises(ConfigurationError, match="multiple splits"):
        check_split_integrity((_case(Split.DEV), _case(Split.HELDOUT)))
