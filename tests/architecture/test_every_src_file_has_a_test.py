"""S-6 (deliverable 7): every file under src/ has a test module or is allowlisted.

The allowlist exists for genuine glue: package `__init__.py` markers,
protocol-only files, and generated schema code. Adding to the allowlist
requires a reviewer to agree in writing (in the diff).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.conftest import PROJECT_ROOT, SRC_ROOT, iter_python_files, rel

# Files that need no dedicated test module.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/wageguard/__init__.py",
        "src/wageguard/domain/__init__.py",
        "src/wageguard/intake/__init__.py",
        "src/wageguard/compliance/__init__.py",
        "src/wageguard/compliance/checks/__init__.py",
        "src/wageguard/evidence/__init__.py",
        "src/wageguard/llm/__init__.py",
        "src/wageguard/verification/__init__.py",
        "src/wageguard/ledger/__init__.py",
        "src/wageguard/replay/__init__.py",
        "src/wageguard/evaluation/__init__.py",
        "src/wageguard/interfaces/__init__.py",
        "src/wageguard/observability/__init__.py",
    }
)

TESTS_ROOT = PROJECT_ROOT / "tests"


def _candidate_test_names(src_file: Path) -> list[str]:
    """Plausible test module names for a given src file."""
    stem = src_file.stem
    package = src_file.relative_to(SRC_ROOT).parts[:-1]  # dirs above the file
    # Accept any of: test_<stem>.py, test_<pkg>_<stem>.py, <stem>_test.py.
    joined = "_".join(package)
    bases = {f"test_{stem}.py", f"{stem}_test.py"}
    if joined:
        bases.add(f"test_{joined}_{stem}.py")
    return sorted(bases)


@pytest.mark.architecture
def test_every_source_file_is_covered_by_a_test_module_or_allowlisted() -> None:
    missing: list[str] = []
    for src_file in iter_python_files(SRC_ROOT):
        rel_path = rel(src_file)
        if rel_path in _ALLOWLIST:
            continue
        candidates = _candidate_test_names(src_file)
        if not any(list(TESTS_ROOT.rglob(name)) for name in candidates):
            missing.append(f"{rel_path} has no test module (looked for: {', '.join(candidates)})")
    assert not missing, (
        "Every src/ file needs a dedicated test module or an explicit allowlist entry:\n  "
        + "\n  ".join(missing)
    )
