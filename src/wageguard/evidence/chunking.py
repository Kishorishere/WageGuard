"""Chunker: HTML bytes -> stable, deterministic passages (spec §10.5, G-08).

Pure. The same bytes with the same chunker version always yield the
same tuple of Passages, byte-for-byte. Passage IDs are
`source_key@v{version_no}#p{ordinal:03d}` and passage content hashes
are SHA-256 of the normalized text (NFC + collapsed whitespace).
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

from wageguard.domain.identifiers import (
    ChunkerVersion,
    ContentHash,
    PassageId,
    SourceKey,
)
from wageguard.evidence.extraction import extract_units


@dataclass(frozen=True, slots=True)
class Passage:
    passage_id: PassageId
    text: str
    normalized_text: str
    heading_path: tuple[str, ...]
    char_start: int
    char_end: int
    token_count: int
    content_hash: ContentHash
    chunker_version: ChunkerVersion


def chunk_html(
    data: bytes,
    source_key: SourceKey,
    version_no: int,
    *,
    chunker_version: ChunkerVersion | None = None,
) -> tuple[Passage, ...]:
    if chunker_version is None:
        chunker_version = ChunkerVersion("v1")
    units = extract_units(data)
    passages: list[Passage] = []
    for i, unit in enumerate(units):
        normalized = unicodedata.normalize("NFC", unit.text).strip()
        content_hash = ContentHash(hashlib.sha256(normalized.encode("utf-8")).hexdigest())
        passages.append(
            Passage(
                passage_id=PassageId(
                    source_key=str(source_key),
                    version_no=version_no,
                    ordinal=i,
                ),
                text=unit.text,
                normalized_text=normalized,
                heading_path=unit.heading_path,
                char_start=unit.char_start,
                char_end=unit.char_end,
                token_count=len(normalized.split()),
                content_hash=content_hash,
                chunker_version=chunker_version,
            )
        )
    return tuple(passages)
