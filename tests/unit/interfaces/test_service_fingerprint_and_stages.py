"""Service-level guarantees: fault stages are spec-named, bodies carry input fingerprints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wageguard.config import PrivacyMode, Settings
from wageguard.interfaces.composition import build_check_service
from wageguard.interfaces.service import ResultCategory
from wageguard.resilience.clock import FakeClock

_VALID_STAGES = {"evidence", "llm", "verification", "ledger", "engine"}


def test_fault_stage_is_always_a_spec_named_value() -> None:
    """Injected ledger failure must produce a FAULT whose fault_stage
    is one of the spec-named set (never 'service' or similar)."""
    from wageguard.domain.errors import AppendFailed
    from wageguard.ledger.repository import InMemoryLedgerRepository
    from wageguard.resilience.fault_injection import (
        FailureSchedule,
        FaultInjectingLedgerRepository,
        Schedule,
    )

    broken = FaultInjectingLedgerRepository(
        inner=InMemoryLedgerRepository(),
        exc_factory=lambda: AppendFailed("db down"),
        schedule=Schedule(FailureSchedule.ALWAYS),
        stage="append_record",
    )
    artifacts = build_check_service(Settings(), ledger_repo=broken, clock=FakeClock())
    r = artifacts.service.run_check(
        json.dumps(
            {
                "check": "minimum_wage",
                "work_state": "US",
                "work_date": "2024-07-01",
                "pay_rate": "7.25",
                "pay_basis": "hourly",
                "worker_category": "general",
            }
        )
    )
    assert r.category is ResultCategory.FAULT
    assert r.fault_stage in _VALID_STAGES


def test_decision_body_carries_input_fingerprint_in_synthetic_mode(
    tmp_path: Path,
) -> None:
    settings = Settings(ledger_path=str(tmp_path / "ledger.ndjson"))
    artifacts = build_check_service(settings, clock=FakeClock())
    payload = {
        "check": "minimum_wage",
        "work_state": "US",
        "work_date": "2024-07-01",
        "pay_rate": "7.25",
        "pay_basis": "hourly",
        "worker_category": "general",
    }
    r = artifacts.service.run_check(json.dumps(payload))
    assert r.category is ResultCategory.DECISION
    assert r.decision_id is not None
    records = artifacts.ledger_repo.find_by_decision_id(r.decision_id)
    body = records[0].body
    assert "input_hash" in body
    assert isinstance(body["input_hash"], str)
    assert len(body["input_hash"]) == 64  # sha256 hex
    assert "input_snapshot" in body


def test_hash_only_privacy_mode_strips_snapshot(tmp_path: Path) -> None:
    settings = Settings(
        ledger_path=str(tmp_path / "ledger.ndjson"),
        privacy_mode=PrivacyMode.HASH_ONLY,
    )
    artifacts = build_check_service(settings, clock=FakeClock())
    payload = {
        "check": "minimum_wage",
        "work_state": "US",
        "work_date": "2024-07-01",
        "pay_rate": "7.25",
        "pay_basis": "hourly",
        "worker_category": "general",
    }
    r = artifacts.service.run_check(json.dumps(payload))
    assert r.decision_id is not None
    records = artifacts.ledger_repo.find_by_decision_id(r.decision_id)
    body = records[0].body
    assert "input_hash" in body
    assert "input_snapshot" not in body


def test_abstention_body_also_carries_fingerprint(tmp_path: Path) -> None:
    settings = Settings(ledger_path=str(tmp_path / "ledger.ndjson"))
    artifacts = build_check_service(settings, clock=FakeClock())
    r = artifacts.service.run_check(json.dumps({"check": "minimum_wage", "work_state": "US"}))
    assert r.category is ResultCategory.ABSTENTION
    records = artifacts.ledger_repo.find_by_decision_id(r.decision_id)  # type: ignore[arg-type]
    assert "input_hash" in records[0].body


def test_cli_check_and_ledger_show_see_the_same_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the CLI persistence bug: `check` then
    `ledger show` in the same shell returns the just-appended record."""
    ledger_path = tmp_path / "ledger.ndjson"
    monkeypatch.setenv("WAGEGUARD_LEDGER_PATH", str(ledger_path))

    input_path = tmp_path / "in.json"
    input_path.write_text(
        json.dumps(
            {
                "check": "minimum_wage",
                "work_state": "US",
                "work_date": "2024-07-01",
                "pay_rate": "7.25",
                "pay_basis": "hourly",
                "worker_category": "general",
            }
        ),
        encoding="utf-8",
    )

    from wageguard.interfaces.cli import main

    assert main(["check", str(input_path), "--json"]) == 0
    assert ledger_path.exists()
    # The file now contains one line.
    first_line = ledger_path.read_text(encoding="utf-8").strip().splitlines()[0]
    first_record = json.loads(first_line)
    decision_id = first_record["header"]["decision_id"]
    assert main(["ledger", "show", decision_id]) == 0
    assert main(["ledger", "verify"]) == 0
