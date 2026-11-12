"""S-2: naive datetimes are banned anywhere under src/.

ruff's DTZ ruleset catches most calls; this test is a second line of
defense that walks the AST directly, so a new pattern or a disabled
ruff rule still gets caught.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

import pytest

from tests.architecture.conftest import SRC_ROOT, iter_python_files, parse, rel

# datetime.utcnow() is always naive.
# datetime(...) without a tzinfo kwarg is always naive.
# datetime.now() without tz is naive; with tz it is aware.
# datetime.fromtimestamp(x) without tz is naive.
# date.today() is intentionally allowed (date, not datetime).
_NAIVE_ATTR_CALLS = frozenset({"utcnow", "utcfromtimestamp"})
_NEEDS_TZ_CALLS = frozenset({"now", "fromtimestamp"})
# Position of the tzinfo parameter in datetime's positional signature.
_DATETIME_TZINFO_POSITION = 8


def _is_datetime_class(node: ast.expr) -> bool:
    if isinstance(node, ast.Name) and node.id == "datetime":
        return True
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "datetime"
        and isinstance(node.value, ast.Name)
        and node.value.id == "datetime"
    )


def _naive_hits(tree: ast.AST) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if not _is_datetime_class(func.value):
                continue
            if func.attr in _NAIVE_ATTR_CALLS:
                yield node.lineno, f"datetime.{func.attr}() is always naive"
                continue
            if func.attr in _NEEDS_TZ_CALLS and not _has_tz(node):
                yield node.lineno, f"datetime.{func.attr}() must be called with a tz"
                continue
        if _is_datetime_class(func) and not _has_tz(node):
            yield node.lineno, "datetime(...) constructed without a tzinfo"


def _has_tz(call: ast.Call) -> bool:
    if any(kw.arg in {"tz", "tzinfo"} for kw in call.keywords):
        return True
    # datetime.now(tz) is positional; same for fromtimestamp(ts, tz).
    if isinstance(call.func, ast.Attribute) and call.func.attr == "now":
        return len(call.args) >= 1
    if isinstance(call.func, ast.Attribute) and call.func.attr == "fromtimestamp":
        return len(call.args) >= 2
    if _is_datetime_class(call.func):
        return len(call.args) >= _DATETIME_TZINFO_POSITION
    return False


@pytest.mark.architecture
def test_no_naive_datetime_calls_under_src() -> None:
    violations: list[str] = []
    for path in iter_python_files(SRC_ROOT):
        tree = parse(path)
        for lineno, reason in _naive_hits(tree):
            violations.append(f"{rel(path)}:{lineno} {reason}")
    assert not violations, "naive datetime usage under src/ is banned:\n  " + "\n  ".join(
        violations
    )
