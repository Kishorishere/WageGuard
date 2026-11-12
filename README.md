# WageGuard

An auditable screening system for a bounded set of US wage-and-hour
checks. For a synthetic employee record, WageGuard returns exactly one
of four outcomes, cites the official passages it relied on, names every
missing input when it abstains, and writes a tamper-evident record that
can be replayed later.

**This project is a research and engineering prototype. It is not legal
advice, not a payroll engine, and not affiliated with or endorsed by any
employer, agency, or vendor.** Rules in this repository are
**not reviewed by counsel** (every rule row carries
`review_status: not_reviewed_by_counsel`).

---

## Status

| Component | State |
|-----------|-------|
| Phase 0 — foundations, CI, guardrails | ✅ Implemented |
| Phase 1 — domain core (Money, EffectiveRange, IDs, outcomes, errors) | ✅ Implemented |
| Phase 2 — intake + required-facts graph | ✅ Implemented |
| Phase 3 — rules-as-data + minimum-wage engine | ✅ Implemented (synthetic ruleset; real rules pending `VERIFY`) |
| Phase 4 — evidence corpus + ingestion | ✅ Implemented in-memory; synthetic HTML fixture |
| Phase 5 — retrieval | ✅ In-memory; SQL/pgvector adapter deferred |
| Phase 6 — explainer + verifier | ✅ Implemented (FakeClient; GeminiClient wired but not CI-tested) |
| Phase 7 — ledger + replay | ✅ Implemented in-memory; SQL adapter deferred |
| Phase 8 — evaluation core (scoring, metrics, Wilson, cases) | ✅ Core complete; 3 synthetic cases; baseline + Evalforge deferred |
| Phase 9 — exemption screen | ✅ Implemented (refusal to certify; property-tested) |
| Phase 10 — failure injection | ✅ 16-row matrix implemented |
| Phase 11 — interfaces, composition root, API-key auth | ✅ Implemented (CLI + FastAPI + GeminiClient) |
| Phase 12 — docs, ADRs, README | ✅ This document; 22 ADRs |

### Partially implemented

- **Real-corpus ingestion** — `evidence/` runs against a synthetic HTML
  fixture; real DOL and state-agency snapshots are pending user-fetched
  URLs (CLAUDE.md rule 1: Claude Code never supplies legal facts).
- **End-to-end LLM loop in `CheckService`** — the service runs
  intake → scope → facts → engine → ledger for every category; the
  explainer/verifier loop on decisive outcomes exists as separate
  modules but is wired through `FakeClient`, not yet threaded into
  `CheckService.run_check` for a single decisive path.

### Not yet implemented (and tracked)

- SQL adapters for ledger and evidence store (Alembic migration +
  pgvector).
- External head anchoring (`wageguard ledger anchor`).
- Fresh-mode replay.
- `CassetteClient` + the full cassette-driven golden workflow.
- `baseline.py` + the deliberate-regression Evalforge demo.
- The full 40-case golden set.
- Structured JSON logging + metrics; OpenAPI drift check.
- `make reproduce` end-to-end (G-26 stays Planned until the real
  corpus lands).

---

## Scope

- Checks: `minimum_wage`, `exemption_salary_level`.
- Jurisdictions (recommended, pending user `VERIFY`): US federal +
  Washington (state-above-federal) + Alabama (no state minimum).
- Dates: single `work_date` per request.
- Pay basis: hourly for minimum wage; salaried for exemption.
- Worker categories: `general` only; other categories route to
  `NEEDS_LEGAL_REVIEW`.

## Not in scope

Multi-agent orchestration; a web dashboard; tax calculation; worker
classification; work authorization; payments compliance; more than
three jurisdictions; tipped and youth wage rules; overtime
calculation; local (city/county) ordinances; multi-state work in a
pay period; pay periods straddling a rule-change date. Each has its
own reason code and is routed to `NEEDS_LEGAL_REVIEW`.

## Limitations — stated before features

- **Citation integrity is not semantic support.** The verifier proves
  a cited passage was retrieved and that any quote matches it. It
  does not prove the passage legally justifies the claim.
- **Temperature 0 and a pinned model ID do not guarantee
  determinism** on a hosted provider. The ledger records everything
  needed to investigate drift; replay can return `CANNOT_REPLAY`
  (ADR-0015).
- **A hash chain makes tampering evident, not impossible.**
  Mitigation is external anchoring of the head hash (ADR-0012).
- **Small golden sets mean wide confidence intervals.** Metrics are
  reported with numerators, denominators, and Wilson 95% intervals
  (ADR-0018); `non_abstained == 0` is reported as *undefined*, not
  zero.
- **Rules are not reviewed by counsel.** Every rule row carries
  `review_status: not_reviewed_by_counsel` by default.
- **No real wage figures in this build.** The default composition
  root uses a synthetic placeholder rate (derived from integer cents
  so no wage-shaped literal appears in `src/` — G-06). Real rules
  land only after the user fetches and reviews the DOL / state
  passages.

## Questions for legal

See [`docs/legal-questions.md`](docs/legal-questions.md). The system
refuses to make the following interpretations; each routes to
`NEEDS_LEGAL_REVIEW`:

- Local (city/county) minimum-wage ordinances.
- Multi-state work in a single pay period.
- Pay periods straddling a rule-change date.
- Tipped, youth, student, and other special categories.
- Employer-size- or industry-dependent state thresholds without the
  size fact supplied.
- Exemption classification based on duties alone (the exemption
  screen is salary-level + salary-basis only; duties are not
  automated — ADR-0020).
- Any exemption threshold whose legal status on the work date is
  uncertain or under litigation.

---

## Architecture

```text
CLI / API
   │
Intake ........ parse → validate → normalize            (reject malformed)
   │
Scope guard ... supported jurisdiction / date / worker  (else NEEDS_LEGAL_REVIEW)
   │
Required facts  PRESENT / MISSING / INVALID / AMBIGUOUS (else CANNOT_DETERMINE)
   │
Jurisdiction   applicable rules for (location, work_date)
   │
Rule engine ... pure, Decimal, effective-dated → Outcome
   │
Retriever ..... hard filter (jurisdiction, topic, date) THEN pgvector rank
   │
Explainer ..... LLM, structured output, cite only supplied passage ids
   │
Verifier ...... schema, citation integrity, quote match, numeric agreement
   │
Ledger ........ append-only, hash-chained
   │
Result + decision_id
```

Key invariants:

1. **The engine decides the outcome before the LLM is called**
   (ADR-0001). The LLM may only write prose.
2. **The verifier can veto but never upgrade** (G-11). Verification
   failure is a Fault, not a fallback decision.
3. **Abstentions skip the LLM** via templated prose (G-12, ADR-0014).
4. **The ledger write is the commit point** (spec §13.5). No
   `decision_id` is returned until a durable record exists (G-14).

See [`docs/architecture.md`](docs/architecture.md) for a longer prose
treatment.

## Quickstart

```bash
# From a clean clone:
make setup              # uv sync --frozen --extra dev  (creates .venv/)
make hooks              # pre-commit install
docker compose up -d    # local Postgres + pgvector  (not needed for unit tests)

# Day-to-day:
make lint               # ruff check + format check
make types              # mypy --strict
make test               # unit + property + architecture, with coverage
make docs-check         # guarantees ↔ tests, JSON schema, source register

# A worked example (all four categories):
cat > /tmp/pass.json <<EOF
{"check":"minimum_wage","work_state":"US","work_date":"2024-07-01",
 "pay_rate":"7.25","pay_basis":"hourly","worker_category":"general"}
EOF
uv run wageguard check /tmp/pass.json --json
# → DECISION  (synthetic rate; replace rule file for real evaluation)

cat > /tmp/miss.json <<EOF
{"check":"minimum_wage","work_state":"US"}
EOF
uv run wageguard check /tmp/miss.json --json
# → ABSTENTION  (CannotDetermine, names every missing field)

cat > /tmp/bad.json <<EOF
{"check":"minimum_wage","paY_rate":"15.00"}
EOF
uv run wageguard check /tmp/bad.json --json
# → REJECTION  (unknown field; exit 2)
```

Docker **images** build in GitHub Actions
(`.github/workflows/docker.yaml`); never with `docker compose build`.

## Data contract

Request fields (strict; unknown fields rejected — G-04):

| Field | Type | Required for |
|-------|------|--------------|
| `check` | `"minimum_wage"` \| `"exemption_salary"` | all |
| `work_state` | 2-letter state or `"US"` | all |
| `work_date` | ISO 8601 date | all |
| `pay_rate` | decimal **string** (not float; G-01) | minimum_wage |
| `pay_basis` | `"hourly"` \| `"salary"` | all |
| `worker_category` | `"general"` (others → legal review) | all |
| `salary_amount`, `pay_period`, `current_exempt_status` | — | exemption |

The full JSON schema is committed under
[`docs/schemas/check_request.json`](docs/schemas/check_request.json)
and CI-checked for drift.

Response shape (same for CLI `--json` and API):

```json
{
  "category":   "decision | abstention | rejection | fault",
  "decision_id": "d-000001 or null (fault without ledger)",
  "detail":      "human-readable explanation",
  "fault_stage": "null unless category == fault"
}
```

HTTP mapping (G-24): `201` decision/abstention; `422` rejection;
`503` fault (body names `fault_stage`); `404` unknown decision_id;
`401` missing/bad API key.

CLI exit codes: `0` decision/abstention, `2` rejection, `3` fault,
`4` verification, `5` ledger integrity, `1` unexpected.

## Audit record (example shape)

The in-memory ledger stores records whose canonical hash is:

```
record_hash = SHA-256( prev_hash || canonical_json({header, body, prev_hash}) )
```

Each record carries:

- **Identity**: `decision_id`, `sequence_no`, `created_at` (UTC),
  `app_version`, `git_commit`, `record_kind`, `canon_version`.
- **Check**: `check_type`, `ruleset_version`, `ruleset_hash`.
- **Body**: check-specific payload (verdict, controlling rule id,
  controlling rate, actual rate, shortfall, reason codes).
- **Chain**: `prev_hash`, `record_hash`.

Walk and verify with `uv run wageguard ledger verify`; the command
reports the first break by sequence index and reason (G-15).
Replay with `uv run wageguard ledger show <id>` (SQL-backed
`replay_exact` on engine-only records is byte-identical, G-17).

## Evaluation

Metrics code is complete (`evaluation.intervals`, `.scoring`,
`.metrics`, `.cases`). The committed synthetic golden set has:

- `data/golden/dev/` — 2 cases (threshold-below-cent, missing-pay-rate)
- `data/golden/heldout/` — 1 case (no-state-rule path)

The full 40-case corpus and the end-to-end `make golden` harness
land with the real-corpus flow. Metric semantics are pinned:

- **Headline**: `confidently_wrong_rate = CW / (CW + CORRECT_DECISIVE)`.
- **Undefined when `non_abstained == 0`**, not zero (G-19, ADR-0017).
- **Wilson 95% intervals** accompany every rate (ADR-0018). The
  implementation is pure and reference-tested against `statsmodels`.
- **Held-out split integrity** is a load-time check (G-20).
- **Baseline**: plain LLM+RAG on the same model and corpus
  (ADR-0019); lands with cassettes.

## Primary source register

Generated by `scripts/generate_source_register.py` from
`data/sources/manifest.yaml`. Phase 12 ships the generator;
[`docs/source-register.md`](docs/source-register.md) remains
scaffolding until the real-corpus manifest arrives.

## Guarantees table

| ID | Guarantee | Status |
|----|-----------|--------|
| G-01 | Money rejects float at construction | Active |
| G-02 | EffectiveRange is half-open; adjacent ranges never overlap | Active |
| G-03 | Decision / Abstention / Rejection / Fault are disjoint | Active |
| G-04 | Intake rejects unknown fields; distinguishes MISSING / INVALID | Active |
| G-05 | CannotDetermine names every offending field at once | Active |
| G-06 | No legal value hard-coded in `src/` | Active |
| G-07 | Highest applicable rate controls | Engine Active; sourcing pending |
| G-08 | Chunker deterministic: identical bytes → identical passage IDs | Active |
| G-09 | Hard metadata filters applied BEFORE vector ranking | Active |
| G-10 | Required citations come from the engine, not retrieval | Active |
| G-11 | Verifier can veto but never upgrade | Active |
| G-12 | Abstentions skip the LLM (templated) | Active |
| G-13 | Prompt hash verified at startup | Active |
| G-14 | Every completed check appended to hash-chained ledger | Active |
| G-15 | `ledger verify` detects every tamper class | Active |
| G-16 | Concurrent appends never fork the chain | Active |
| G-17 | Exact replay of engine-only outcomes is byte-identical | Active |
| G-18 | Replay writes a new record; original never mutated | Active |
| G-19 | Metrics reported with Wilson 95% intervals; undefined when n=0 | Active |
| G-20 | Held-out split is structurally separate; runs logged | Active |
| G-21 | Exemption `PASS` unreachable without documented conditions | Active |
| G-22 | Every fault-matrix row produces a Fault; no decision | Active |
| G-23 | CLI and API share one service; identical results | Active |
| G-24 | API returns 2xx only when a ledger record exists | Active |
| G-25 | `/readyz` fails on ruleset or prompt hash mismatch | Active |
| G-26 | `make reproduce` runs end-to-end from a clean clone | Planned (needs real corpus) |

24 guarantees Active; `docs/guarantees.md` is the authoritative table
and is CI-checked against every test marker.

## Reproducibility

- **Dependencies** pinned via `uv.lock` (ADR-0003); `uv sync
  --frozen --extra dev` is byte-reproducible.
- **Deterministic**: chunker, embedder-fake, canonical
  serialization, ledger hash, Wilson interval, engine.
- **Non-deterministic on hosted LLM**: handled honestly via
  cassettes (ADR-0016) and `MATCH_WITH_TEXT_VARIATION` replay
  semantics (ADR-0015).
- **Docker** images build in GitHub Actions; local workflow uses
  only `uv run`.
- **`make reproduce`** target exists; the full round-trip lands when
  the SQL adapter and real-corpus ingestion ship.

## Security and privacy

- Synthetic data only. Secrets via env; `.env` is gitignored.
- No PII in logs; `hash_only` privacy mode stores an input hash and
  fact statuses only.
- API-key auth on every non-health endpoint (constant-time compare).
- No vendor-SDK import for the LLM — `GeminiClient` is a thin httpx
  adapter (architecture-test enforced).
- Dependency and secret scanning in CI (`pip-audit`, `gitleaks`).
- Full threat model: [`docs/threat-model.md`](docs/threat-model.md).

## Design decisions (ADRs)

All 22 ADRs live in `docs/adr/`. Quick index:

- **0001** Deterministic rules decide; the LLM explains.
- **0002** Pydantic at boundaries, frozen dataclasses inside.
- **0003** Hermetic builds with uv.
- **0004** Four disjoint result categories.
- **0005** Decimal quantization policy.
- **0006** Half-open effective ranges.
- **0007** Highest applicable rate controls.
- **0008** Required evidence comes from the engine.
- **0009** Hard filters before vector ranking.
- **0010** pgvector and index choice.
- **0011** Content-addressed immutable source versions.
- **0012** Hash chain and its limits.
- **0013** Canonicalization and versioning.
- **0014** Templated abstentions skip the LLM.
- **0015** Replay semantics and MATCH.
- **0016** Cassette-based CI evaluation.
- **0017** Confidently-wrong is the headline metric.
- **0018** Wilson intervals and held-out discipline.
- **0019** Baseline design.
- **0020** Exemption: refusal to certify.
- **0021** No silent fallbacks.
- **0022** Evalforge boundary.

## Development

Standards summary (full detail in `compliance-project.md` §2):

- Python 3.12, `uv` frozen lockfile, Docker images from GH Actions.
- `ruff` (broad rule set) + `mypy --strict`; pre-commit mirrors CI.
- Pure domain core (stdlib only). Pydantic only at trust boundaries.
- `Decimal` everywhere money touches; float banned under
  `compliance/` and `ledger/` by an architecture test.
- UTC-aware datetimes; naive datetimes banned under `src/` by an
  architecture test.
- Append-only ledger; canonical serialization; hash chain.

How to contribute (short form; see
[CONTRIBUTING.md](CONTRIBUTING.md)):

- One logical change per PR.
- Tests-first in Phases 1, 2, 3, 6, 7 (red commit before green).
- ADR first for non-obvious decisions.
- Every README claim maps to a `@pytest.mark.guarantee("G-NN")`
  test; `make docs-check` enforces it.

## Numbers

**As of this commit:**

- 545 tests pass (unit, property, metamorphic, architecture,
  adversarial, resilience).
- 24 guarantees Active; 2 Planned.
- 22 ADRs.
- 70 source files; `mypy --strict` clean.
- 95%+ branch coverage overall; 100% on the core (`compliance/`,
  `ledger/canonical`, `ledger/chain`).

The committed golden-report numbers (confidently-wrong rate, etc.)
land when the end-to-end `make golden` runs over the full 40-case
corpus — pending real-corpus sources.
