"""FastAPI contract (spec §17.3, G-23, G-24, G-25)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from wageguard.config import Settings
from wageguard.interfaces.api import create_app
from wageguard.interfaces.composition import build_check_service
from wageguard.resilience.clock import FakeClock


def _app_with_keys(key: str = "test-secret") -> tuple[object, str, object]:
    settings = Settings(api_keys=f"checker:{key}")
    artifacts = build_check_service(settings, clock=FakeClock())
    return create_app(settings, artifacts=artifacts), key, artifacts


def test_post_check_decision_returns_201() -> None:
    app, key, _ = _app_with_keys()
    client = TestClient(app)
    payload = {
        "check": "minimum_wage",
        "work_state": "US",
        "work_date": "2024-07-01",
        "pay_rate": "7.25",
        "pay_basis": "hourly",
        "worker_category": "general",
    }
    r = client.post("/v1/checks", content=json.dumps(payload), headers={"x-api-key": key})
    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "decision"
    assert body["decision_id"] is not None


def test_post_check_rejection_returns_422() -> None:
    app, key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.post(
        "/v1/checks",
        content=json.dumps({"check": "minimum_wage", "paY_rate": "1"}),
        headers={"x-api-key": key},
    )
    assert r.status_code == 422


@pytest.mark.guarantee("G-24")
def test_post_check_fault_returns_503_and_names_stage() -> None:
    # Inject a ledger that fails every append; any check must come back
    # as a 503 whose body names a spec-known fault_stage.
    from wageguard.domain.errors import AppendFailed
    from wageguard.interfaces.api import create_app
    from wageguard.interfaces.composition import build_check_service
    from wageguard.ledger.repository import InMemoryLedgerRepository
    from wageguard.resilience.fault_injection import (
        FailureSchedule,
        FaultInjectingLedgerRepository,
        Schedule,
    )

    settings = Settings(api_keys="checker:test-secret")
    broken = FaultInjectingLedgerRepository(
        inner=InMemoryLedgerRepository(),
        exc_factory=lambda: AppendFailed("db down"),
        schedule=Schedule(FailureSchedule.ALWAYS),
        stage="append_record",
    )
    artifacts = build_check_service(settings, ledger_repo=broken, clock=FakeClock())
    app = create_app(settings, artifacts=artifacts)
    client = TestClient(app)
    r = client.post(
        "/v1/checks",
        content=json.dumps(
            {
                "check": "minimum_wage",
                "work_state": "US",
                "work_date": "2024-07-01",
                "pay_rate": "7.25",
                "pay_basis": "hourly",
                "worker_category": "general",
            }
        ),
        headers={"x-api-key": "test-secret"},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["fault_stage"] in {"evidence", "llm", "verification", "ledger", "engine"}


def test_missing_api_key_returns_401() -> None:
    app, _key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.post("/v1/checks", content=b"{}")
    assert r.status_code == 401


def test_wrong_api_key_returns_401() -> None:
    app, _key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.post("/v1/checks", content=b"{}", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_healthz_does_not_require_key() -> None:
    app, _key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200


@pytest.mark.guarantee("G-25")
def test_readyz_passes_on_healthy_build() -> None:
    app, _key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["prompt_hash"] == "ok"
    assert r.json()["ruleset_hash"] == "ok"


def test_get_decision_404_on_unknown_id() -> None:
    app, key, _ = _app_with_keys()
    client = TestClient(app)
    r = client.get("/v1/decisions/nope", headers={"x-api-key": key})
    assert r.status_code == 404


@pytest.mark.guarantee("G-23")
def test_cli_and_api_produce_same_category_for_same_input() -> None:
    # Spec §17.7: CLI and API share one service and produce identical
    # results for the same input.
    payload = {
        "check": "minimum_wage",
        "work_state": "US",
        "work_date": "2024-07-01",
        "pay_rate": "7.25",
        "pay_basis": "hourly",
        "worker_category": "general",
    }
    # API path.
    app, key, artifacts_api = _app_with_keys()
    client = TestClient(app)
    r = client.post("/v1/checks", content=json.dumps(payload), headers={"x-api-key": key})
    api_category = r.json()["category"]
    # Direct service path (same service type the CLI uses).
    from wageguard.interfaces.composition import build_check_service

    artifacts_cli = build_check_service(Settings(), clock=FakeClock())
    direct = artifacts_cli.service.run_check(json.dumps(payload))
    assert api_category == direct.category.value
