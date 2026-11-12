.PHONY: help setup lint format types test test-unit test-property test-integration \
        golden golden-live ingest migrate reproduce ledger-verify docs-check \
        audit hooks clean

UV ?= uv

help:
	@echo "WageGuard — development targets"
	@echo "  setup            Create .venv and install locked deps (uv sync --frozen)"
	@echo "  lint             Run ruff (lint + format check)"
	@echo "  format           Run ruff --fix and ruff format"
	@echo "  types            Run mypy --strict"
	@echo "  test             Run the unit + property + architecture tiers with coverage"
	@echo "  test-unit        Unit tests only"
	@echo "  test-property    Hypothesis property tests only"
	@echo "  test-integration Integration tests (requires local Postgres+pgvector)"
	@echo "  golden           Golden suite against recorded cassettes"
	@echo "  golden-live      Golden suite against live models (manual, requires API keys)"
	@echo "  ingest           Ingest the committed corpus snapshot (no network)"
	@echo "  migrate          Run Alembic migrations"
	@echo "  reproduce        setup -> migrate -> ingest -> golden from a clean checkout"
	@echo "  ledger-verify    Walk and verify the ledger hash chain"
	@echo "  docs-check       Verify guarantees.md <-> test marker invariants"
	@echo "  audit            pip-audit against the lockfile"
	@echo "  hooks            Install pre-commit hooks locally"

setup:
	$(UV) sync --frozen --extra dev

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

types:
	$(UV) run mypy

test:
	$(UV) run pytest -m "not integration and not golden and not failure_injection" \
	    --cov --cov-report=term-missing

test-unit:
	$(UV) run pytest tests/unit

test-property:
	$(UV) run pytest -m property

test-integration:
	$(UV) run pytest -m integration

golden:
	$(UV) run pytest -m golden

golden-live:
	@echo "Live golden suite — requires GEMINI_API_KEY or GROQ_API_KEY in env."
	$(UV) run pytest -m golden --golden-live

ingest:
	$(UV) run wageguard ingest

migrate:
	$(UV) run alembic upgrade head

reproduce: setup migrate ingest golden

ledger-verify:
	$(UV) run wageguard ledger verify

docs-check:
	$(UV) run python scripts/check_guarantees.py
	$(UV) run python scripts/check_schemas.py
	$(UV) run python scripts/generate_source_register.py

audit:
	$(UV) run pip-audit --strict

hooks:
	$(UV) run pre-commit install

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .hypothesis .coverage coverage.xml htmlcov dist build
