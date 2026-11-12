"""Quote normalization: NFC + whitespace + curly quotes/dashes (spec §12.4 check 6)."""

from __future__ import annotations

from wageguard.verification.quote_match import matches_after_normalize


def test_exact_substring_matches() -> None:
    assert matches_after_normalize("minimum wage", "The minimum wage is $10.")


def test_collapses_whitespace() -> None:
    assert matches_after_normalize("minimum  wage", "The minimum wage is $10.")


def test_strips_surrounding_whitespace() -> None:
    assert matches_after_normalize("  minimum wage  ", "The minimum wage is $10.")


def test_curly_quotes_normalized_to_straight() -> None:
    # Quote uses a curly apostrophe (U+2019); passage uses a straight one.
    assert matches_after_normalize("worker’s rate", "a worker's rate is set.")  # noqa: RUF001


def test_em_dash_normalized_to_hyphen() -> None:
    assert matches_after_normalize("rate—hourly", "the rate-hourly cap applies.")


def test_non_substring_rejected() -> None:
    assert not matches_after_normalize("overtime", "The minimum wage is $10.")


def test_nfc_normalization() -> None:
    # Combining acute vs precomposed 'é'.
    assert matches_after_normalize("café", "serves café drinks")


def test_empty_quote_does_not_match() -> None:
    # Policy: empty quote must not be used; treat as a non-match so the
    # verifier catches it.
    assert not matches_after_normalize("", "anything")
