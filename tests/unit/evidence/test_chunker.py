"""HTML chunker determinism and numeric-fidelity (spec §10.5, §10.9, G-08)."""

from __future__ import annotations

from pathlib import Path

import pytest

from wageguard.domain.identifiers import ChunkerVersion, SourceKey
from wageguard.evidence.chunking import chunk_html

FIXTURE = Path(__file__).resolve().parents[3] / "_fixtures" / "corpus" / "synthetic.html"


def _bytes() -> bytes:
    return FIXTURE.read_bytes()


class TestDeterminism:
    @pytest.mark.guarantee("G-08")
    def test_same_bytes_produce_identical_passages(self) -> None:
        a = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        b = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        assert a == b
        assert [str(p.passage_id) for p in a] == [str(p.passage_id) for p in b]

    def test_passage_ids_are_zero_padded_ordinals(self) -> None:
        passages = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        assert str(passages[0].passage_id) == "synthetic_src@v1#p000"
        if len(passages) > 1:
            assert str(passages[1].passage_id).endswith("#p001")


class TestChunkerVersion:
    def test_different_chunker_versions_produce_different_passages(self) -> None:
        a = chunk_html(_bytes(), SourceKey("s"), 1, chunker_version=ChunkerVersion("v1"))
        b = chunk_html(_bytes(), SourceKey("s"), 1, chunker_version=ChunkerVersion("v2"))
        assert a[0].chunker_version != b[0].chunker_version


class TestExtractedContentCoverage:
    def test_concatenated_text_covers_body_paragraphs(self) -> None:
        # The chunker must not silently drop paragraphs; §10.9 numeric
        # fidelity spot-check.
        passages = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        full_text = " ".join(p.text for p in passages)
        assert "covers" in full_text
        assert "$9.99" in full_text
        assert "2024-07-01" in full_text

    def test_currency_figures_preserved_verbatim(self) -> None:
        # Paragraph containing a currency figure must preserve it exactly.
        passages = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        currency_bearing = [p for p in passages if "$" in p.text]
        assert currency_bearing
        for p in currency_bearing:
            assert "$9.99" in p.text


class TestHeadingPath:
    def test_passage_carries_its_heading_path(self) -> None:
        passages = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        for p in passages:
            assert p.heading_path  # non-empty
        # The "$9.99" paragraph is under the "Rates" heading.
        rate_passages = [p for p in passages if "$9.99" in p.text]
        assert any("Rates" in " > ".join(p.heading_path) for p in rate_passages)


class TestPassageContentHash:
    def test_passage_content_hash_is_sha256_of_normalized_text(self) -> None:
        import hashlib as _hashlib

        passages = chunk_html(_bytes(), SourceKey("synthetic_src"), version_no=1)
        for p in passages:
            expected = _hashlib.sha256(p.normalized_text.encode("utf-8")).hexdigest()
            assert p.content_hash == expected
