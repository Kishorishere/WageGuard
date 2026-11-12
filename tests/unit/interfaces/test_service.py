"""CheckService: end-to-end paths across the composition root."""

from __future__ import annotations

import json
from datetime import UTC

from wageguard.config import Settings
from wageguard.interfaces.composition import build_check_service
from wageguard.interfaces.service import ResultCategory
from wageguard.ledger.records import RecordKind
from wageguard.resilience.clock import FakeClock


def _service() -> object:
    return build_check_service(Settings(), clock=FakeClock())


def test_decision_path_pass() -> None:
    art = _service()
    raw = json.dumps(
        {
            "check": "minimum_wage",
            "work_state": "US",
            "work_date": "2024-07-01",
            "pay_rate": "7.25",
            "pay_basis": "hourly",
            "worker_category": "general",
        }
    )
    r = art.service.run_check(raw)
    assert r.category is ResultCategory.DECISION
    assert r.decision_id is not None
    records = art.ledger_repo.find_by_decision_id(r.decision_id)
    assert records[0].header.record_kind is RecordKind.DECISION


def test_decision_path_flag() -> None:
    art = _service()
    raw = json.dumps(
        {
            "check": "minimum_wage",
            "work_state": "US",
            "work_date": "2024-07-01",
            "pay_rate": "7.24",
            "pay_basis": "hourly",
            "worker_category": "general",
        }
    )
    r = art.service.run_check(raw)
    assert r.category is ResultCategory.DECISION
    assert "below" in r.detail


def test_abstention_missing_field() -> None:
    art = _service()
    raw = json.dumps({"check": "minimum_wage", "work_state": "US"})
    r = art.service.run_check(raw)
    assert r.category is ResultCategory.ABSTENTION
    assert r.decision_id is not None


def test_rejection_unknown_field() -> None:
    art = _service()
    raw = json.dumps({"check": "minimum_wage", "paY_rate": "15.00"})
    r = art.service.run_check(raw)
    assert r.category is ResultCategory.REJECTION
    assert r.decision_id is None


def test_scope_guard_routes_tipped_to_legal_review() -> None:
    art = _service()
    raw = json.dumps(
        {
            "check": "minimum_wage",
            "work_state": "US",
            "work_date": "2024-07-01",
            "pay_rate": "7.25",
            "pay_basis": "hourly",
            "worker_category": "tipped",
        }
    )
    r = art.service.run_check(raw)
    assert r.category is ResultCategory.ABSTENTION
    _ = UTC
