"""Field names are a closed snake_case enum."""

from __future__ import annotations

from wageguard.domain.fields import FieldName


def test_values_are_lower_snake_case() -> None:
    for f in FieldName:
        assert f.value == f.value.lower()
        assert " " not in f.value
        assert "-" not in f.value


def test_values_are_unique() -> None:
    values = [f.value for f in FieldName]
    assert len(values) == len(set(values))


def test_includes_minimum_wage_core_fields() -> None:
    # The intake phase builds required-facts graphs over these; if a name
    # drifts here, Phase 2 fact resolution silently breaks.
    required = {"work_state", "work_date", "pay_rate", "pay_basis", "worker_category"}
    assert required <= {f.value for f in FieldName}
