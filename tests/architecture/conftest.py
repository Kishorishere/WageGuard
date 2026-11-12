"""Shared helpers for the architecture test tier.

These tests walk the `src/` tree with the standard library `ast` module,
so they have zero third-party dependencies and run in every tier that
exercises `tests/architecture/`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "wageguard"


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every `*.py` file under `root` in a deterministic order."""
    yield from sorted(p for p in root.rglob("*.py") if p.is_file())


def modules_under(subpath: str) -> Iterable[Path]:
    """Yield files under `src/wageguard/<subpath>/` as repo-relative Paths."""
    base = SRC_ROOT / subpath
    if not base.exists():
        return ()
    return iter_python_files(base)


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
