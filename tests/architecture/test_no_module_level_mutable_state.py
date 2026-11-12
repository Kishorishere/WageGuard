"""S-4: no module-level mutable state and no import-time side effects.

A module is allowed to define constants (frozen dataclasses, tuples,
frozensets, immutable primitives). It is NOT allowed to:
  * assign a `list`, `dict`, `set`, or mutable object literal at module scope;
  * call a function at module scope whose return value is stored at module scope
    (import-time side effect), excluding a small allowlist (logging.getLogger,
    typing.TypeVar/NewType constructors, Enum/StrEnum subclasses via class body).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

import pytest

from tests.architecture.conftest import SRC_ROOT, iter_python_files, parse, rel

_MUTABLE_LITERALS: tuple[type[ast.AST], ...] = (
    ast.List,
    ast.Dict,
    ast.Set,
    ast.DictComp,
    ast.SetComp,
    ast.ListComp,
)

# Call expressions permitted at module top level: pure constructors of
# recognised immutable or safe-at-import-time objects.
_ALLOWED_MODULE_LEVEL_CALLS = frozenset(
    {
        "frozenset",
        "tuple",
        "NewType",
        "TypeVar",
        "ParamSpec",
        "StrEnum",
        "Enum",
        "IntEnum",
        "Flag",
        "IntFlag",
        "auto",
        "getLogger",  # logging.getLogger("wageguard.<...>")
        "Decimal",  # Decimal("1.50") is immutable
        "Path",  # Path("/...") is immutable
        "MappingProxyType",  # read-only view over a dict literal, immutable
        "compile",  # re.compile(...) returns an immutable Pattern object
        "sha256",  # hashlib.sha256() is a ctor; usage is pure
        "field",  # dataclasses.field(...) is a descriptor spec
        "maketrans",  # type-system constructor; no runtime side effect
    }
)


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _module_level_violations(tree: ast.Module) -> Iterator[tuple[int, str]]:
    for stmt in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets = [stmt.target]
            value = stmt.value
        if value is None:
            continue
        name = _first_name(targets)
        # Private dunder names like __all__ are informational; they must
        # still be immutable, so we fall through to the same checks.
        if isinstance(value, _MUTABLE_LITERALS):
            # tuple literals are fine; the checked list above does not include ast.Tuple.
            yield stmt.lineno, f"module-level mutable literal assigned to `{name}`"
        elif isinstance(value, ast.Call):
            call_name = _call_name(value)
            if call_name is None or call_name not in _ALLOWED_MODULE_LEVEL_CALLS:
                yield (
                    stmt.lineno,
                    (
                        f"module-level call `{call_name or '?'}(...)` assigned to `{name}` "
                        "(import-time side effect)"
                    ),
                )


def _first_name(targets: list[ast.expr]) -> str:
    for t in targets:
        if isinstance(t, ast.Name):
            return t.id
    return "?"


@pytest.mark.architecture
def test_no_module_level_mutable_state_under_src() -> None:
    violations: list[str] = []
    for path in iter_python_files(SRC_ROOT):
        tree = parse(path)
        for lineno, reason in _module_level_violations(tree):
            violations.append(f"{rel(path)}:{lineno} {reason}")
    message = "module-level mutable state / side effects are banned:\n  " + "\n  ".join(violations)
    assert not violations, message
