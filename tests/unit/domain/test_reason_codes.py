"""Every ReasonCode has a category and a human-readable template.

Adding a code without wiring it into both tables is a review failure —
caught here, not in integration or later.
"""

from __future__ import annotations

import pytest

from wageguard.domain.reason_codes import (
    ReasonCategory,
    ReasonCode,
    category_of,
    template_of,
)


@pytest.mark.parametrize("code", list(ReasonCode))
def test_every_code_has_a_category(code: ReasonCode) -> None:
    cat = category_of(code)
    assert isinstance(cat, ReasonCategory)


@pytest.mark.parametrize("code", list(ReasonCode))
def test_every_code_has_a_non_empty_template(code: ReasonCode) -> None:
    tpl = template_of(code)
    assert isinstance(tpl, str)
    assert tpl.strip() != ""


def test_categories_are_a_closed_set() -> None:
    assert set(ReasonCategory) == {
        ReasonCategory.DECISION,
        ReasonCategory.ABSTENTION_DATA,
        ReasonCategory.ABSTENTION_SCOPE,
        ReasonCategory.REJECTION,
        ReasonCategory.FAULT,
    }


def test_values_are_lower_snake_case() -> None:
    for code in ReasonCode:
        assert code.value == code.value.lower()
        assert " " not in code.value
        assert "-" not in code.value
