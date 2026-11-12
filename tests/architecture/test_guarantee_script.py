"""The guarantee checker is code and can be wrong. Test it.

These unit tests exercise the parser and the diff logic without invoking
subprocess; the shell-level invariant (make docs-check clean) is covered
by Phase 0.9 verification.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script() -> ModuleType:
    path = PROJECT_ROOT / "scripts" / "check_guarantees.py"
    spec = importlib.util.spec_from_file_location("check_guarantees", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_guarantees"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return _load_script()


@pytest.mark.architecture
def test_parses_ids_only_under_active_heading(script: ModuleType) -> None:
    md = """
# Guarantees

## Active

| ID   | Guarantee | Owning test marker |
|------|-----------|--------------------|
| G-01 | one       | test_one           |
| G-02 | two       | test_two           |

## Planned

| ID   | Guarantee | Target phase |
|------|-----------|--------------|
| G-99 | nope      | later        |
""".strip()
    assert script.parse_active_ids(md) == {"G-01", "G-02"}


@pytest.mark.architecture
def test_ignores_malformed_ids(script: ModuleType) -> None:
    md = """
## Active

| ID    | Guarantee |
|-------|-----------|
| G-1   | bad       |
| G-001 | bad       |
| g-01  | bad       |
| G-07  | good      |
""".strip()
    assert script.parse_active_ids(md) == {"G-07"}


@pytest.mark.architecture
def test_phase_zero_registry_is_internally_consistent(script: ModuleType) -> None:
    """Phase 0 ships zero Active guarantees; the script must exit 0 on this repo."""
    md_path = PROJECT_ROOT / "docs" / "guarantees.md"
    active: set[str] = script.parse_active_ids(md_path.read_text(encoding="utf-8"))
    markers: dict[str, list[str]] = script.collect_marker_ids(PROJECT_ROOT / "tests")
    missing_tests = sorted(active - markers.keys())
    unknown_markers = sorted(markers.keys() - active)
    assert not missing_tests, f"Active guarantees without a test marker: {missing_tests}"
    assert not unknown_markers, f"Test markers for non-Active IDs: {unknown_markers}"
