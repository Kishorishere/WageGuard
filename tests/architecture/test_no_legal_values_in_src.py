"""G-06: no legal (wage/threshold) value appears in src/.

A `Decimal("XX.XX")` literal with a fractional part under `src/` is the
shape wage figures take. Keeping them in `data/rules/**` (sourced from
official passages and reviewed) is the whole point of rules-as-data.
This test fails CI before such a value can land in code.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator

import pytest

from tests.architecture.conftest import SRC_ROOT, iter_python_files, parse, rel

_WAGE_SHAPED = re.compile(r"\d+\.\d+")


def _decimal_literal_hits(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield lineno + literal for any `Decimal("X.X...")` call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "Decimal":
            continue
        if len(node.args) != 1:
            continue
        arg = node.args[0]
        if (
            isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and _WAGE_SHAPED.fullmatch(arg.value.strip())
        ):
            yield node.lineno, arg.value


@pytest.mark.architecture
@pytest.mark.guarantee("G-06")
def test_no_wage_shaped_decimal_literal_under_src() -> None:
    violations: list[str] = []
    for path in iter_python_files(SRC_ROOT):
        tree = parse(path)
        for lineno, literal in _decimal_literal_hits(tree):
            violations.append(f"{rel(path)}:{lineno} Decimal({literal!r})")
    assert not violations, (
        "G-06: legal values (wage rates, thresholds) must live in "
        "`data/rules/**` tied to a sourced passage, not in src/. "
        "Offenders:\n  " + "\n  ".join(violations)
    )
