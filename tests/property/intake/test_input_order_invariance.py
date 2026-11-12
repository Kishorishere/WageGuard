"""Field order in JSON must not affect the parsed RawFacts (spec §8.6)."""

from __future__ import annotations

import json
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wageguard.domain.fields import FieldName
from wageguard.intake.parser import parse_check_request

_FIELDS = (
    ("work_state", "WA"),
    ("work_date", "2024-07-01"),
    ("pay_rate", "15.50"),
    ("pay_basis", "hourly"),
    ("worker_category", "general"),
)


@pytest.mark.property
@settings(max_examples=200)
@given(perm=st.permutations([*_FIELDS]))
def test_field_order_does_not_change_parsed_facts(perm: list[tuple[str, str]]) -> None:
    payload: dict[str, str] = {"check": "minimum_wage"}
    for name, value in perm:
        payload[name] = value
    rf = parse_check_request(json.dumps(payload))
    assert rf.values[FieldName.WORK_DATE] == date(2024, 7, 1)
    assert rf.values[FieldName.WORK_STATE] == "WA"
