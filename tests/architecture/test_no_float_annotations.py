"""S-2: `float` is banned in annotations under compliance/ and ledger/.

Money is `Decimal`. A `float` sneaking into a public signature of a
compliance or ledger module is a correctness defect, not a style issue.
This test fails the build before such a change can merge.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

import pytest

from tests.architecture.conftest import modules_under, parse, rel

_FORBIDDEN_NAME = "float"
_SUBTREES = ("compliance", "ledger")


def _float_hits(tree: ast.AST) -> Iterator[ast.AST]:
    """Yield every annotation node that references bare `float`.

    Catches `x: float`, `def f(x: float) -> float: ...`, `list[float]`,
    `Decimal | float`, and `Annotated[float, ...]`. Attribute accesses
    like `numpy.float64` are deliberately not caught here — the ban is
    on the built-in `float` type used in annotations.
    """
    for node in ast.walk(tree):
        annotation: ast.AST | None = None
        if isinstance(node, ast.AnnAssign | ast.arg):
            annotation = node.annotation
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            annotation = node.returns
        if annotation is None:
            continue
        for sub in ast.walk(annotation):
            if isinstance(sub, ast.Name) and sub.id == _FORBIDDEN_NAME:
                yield sub


@pytest.mark.architecture
def test_no_float_annotations_in_core_packages() -> None:
    violations: list[str] = []
    for subtree in _SUBTREES:
        for path in modules_under(subtree):
            tree = parse(path)
            for hit in _float_hits(tree):
                violations.append(f"{rel(path)}:{hit.lineno} uses `float` in an annotation")
    assert not violations, (
        "float is banned in annotations under compliance/ and ledger/ (S-2). "
        "Use Decimal:\n  " + "\n  ".join(violations)
    )
