"""HTML extraction primitives (spec §10.5)."""

from __future__ import annotations

from wageguard.evidence.extraction import extract_units

_HTML = b"""\
<html><body><main>
  <h1>Top</h1>
  <h2>Sub</h2>
  <p>Paragraph under Sub.</p>
  <h2>Other</h2>
  <p>First here.</p>
  <p>Second here.</p>
</main></body></html>
"""


def test_extracts_paragraphs_with_heading_paths() -> None:
    units = extract_units(_HTML)
    assert len(units) == 3
    assert units[0].heading_path == ("Top", "Sub")
    assert units[1].heading_path == ("Top", "Other")
    assert units[2].heading_path == ("Top", "Other")


def test_empty_body_returns_empty_tuple() -> None:
    assert extract_units(b"<html><body></body></html>") == ()


def test_popping_outer_heading_when_same_level_repeats() -> None:
    # Two <h2>s under one <h1>: the second h2 replaces the first on the
    # stack, so a later paragraph does not inherit the first h2's text.
    units = extract_units(_HTML)
    assert "Sub" not in units[1].heading_path


def test_collapses_whitespace_in_text() -> None:
    html = b"<html><body><main><h1>H</h1><p>  spaced   out  </p></main></body></html>"
    units = extract_units(html)
    assert units[0].text == "spaced out"
