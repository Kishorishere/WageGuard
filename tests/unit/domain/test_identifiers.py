"""Identifiers are typed and never bare strings crossing module boundaries.

PassageId is a structured value: `source_key@vN#pNNN`. Parsing is strict
so a typo in a rule file becomes a load-time failure, not a silent miss
at retrieval time.
"""

from __future__ import annotations

import pytest

from wageguard.domain.identifiers import PassageId


class TestPassageIdFormat:
    def test_formats_as_canonical_string(self) -> None:
        pid = PassageId(source_key="dol_flsa_minwage", version_no=1, ordinal=7)
        assert str(pid) == "dol_flsa_minwage@v1#p007"

    def test_zero_pads_ordinal_to_three_digits(self) -> None:
        pid = PassageId(source_key="src", version_no=1, ordinal=0)
        assert str(pid) == "src@v1#p000"

    def test_ordinal_above_999_still_formats(self) -> None:
        pid = PassageId(source_key="src", version_no=1, ordinal=1234)
        # Longer ordinals use more digits; the floor is still three.
        assert str(pid).endswith("#p1234")


class TestPassageIdParse:
    def test_parses_canonical(self) -> None:
        pid = PassageId.parse("dol_flsa_minwage@v3#p042")
        assert pid.source_key == "dol_flsa_minwage"
        assert pid.version_no == 3
        assert pid.ordinal == 42

    def test_rejects_missing_at(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("dol_flsa_minwagev1#p001")

    def test_rejects_missing_hash(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("dol_flsa_minwage@v1p001")

    def test_rejects_non_integer_version(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("src@vA#p001")

    def test_rejects_non_integer_ordinal(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("src@v1#pAAA")

    def test_rejects_uppercase_source_key(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("DOL_Flsa@v1#p001")

    def test_rejects_empty_source_key(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("@v1#p001")

    def test_rejects_negative_version(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId.parse("src@v0#p001")


class TestPassageIdDirectConstructionValidation:
    """parse() rejects via regex; direct __init__ has its own guards."""

    def test_direct_construction_rejects_invalid_source_key(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId(source_key="UPPER", version_no=1, ordinal=0)

    def test_direct_construction_rejects_zero_version(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId(source_key="src", version_no=0, ordinal=0)

    def test_direct_construction_rejects_negative_ordinal(self) -> None:
        with pytest.raises(ValueError, match="passage id"):
            PassageId(source_key="src", version_no=1, ordinal=-1)


class TestPassageIdEquality:
    def test_equal_ids_compare_equal(self) -> None:
        a = PassageId("src", 1, 1)
        b = PassageId.parse("src@v1#p001")
        assert a == b
        assert hash(a) == hash(b)

    def test_different_ordinal_not_equal(self) -> None:
        assert PassageId("src", 1, 1) != PassageId("src", 1, 2)
