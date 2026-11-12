"""PassageId format/parse roundtrip (spec §7.5 Hypothesis criterion)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wageguard.domain.identifiers import PassageId

_source_keys = st.from_regex(r"[a-z][a-z0-9_]{0,31}", fullmatch=True)
_versions = st.integers(min_value=1, max_value=9999)
_ordinals = st.integers(min_value=0, max_value=99_999)


@pytest.mark.property
@given(source_key=_source_keys, version_no=_versions, ordinal=_ordinals)
def test_format_parse_roundtrip(source_key: str, version_no: int, ordinal: int) -> None:
    pid = PassageId(source_key=source_key, version_no=version_no, ordinal=ordinal)
    parsed = PassageId.parse(str(pid))
    assert parsed == pid


@pytest.mark.property
@given(s=st.text().filter(lambda t: "@" not in t or "#" not in t))
def test_malformed_strings_raise(s: str) -> None:
    with pytest.raises(ValueError, match="passage id"):
        PassageId.parse(s)
