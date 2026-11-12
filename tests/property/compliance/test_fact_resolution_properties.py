"""Resolver reports exactly the missing subset of required facts (spec §8.6)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from wageguard.compliance.facts import RawFacts, minimum_wage_facts, resolve
from wageguard.domain.enums import CheckType, PayBasis, WorkerCategory
from wageguard.domain.fields import FieldName
from wageguard.domain.outcomes import CannotDetermine

_ALL_VALUES: dict[FieldName, object] = {
    FieldName.WORK_STATE: "WA",
    FieldName.WORK_DATE: date(2024, 7, 1),
    FieldName.PAY_RATE: Decimal("15.50"),
    FieldName.PAY_BASIS: PayBasis.HOURLY,
    FieldName.WORKER_CATEGORY: WorkerCategory.GENERAL,
}


@pytest.mark.property
@settings(max_examples=500)
@given(subset=st.sets(st.sampled_from(list(_ALL_VALUES.keys())), min_size=1))
def test_resolver_reports_exactly_the_missing_subset(subset: set[FieldName]) -> None:
    values = {k: v for k, v in _ALL_VALUES.items() if k not in subset}
    rf = RawFacts(check=CheckType.MINIMUM_WAGE, values=values)
    res = resolve(minimum_wage_facts(), rf)
    abst = res.as_abstention()
    assert isinstance(abst, CannotDetermine)
    assert set(abst.fields) == subset


@pytest.mark.property
@settings(max_examples=200)
@given(subset=st.sets(st.sampled_from(list(_ALL_VALUES.keys()))))
def test_removing_no_fields_passes_resolution(subset: set[FieldName]) -> None:
    values = dict(_ALL_VALUES)
    rf = RawFacts(check=CheckType.MINIMUM_WAGE, values=values)
    res = resolve(minimum_wage_facts(), rf)
    # Sanity: with all fields present the resolution is clean regardless
    # of the (unused) subset.
    assert res.all_present is True
    _ = subset  # keep hypothesis happy
