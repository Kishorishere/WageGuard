"""CLI exit-code contract (spec §17.2)."""

from __future__ import annotations

import json
from pathlib import Path

from wageguard.interfaces.cli import (
    EXIT_LEDGER_INTEGRITY,
    EXIT_OK,
    EXIT_REJECTION,
    main,
)


def _write_input(tmp_path: Path, payload: dict[str, object]) -> Path:
    p = tmp_path / "in.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_decision_exits_zero(tmp_path: Path) -> None:
    p = _write_input(
        tmp_path,
        {
            "check": "minimum_wage",
            "work_state": "US",
            "work_date": "2024-07-01",
            "pay_rate": "7.25",
            "pay_basis": "hourly",
            "worker_category": "general",
        },
    )
    assert main(["check", str(p), "--json"]) == EXIT_OK


def test_abstention_exits_zero(tmp_path: Path) -> None:
    p = _write_input(tmp_path, {"check": "minimum_wage", "work_state": "US"})
    assert main(["check", str(p), "--json"]) == EXIT_OK


def test_rejection_exits_two(tmp_path: Path) -> None:
    p = _write_input(tmp_path, {"check": "minimum_wage", "paY_rate": "15.00"})
    assert main(["check", str(p), "--json"]) == EXIT_REJECTION


def test_ledger_verify_on_fresh_repo_passes() -> None:
    # A fresh composition root starts with an empty ledger; verify is OK.
    assert main(["ledger", "verify"]) == EXIT_OK


def test_rules_validate_on_default_ruleset_passes() -> None:
    assert main(["rules", "validate"]) == EXIT_OK


# EXIT_LEDGER_INTEGRITY path is exercised in ledger-tier tests; this
# constant is referenced here so the symbol stays wired.
_ = EXIT_LEDGER_INTEGRITY
