# ADR-0003: Hermetic builds with uv

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Reproducibility is one of the system's load-bearing claims (spec
§S-7). A dependency that silently updates between runs breaks
replay in subtle ways: the LLM client library changes its retry
semantics, the YAML loader changes its number parsing, a transitive
dep's DateTime module changes its rounding behaviour. Any of those
makes "the same input, the same version" produce a different
ledger record.

## Decision

**`uv` with a committed `uv.lock` is the dependency source of
truth.** Specifically:

- `pyproject.toml` declares top-level pins (exact versions, no
  caret or tilde specifiers for runtime deps).
- `uv.lock` captures every transitive dep, hashes included, and is
  committed to the repo.
- `make setup` runs `uv sync --frozen --extra dev`; CI runs the same.
  Any run that would require changing the lock without the commit
  fails.
- A pre-commit hook asserts `uv lock --check` is clean (the lockfile
  is current with `pyproject.toml`).

Docker image builds run in GitHub Actions
(`.github/workflows/docker.yaml`), **not** via local
`docker compose build` (user directive, documented in CLAUDE.md
and this ADR).

## Alternatives considered

- **pip + requirements.txt + pip-compile.** Works; slower than `uv`
  and less ergonomic for dev. Rejected.
- **Poetry.** Works; bigger surface, slower lock resolution,
  historically some reproducibility bugs around resolving extras
  differently. Rejected.
- **No lockfile, latest-floating deps.** Rejected on principle for
  a system whose output must replay.

## Consequences

- `uv sync --frozen` produces a `.venv/` identical byte-for-byte
  across machines with the same Python version.
- `make reproduce` genuinely re-runs: clean clone -> `uv sync
  --frozen` -> `uv run wageguard ...` -> same output.
- A dependency bump is a reviewed PR that changes both
  `pyproject.toml` and `uv.lock`; the PR shows exactly which
  transitive dep moved.
