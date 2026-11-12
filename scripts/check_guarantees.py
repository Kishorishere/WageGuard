"""Enforce the guarantee <-> test marker invariants.

Rules (see docs/guarantees.md):
  1. Every Active guarantee has at least one test marked with its ID.
  2. Every `@pytest.mark.guarantee("G-NN")` marker references an Active ID.
  3. IDs are `G-NN`, zero-padded, two digits.

Exit codes:
  0 - clean
  1 - violations printed to stderr
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GUARANTEES_MD = PROJECT_ROOT / "docs" / "guarantees.md"
TESTS_ROOT = PROJECT_ROOT / "tests"

ID_RE = re.compile(r"\bG-\d{2}\b")


def parse_active_ids(markdown: str) -> set[str]:
    """Collect IDs listed under the `## Active` heading.

    The Active section ends at the next `## ` heading or EOF. We read IDs
    from the leading cell of each Markdown table row (ignoring header and
    separator rows).
    """
    active: set[str] = set()
    in_active = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_active = line == "## Active"
            continue
        if not in_active:
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if first in {"ID", ""} or set(first) <= set("-: "):
            continue
        m = ID_RE.fullmatch(first)
        if m is not None:
            active.add(m.group(0))
    return active


def _marker_ids_in_decorator(dec: ast.expr) -> Iterator[str]:
    """Yield guarantee IDs referenced by `@pytest.mark.guarantee("G-NN")`."""
    if not isinstance(dec, ast.Call):
        return
    func = dec.func
    # `pytest.mark.guarantee(...)` -> Attribute(attr="guarantee",
    #                                             value=Attribute(attr="mark", ...))
    if not isinstance(func, ast.Attribute) or func.attr != "guarantee":
        return
    if not isinstance(func.value, ast.Attribute) or func.value.attr != "mark":
        return
    for arg in dec.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            m = ID_RE.fullmatch(arg.value)
            if m is not None:
                yield m.group(0)


def collect_marker_ids(tests_root: Path) -> dict[str, list[str]]:
    """Return {guarantee_id: [test_locations]} across every test file."""
    hits: dict[str, list[str]] = {}
    for path in sorted(tests_root.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - surfaces as a real failure
            print(f"[docs-check] syntax error in {path}: {exc}", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            for dec in node.decorator_list:
                for gid in _marker_ids_in_decorator(dec):
                    location = f"{path.relative_to(PROJECT_ROOT)}::{node.name}"
                    hits.setdefault(gid, []).append(location)
    return hits


def main() -> int:
    if not GUARANTEES_MD.exists():
        print(f"[docs-check] {GUARANTEES_MD} not found", file=sys.stderr)
        return 1
    active = parse_active_ids(GUARANTEES_MD.read_text(encoding="utf-8"))
    markers = collect_marker_ids(TESTS_ROOT)

    missing_tests = sorted(active - markers.keys())
    unknown_marker_ids = sorted(markers.keys() - active)

    violations: list[str] = []
    for gid in missing_tests:
        violations.append(f"Active guarantee {gid} has no test marker in tests/")
    for gid in unknown_marker_ids:
        where = ", ".join(sorted(markers[gid]))
        violations.append(f"Test marker references non-Active guarantee {gid}: {where}")

    if violations:
        print("[docs-check] guarantee registry inconsistencies:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(
        f"[docs-check] OK: {len(active)} active guarantees, "
        f"{sum(len(v) for v in markers.values())} test markers across "
        f"{len(markers)} IDs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
