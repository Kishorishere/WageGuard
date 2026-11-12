# Contributing

This is a portfolio prototype. External contributions are not accepted,
but the workflow below applies to anyone — human or AI — editing the repo.

## Development setup

Prerequisites: `uv >= 0.4.20`, Docker (for the local database only),
Git, and a POSIX shell (Git Bash works on Windows).

```bash
make setup            # creates .venv, installs frozen deps
make hooks            # installs pre-commit hooks
docker compose up -d  # starts local Postgres+pgvector
```

Never `docker compose build`. The application image is built in GitHub
Actions (`.github/workflows/docker.yaml`).

## Day-to-day

```bash
make lint             # ruff check + format check
make format           # ruff --fix and ruff format
make types            # mypy --strict
make test             # unit + property + architecture, with coverage
make test-integration # requires `compose up -d`
make golden           # recorded cassettes, no network
make docs-check       # guarantee registry sanity
```

Pre-commit runs the same linters on every commit. Do not disable hooks.
If a hook fails, fix the underlying issue; do not pass `--no-verify`.

## Branches, commits, PRs

- One logical change per PR.
- Commit style: one imperative headline (60 chars or less), then up
  to five short bullets naming what the commit adds.
- No conventional-commit prefix, no phase / spec references, no AI
  co-author trailers.
- Red commit lands before the green one when writing tests first.
- ADR first for non-obvious choices (`docs/adr/NNNN-title.md`).

## Guarantees

Every README claim lives in `docs/guarantees.md` first. Moving a
guarantee from **Planned** to **Active** requires:

1. a passing test marked `@pytest.mark.guarantee("G-NN")`;
2. the row added to the Active table in the same PR;
3. `make docs-check` passing locally and in CI.

## What goes in an ADR

Context (what prompted the decision), Decision (chosen approach),
Alternatives considered (with a one-line reason each was rejected), and
Consequences (what this closes off, what it costs, what it still leaves
open). Keep it terse — half a page, not three pages.

## Reporting issues

Use GitHub issues. Never include real worker data in a reproduction.
All inputs in this project are synthetic.
