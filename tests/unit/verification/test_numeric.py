"""Numeric figure extraction + comparison (spec §12.4 check 8)."""

from __future__ import annotations

from decimal import Decimal

from wageguard.verification.numeric import extract_dollar_figures


def test_extracts_one_figure() -> None:
    assert extract_dollar_figures("Minimum is $10.00 per hour.") == (Decimal("10.00"),)


def test_extracts_multiple_figures() -> None:
    assert extract_dollar_figures("From $7.25 to $15.00.") == (
        Decimal("7.25"),
        Decimal("15.00"),
    )


def test_ignores_bare_numbers_without_dollar_sign() -> None:
    assert extract_dollar_figures("The employer has 50 workers.") == ()


def test_integer_dollar_figure() -> None:
    assert extract_dollar_figures("$15") == (Decimal("15"),)


def test_figures_with_comma_separator() -> None:
    assert extract_dollar_figures("$1,234.56") == (Decimal("1234.56"),)


def test_figure_at_boundary_of_sentence() -> None:
    assert extract_dollar_figures("$10.") == (Decimal("10"),)
