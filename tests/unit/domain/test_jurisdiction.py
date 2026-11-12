"""Jurisdiction syntactic validator."""

from __future__ import annotations

import pytest

from wageguard.domain.jurisdiction import is_valid_jurisdiction_code, jurisdiction


@pytest.mark.parametrize("code", ["US", "WA", "CA", "TX", "TESTLAND-A", "TESTLAND-Z"])
def test_valid(code: str) -> None:
    assert is_valid_jurisdiction_code(code)
    assert jurisdiction(code) == code


@pytest.mark.parametrize("code", ["us", "wa", "USA", "W", "WAX", "", "TESTLAND-AA", "123"])
def test_invalid(code: str) -> None:
    assert not is_valid_jurisdiction_code(code)
    with pytest.raises(ValueError, match="jurisdiction"):
        jurisdiction(code)
