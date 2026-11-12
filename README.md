# WageGuard

An auditable screening system for a bounded set of US wage-and-hour
checks. For a synthetic employee record it returns exactly one of four
outcomes, cites the official passages it relied on, names every missing
input when it abstains, and writes a tamper-evident record that can be
replayed later.

**This project is a research and engineering prototype. It is not legal
advice, not a payroll engine, and not affiliated with or endorsed by any
employer, agency, or vendor.** Rules in this repository are
**not reviewed by counsel**.

---

## Status

| Component | State |
|-----------|-------|
| Phase 0 — foundations, CI, guardrails | **In progress** |
| Phase 1 — domain core | Planned |
| Phase 2 — intake / required-facts graph | Planned |
| Phase 3 — rules-as-data and min-wage engine | Planned |
| Phase 4 — evidence corpus and ingestion | Planned |
| Phase 5 — retrieval | Planned |
| Phase 6 — explainer + verifier | Planned |
| Phase 7 — ledger + replay | Planned |
| Phase 8 — evaluation / Evalforge / baseline | Planned |
| Phase 9 — exemption screen (Tier 3) | Planned |
| Phase 10 — failure injection | Planned |
| Phase 11 — CLI + API + security + observability | Planned |
| Phase 12 — docs + ADRs + README numbers | Planned |

The README is updated honestly per phase. No planned feature is described
as implemented. See `docs/guarantees.md` for the full planned-vs-active
guarantees table.

## Scope

- Checks: `minimum_wage`, `exemption_salary_level`.
- Jurisdictions: US federal + two states (chosen in Phase 3; `VERIFY`
  rate and effective-date sources against state labor departments).
- Dates: single `work_date` per request.
- Pay basis: hourly only (salaried records route to the exemption screen
  or legal review).
- Worker categories: general only (tipped, youth, student, and others
  route to legal review).

## Not in scope

Multi-agent orchestration, a web dashboard, tax calculation, worker
classification, work authorization, payments compliance, more than three
jurisdictions, tipped and youth wage rules, overtime calculation, local
(city/county) ordinances, multi-state work in a pay period, pay periods
straddling a rule-change date. Each has its own reason code and is
routed to `NEEDS_LEGAL_REVIEW`.

## Limitations (stated before features)

- **Citation integrity is not semantic support.** The verifier proves a
  cited passage was retrieved and that any quote matches it. It does
  not prove the passage legally justifies the claim.
- **Temperature 0 and a pinned model ID do not guarantee determinism**
  on a hosted provider. The ledger records everything needed to
  investigate drift; replay can return `CANNOT_REPLAY`.
- **A hash chain makes tampering evident, not impossible.** Mitigation
  is external anchoring of the head hash.
- **Small golden sets mean wide confidence intervals.** Reported with
  numerators, denominators, and Wilson intervals.
- **No legal review of rules.** Every rule row carries
  `review_status: not_reviewed_by_counsel` by default.

## Development

Quickstart:

```bash
make setup            # create .venv and install frozen deps
make hooks            # pre-commit hooks
docker compose up -d  # local Postgres+pgvector only
make lint && make types && make test
```

Docker **images** are built in GitHub Actions
(`.github/workflows/docker.yaml`), never with `docker compose build`.
For the full project standards see [`CLAUDE.md`](CLAUDE.md) and
[`CONTRIBUTING.md`](CONTRIBUTING.md). The authoritative build
specification is [`compliance-project.md`](compliance-project.md).

## LLM provider

The `LlmClient` port is provider-agnostic. Development adapters are
**Gemini** and **Groq**; no code in this repository imports
`anthropic` or `openai` (enforced by an architecture test).

## Reproducibility

`make reproduce` performs a clean checkout rebuild: `uv sync --frozen`,
migrate, ingest from committed corpus snapshots, run the golden suite on
recorded cassettes with no network. Phase 0 wires the target; the full
flow becomes operational once Phases 4 and 8 ship.
