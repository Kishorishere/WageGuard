"""FastAPI surface (spec §17.3) sharing one CheckService with the CLI (G-23).

HTTP status contract (G-24):
  201  decision OR abstention — a durable ledger record exists
  422  rejection (malformed input)
  503  fault (infrastructure) — body names the fault stage
  404  decision_id not found
  401  missing / unknown API key

/healthz is liveness; /readyz checks prompt and ruleset hashes (G-25).
"""

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from wageguard.config import Settings
from wageguard.interfaces.composition import CompositionArtifacts, build_check_service
from wageguard.interfaces.service import CheckResponse, ResultCategory


@dataclass(frozen=True, slots=True)
class ApiKey:
    role: str
    secret: str


def _parse_api_keys(raw: str) -> tuple[ApiKey, ...]:
    out: list[ApiKey] = []
    for raw_item in raw.split(","):
        item = raw_item.strip()
        if not item or ":" not in item:
            continue
        role, secret = item.split(":", 1)
        out.append(ApiKey(role=role.strip(), secret=secret.strip()))
    return tuple(out)


def _require_api_key(configured: tuple[ApiKey, ...], presented: str | None) -> ApiKey:
    if presented is None:
        raise HTTPException(status_code=401, detail="API key missing")
    for key in configured:
        if hmac.compare_digest(key.secret, presented):
            return key
    raise HTTPException(status_code=401, detail="API key invalid")


def _map_check_response_to_http(response: CheckResponse) -> Response:
    body: Mapping[str, object] = {
        "category": response.category.value,
        "decision_id": response.decision_id,
        "detail": response.detail,
        "fault_stage": response.fault_stage,
    }
    if response.category in {ResultCategory.DECISION, ResultCategory.ABSTENTION}:
        return JSONResponse(content=body, status_code=status.HTTP_201_CREATED)
    if response.category is ResultCategory.REJECTION:
        return JSONResponse(content=body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    # FAULT (G-24: 2xx only when a record exists).
    return JSONResponse(content=body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def create_app(
    settings: Settings | None = None,
    *,
    artifacts: CompositionArtifacts | None = None,
) -> FastAPI:
    """Build a FastAPI app sharing a CheckService with the CLI (G-23)."""
    settings = settings or Settings()
    artifacts = artifacts or build_check_service(settings)
    configured_keys = _parse_api_keys(settings.api_keys)

    app = FastAPI(title="WageGuard", version="0.0.0")

    def _auth(request: Request) -> ApiKey:
        return _require_api_key(configured_keys, request.headers.get("x-api-key"))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        checks: dict[str, str] = {}
        ruleset_hash_ok = bool(artifacts.rules.ruleset_hash)
        checks["ruleset_hash"] = "ok" if ruleset_hash_ok else "fail"
        # Prompt-hash readiness (G-25): if the prompts directory is
        # committed, loading the registry succeeds; a mismatch raises
        # ConfigurationError at load, which bubbles up to a 503 here.
        try:
            from pathlib import Path

            from wageguard.llm.prompts import load_registry

            root = Path(__file__).resolve().parents[3]
            load_registry(root / "prompts", root / "prompts" / "registry.yaml")
            checks["prompt_hash"] = "ok"
        except Exception as exc:
            checks["prompt_hash"] = f"fail: {exc}"
        all_ok = all(v == "ok" for v in checks.values())
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=checks, status_code=http_status)

    @app.post("/v1/checks")
    async def post_check(
        request: Request,
        _key: Annotated[ApiKey, Depends(_auth)],
    ) -> Response:
        raw = await request.body()
        response = artifacts.service.run_check(raw.decode("utf-8"))
        return _map_check_response_to_http(response)

    @app.get("/v1/decisions/{decision_id}")
    def get_decision(
        decision_id: str,
        _key: Annotated[ApiKey, Depends(_auth)],
    ) -> JSONResponse:
        from wageguard.domain.identifiers import DecisionId

        records = artifacts.ledger_repo.find_by_decision_id(DecisionId(decision_id))
        if not records:
            raise HTTPException(status_code=404, detail="decision not found")
        first = records[0]
        return JSONResponse(
            content={
                "decision_id": first.header.decision_id,
                "sequence_no": first.header.sequence_no,
                "record_kind": first.header.record_kind.value,
                "record_hash": first.record_hash,
            },
            status_code=200,
        )

    return app
