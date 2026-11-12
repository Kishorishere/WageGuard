"""S-4: domain and compliance code cannot import from the edges.

The domain core is pure. The compliance package depends on the domain
and standard library only. Both MUST NOT import from `llm/`, `evidence/`,
`interfaces/`, SQLAlchemy, or any HTTP library. The architecture test
is the one place this is enforced; violations fail CI before review.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

import pytest

from tests.architecture.conftest import modules_under, parse, rel

# Packages the domain core may NOT import.
_FORBIDDEN_FOR_DOMAIN = frozenset(
    {
        "wageguard.llm",
        "wageguard.evidence",
        "wageguard.interfaces",
        "wageguard.ledger.repository",  # the DB adapter; canonical is pure
        "wageguard.ledger.chain",
        "wageguard.observability",
        "sqlalchemy",
        "alembic",
        "httpx",
        "requests",
        "fastapi",
        "psycopg",
        "psycopg2",
        "pgvector",
        "pydantic",
    }
)

# Compliance may not import from edges either, but may use the domain core.
_FORBIDDEN_FOR_COMPLIANCE = _FORBIDDEN_FOR_DOMAIN


def _imports(tree: ast.AST) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            yield node.lineno, node.module


def _violations(subtree: str, forbidden: frozenset[str]) -> list[str]:
    hits: list[str] = []
    for path in modules_under(subtree):
        tree = parse(path)
        for lineno, mod in _imports(tree):
            if any(mod == f or mod.startswith(f + ".") for f in forbidden):
                hits.append(f"{rel(path)}:{lineno} imports forbidden module `{mod}`")
    return hits


@pytest.mark.architecture
def test_domain_does_not_import_from_edges() -> None:
    v = _violations("domain", _FORBIDDEN_FOR_DOMAIN)
    assert not v, "domain/ must depend on stdlib only (S-4):\n  " + "\n  ".join(v)


@pytest.mark.architecture
def test_compliance_does_not_import_from_edges() -> None:
    v = _violations("compliance", _FORBIDDEN_FOR_COMPLIANCE)
    assert not v, "compliance/ must not import from edges (S-4):\n  " + "\n  ".join(v)


@pytest.mark.architecture
def test_no_anthropic_or_openai_import_anywhere() -> None:
    """User directive: provider-agnostic LLM port; no vendor SDK imports."""
    from tests.architecture.conftest import SRC_ROOT, iter_python_files

    banned = {"anthropic", "openai"}
    hits: list[str] = []
    for path in iter_python_files(SRC_ROOT):
        tree = parse(path)
        for lineno, mod in _imports(tree):
            if mod in banned or any(mod.startswith(b + ".") for b in banned):
                hits.append(f"{rel(path)}:{lineno} imports banned vendor SDK `{mod}`")
    assert not hits, (
        "WageGuard uses a provider-agnostic LLM port; anthropic/openai SDK imports are "
        "not permitted:\n  " + "\n  ".join(hits)
    )
