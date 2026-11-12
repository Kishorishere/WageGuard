# WageGuard: Master Engineering Specification

**Status:** Authoritative build specification.
**Audience:** The implementing engineer, Claude Code as pair programmer, and any future reviewer.
**Scope:** Tier 1 (ship), Tier 2 (depth), Tier 3 (exemption screen and failure injection), built as one coherent system.

---

## Table of Contents

0. How to use this document
1. Mission, non-goals, honesty constraints
2. The Standards (global, referenced by every phase)
3. Domain model and glossary
4. System architecture
5. Repository layout and tooling
6. Phase 0: Foundations
7. Phase 1: Domain core
8. Phase 2: Intake and the required-facts graph
9. Phase 3: Rules as data and the minimum-wage engine
10. Phase 4: Evidence corpus and ingestion
11. Phase 5: Retrieval
12. Phase 6: Explainer and verifier
13. Phase 7: Ledger and replay
14. Phase 8: Evaluation, golden set, baseline, Evalforge
15. Phase 9: Exemption screen (Tier 3)
16. Phase 10: Failure injection and resilience
17. Phase 11: Interfaces, security, observability
18. Phase 12: Documentation, ADRs, README, CV
19. Appendices

---

## 0. How to use this document

### 0.1 Working agreement with Claude Code

Claude Code is a fast pair programmer with no judgment about what you can defend in an interview. The agreement:

1. **One phase at a time.** Do not start Phase N+1 until Phase N's acceptance criteria pass in CI.
2. **Tests before implementation** in Phases 1, 2, 3, 6, 7. Write the failing test, commit it, then implement.
3. **Claude Code never supplies a legal fact.** Wage figures, salary thresholds, effective dates, statutory citations and passage text come from official sources you fetched and reviewed. If it needs a number it does not have, it stops and asks. This is enforced in `CLAUDE.md` (Appendix F).
4. **Every diff is reviewed as if a colleague wrote it.** If you cannot explain a line, delete it or learn it.
5. **Every README claim maps to a test.** A guarantee without a test is a wish.
6. **ADR first for non-obvious decisions**, written in your own words.

### 0.2 Conventions

- MUST / MUST NOT / SHOULD follow RFC 2119.
- **VERIFY** marks a fact that must be confirmed against a primary source before use. Nothing marked VERIFY may be hard-coded from this document.
- Each phase opens with a **Standards Reminder**. It is the checklist applied to every pull request in that phase.
- Each phase ends with **Acceptance criteria** that are binary and testable.

### 0.3 The meta-goal

The target role repeats one theme: **defensibility under uncertainty**. Every design choice serves the question a skeptical reviewer will ask: *"Show me why this answer is right, what it was based on, and what happens when it is not."*

---

## 1. Mission, non-goals, honesty constraints

### 1.1 Mission

WageGuard is an auditable screening system for a bounded set of US wage-and-hour checks. For a synthetic employee record it returns exactly one of four outcomes, cites the official passages it relied on, names every missing input when it abstains, and writes a tamper-evident record that can be replayed later.

### 1.2 What it is not

- Not legal advice, a payroll engine, or a compliance guarantee.
- Not affiliated with or endorsed by any employer or vendor. Do not use any third party's product names.
- Does not interpret ambiguous law. Ambiguity becomes `NEEDS_LEGAL_REVIEW`.
- Does not process real employee data. All data is synthetic.

### 1.3 Non-goals (deliberate cuts)

Multi-agent orchestration, a web dashboard, tax calculation, worker classification (employee versus contractor), work authorization, payments compliance, more than three jurisdictions, tipped and youth wage rules, overtime calculation. Each is a real problem. Excluding them is a design decision, and the README lists them as unsupported.

### 1.4 Honesty constraints (stated in the README)

- **Citation integrity is not semantic support.** The system proves a cited passage was retrieved and a quote matches it. It does not prove the passage legally justifies the claim. Humans and golden tests address that.
- **Temperature 0 and a pinned model ID do not guarantee determinism** on a hosted provider. The system records everything needed to investigate drift, and replay can return `CANNOT_REPLAY`.
- **A hash chain makes tampering evident, not impossible.** Anchoring the head hash externally is the mitigation.
- **Small golden sets give wide confidence intervals.** The system reports them.
- **Rule review status is explicit.** Every rule carries `review_status`, defaulting to `not_reviewed_by_counsel`.

---

## 2. The Standards (global)

Phase reminders cite these as S-n. Violations are review failures.

### S-1. Language and toolchain

- Python 3.12. Dependencies managed with `uv`, lockfile committed. No unpinned installs in Docker or CI. Base images pinned by digest.
- `ruff` for lint and format, with a broad rule selection: `E, F, I, B, UP, SIM, C4, PL, RUF, S, PT, ANN, TCH, N, A, DTZ, T20, ERA`. Every ignore is justified inline.
- `mypy --strict` on `src/` and `tests/`. No `Any` leaking from domain code. `# type: ignore[code]  # reason` is the only permitted form.
- `pytest`, `hypothesis`, `testcontainers` (real Postgres with pgvector), `pytest-cov` with floors: 95% branch on `compliance/`, `ledger/`, `citations/`; 85% elsewhere.
- Pre-commit hooks mirror CI so failures surface locally.

### S-2. Types and data modeling

- Domain objects are `@dataclass(frozen=True, slots=True)`, `Enum`, or `NewType`. Pydantic v2 is used only at trust boundaries: CLI/API input, LLM output, file loading. Internal code passes validated domain types.
- **Money is `Decimal`.** Floats are banned in domain code. An architecture test fails the build if `float` appears in annotations under `compliance/` or `ledger/`. Money construction rejects `float` explicitly.
- **Legal effective dates are `datetime.date`.** System timestamps are timezone-aware UTC `datetime`. Naive datetimes are banned (`DTZ` rules).
- **Outcomes are a closed sum type.** Handle with exhaustive `match` plus `assert_never`. Adding a variant must produce type errors everywhere it is unhandled.
- **Identifiers are typed.** `DecisionId`, `RuleId`, `PassageId`, `SourceVersionId` are `NewType`s or small frozen classes. No bare strings cross module boundaries.

### S-3. Control flow and errors

- Four disjoint result categories never share a type: **Decision** (`PASS`/`FLAG`), **Abstention** (`CANNOT_DETERMINE`/`NEEDS_LEGAL_REVIEW`), **Rejection** (malformed input), **Fault** (infrastructure failure). A fault must never be representable as an abstention.
- A small typed exception hierarchy rooted at `WageGuardError`. No bare `except`. No `except Exception` outside a single documented top-level boundary that converts to a `Fault` record and re-raises.
- Never swallow an exception. Never return `None` to signal failure in domain code.

### S-4. Architecture

- Pure functions in the domain core. I/O only at the edges (repositories, LLM client, HTTP, filesystem).
- Dependencies are injected through constructors or function parameters. No module-level singletons, no global mutable state, no import-time side effects.
- Ports and adapters: domain code depends on `Protocol` interfaces, and adapters implement them. The LLM client, embedder, clock, and ID generator are all ports so tests substitute them.
- Rules, prompts, and schemas live outside handlers and are versioned.

### S-5. Naming and code style

- Names come from the domain (`EffectiveDatedRule`, `RequiredFact`, `EvidenceBundle`). No `utils.py`, `helpers.py`, `manager`, `handler`, `common`.
- Modules stay small with one responsibility. Soft ceiling of 250 lines per module and 40 per function. Exceeding it needs a reason.
- Comments explain why, never what. Docstrings appear on public interfaces and non-obvious invariants only, written in prose rather than template boilerplate.
- One pattern per problem. If two modules solve the same problem differently, fix it.

### S-6. Testing

- Test behavior, not implementation. Do not assert that a mock was called. Assert on observable outputs and persisted state.
- Test pyramid: unit (pure core), property (Hypothesis), integration (real Postgres), golden (end-to-end with recorded responses), failure injection.
- Tests are deterministic. Time, randomness, IDs, and network are injected. No sleeping.
- Every bug fix lands with a regression test that fails before the fix.
- Every README guarantee carries a test marker, `@pytest.mark.guarantee("G-07")`, and CI fails if a documented guarantee has no test.

### S-7. Reproducibility

- Builds are hermetic: lockfile, pinned images, pinned embedding and LLM model IDs.
- Every stochastic or external dependency is recorded in the ledger (model, settings, prompt hash, passage hashes, rule versions).
- Golden evaluation runs in CI against **recorded cassettes** so it is deterministic and free. A separate manually triggered job runs live models.
- `make reproduce` rebuilds the environment, migrates, ingests the pinned corpus snapshot, and runs the golden suite from a clean checkout.

### S-8. Git and process

- Small, atomic commits. Imperative subject lines under 72 characters, with a body that explains why. Conventional prefixes (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`) applied consistently.
- Tests-first commits appear before the implementation commits in Phases 1, 2, 3, 6, 7.
- ADRs live in `docs/adr/NNNN-title.md` using a fixed template (Context, Decision, Alternatives, Consequences).
- No commit contains secrets, real data, or generated noise. No "fix typo" commit chains. Squash locally first.

### S-9. Security and privacy

- Synthetic data only. Secrets come from environment variables, never committed. `.env.example` has no real values.
- No PII in logs. Input snapshots in the ledger are synthetic-only by design, and the privacy mode (Section 13.6) stores a hash only.
- Auth on any non-local API. The decision log is never publicly exposed.
- Dependency scanning (`pip-audit`) and secret scanning (`gitleaks`) run in CI.

### S-10. Observability

- Structured JSON logs. The correlation ID is the `decision_id`. Log levels are meaningful and consistent.
- Every external call logs latency, retry count, and outcome category. Never log prompts that contain input data beyond what the privacy mode permits.

### S-11. Documentation honesty

- No hype adjectives ("robust", "scalable", "production-ready", "seamless"). No emoji. State limits first.
- No planned feature is described as implemented. The README distinguishes **Implemented**, **Partially implemented**, and **Not implemented**.

---

## 3. Domain model and glossary

| Term | Meaning |
|---|---|
| **Check** | A named evaluation, e.g. `minimum_wage`, `exemption_salary_level`. |
| **Facts** | Normalized input values about a worker/pay record. |
| **Required fact** | A fact a given check declares it needs. |
| **Fact status** | `PRESENT`, `MISSING`, `INVALID`, `AMBIGUOUS`. |
| **Rule** | Effective-dated, source-linked data row stating a legal value (e.g. a minimum rate). |
| **Ruleset** | A versioned, immutable bundle of rules. |
| **Source** | An official document or page (agency, URL, jurisdiction, topic). |
| **Source version** | An immutable content-hashed snapshot of a source at a retrieval time. |
| **Passage** | A stable-ID chunk of a source version. |
| **Evidence bundle** | The passages retrieved for one decision. |
| **Decision** | Outcome `PASS` or `FLAG`. |
| **Abstention** | Outcome `CANNOT_DETERMINE` or `NEEDS_LEGAL_REVIEW`. |
| **Rejection** | Input failed schema validation. No decision record outcome, but an intake record may be logged. |
| **Fault** | Infrastructure failure. Never a decision or abstention. |
| **Ledger** | Append-only, hash-chained record of every completed check and fault. |
| **Replay** | Re-execution of a logged decision, in `exact` or `fresh` mode. |

### 3.1 Outcome semantics

- `PASS`: facts satisfy the encoded check under the applicable rule on the work date.
- `FLAG`: facts appear not to satisfy the encoded check.
- `CANNOT_DETERMINE`: a required fact is missing, invalid, or ambiguous, or evidence is unavailable. Always names fields.
- `NEEDS_LEGAL_REVIEW`: the scenario is outside the encoded scope or involves an interaction the ruleset does not safely resolve.

There is **no confidence score**. A model can be confident and wrong, so the system's safety mechanism is abstention, not probability.

### 3.2 Outcome precedence

When several conditions apply, the first match wins, in this order:

1. Rejection (malformed input)
2. Out-of-scope, then `NEEDS_LEGAL_REVIEW`
3. Required-fact failures, then `CANNOT_DETERMINE`
4. Jurisdiction ambiguity, then `CANNOT_DETERMINE` or `NEEDS_LEGAL_REVIEW` per reason code
5. Rule evaluation, then `PASS`/`FLAG`
6. Evidence or verification failure, then Fault (fail closed, never a decision)

This ordering is code, tested exhaustively, and documented in an ADR.

---

## 4. System architecture

```text
CLI / API
   |
Intake ........ parse -> validate -> normalize            (reject malformed)
   |
Scope guard ... supported jurisdiction/date/worker category?   (else NEEDS_LEGAL_REVIEW)
   |
Required-facts resolver ... PRESENT/MISSING/INVALID/AMBIGUOUS  (else CANNOT_DETERMINE)
   |
Jurisdiction resolver ... applicable rules for (location, work_date)
   |
Rule engine ... pure functions, Decimal money, effective-dated rules -> Outcome
   |
Evidence retriever ... hard filter (jurisdiction, topic, date) then pgvector rank
   |
Explainer (LLM) ... structured output, may cite only supplied passage IDs
   |
Verifier ... schema, citation integrity, quote match, outcome consistency
   |
Ledger ... append-only, hash-chained, content-addressed evidence
   |
Result + decision_id
```

### 4.1 Critical architectural properties

1. **The engine decides the outcome before the LLM is called.** The LLM receives the outcome as a fixed input and writes only an explanation. It cannot change the outcome.
2. **The verifier can veto but never upgrade.** If verification fails, the result is a Fault. The system never falls back to an unverified decision.
3. **Abstentions skip the LLM where possible.** Abstention explanations are templated from reason codes. This is cheaper, deterministic, and removes a hallucination surface. The LLM is used for decisive outcomes only, and optionally for the legal-review rationale text.
4. **The ledger write is the commit point.** A decision does not exist until its record is durably appended.

### 4.2 Data flow for one check

`CheckRequest` -> `ValidatedFacts` -> `ScopeVerdict` -> `FactResolution` -> `JurisdictionResolution` -> `EngineResult` -> `EvidenceBundle` -> `ExplanationDraft` -> `VerifiedExplanation` -> `LedgerRecord` -> `CheckResponse`.

Each arrow is a pure function or a single port call, and each intermediate type is a frozen dataclass.

---

## 5. Repository layout and tooling

```text
wageguard/
├── README.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── pyproject.toml
├── uv.lock
├── Makefile
├── Dockerfile
├── compose.yaml
├── .env.example
├── .pre-commit-config.yaml
├── .github/workflows/{ci.yaml,live-eval.yaml}
├── alembic.ini
├── migrations/
├── docs/
│   ├── SPEC.md
│   ├── adr/
│   ├── architecture.md
│   ├── legal-questions.md
│   ├── source-register.md
│   └── guarantees.md
├── data/
│   ├── sources/manifest.yaml
│   ├── snapshots/            # content-addressed fetched sources
│   ├── rules/                # effective-dated rule files
│   └── golden/{dev,heldout}/
├── prompts/
│   ├── explain_decision/v1.txt
│   └── registry.yaml
├── src/wageguard/
│   ├── domain/               # types, money, ids, outcomes (no I/O)
│   ├── intake/
│   ├── compliance/
│   │   ├── scope.py
│   │   ├── facts.py
│   │   ├── jurisdiction.py
│   │   ├── rules.py
│   │   └── checks/{minimum_wage.py,exemption_salary.py}
│   ├── evidence/{ingest.py,chunking.py,store.py,retrieval.py,embedder.py}
│   ├── llm/{port.py,anthropic_client.py,cassette.py,prompts.py,schemas.py}
│   ├── verification/{citations.py,consistency.py,verifier.py}
│   ├── ledger/{canonical.py,chain.py,repository.py,verify.py}
│   ├── replay/{exact.py,fresh.py,diff.py}
│   ├── evaluation/{cases.py,metrics.py,intervals.py,evalforge_adapter.py,baseline.py}
│   ├── interfaces/{cli.py,api.py}
│   ├── observability/{logging.py,timing.py}
│   └── config.py
└── tests/{unit,property,integration,golden,failure,architecture}/
```

### 5.1 Dependency direction

`domain` <- `compliance`, `verification`, `ledger.canonical` <- services <- `interfaces`. The `domain` and `compliance` packages MUST NOT import from `llm`, `evidence`, `interfaces`, SQLAlchemy, or any HTTP library. An architecture test (`import-linter` or a custom AST check) enforces this in CI.

### 5.2 Makefile targets

`make setup`, `make lint`, `make types`, `make test`, `make test-property`, `make test-integration`, `make golden`, `make golden-live`, `make ingest`, `make migrate`, `make reproduce`, `make ledger-verify`, `make docs-check`.

---

## 6. Phase 0: Foundations

> **Standards Reminder:** S-1 (toolchain), S-7 (reproducibility), S-8 (git), S-9 (secrets). Establish the guardrails before any domain code exists so nothing is retrofitted.

### 6.1 Objective

A repository where a clean checkout reaches a green CI run with zero domain logic, with the guardrails that keep later phases honest already running.

### 6.2 Deliverables

1. `pyproject.toml` with project metadata, ruff and mypy config, pytest config, coverage floors.
2. `uv.lock` committed. `make setup` runs `uv sync --frozen`.
3. `compose.yaml` with a pinned Postgres+pgvector image (by digest), healthcheck, and a named volume.
4. Pre-commit hooks: ruff, ruff-format, mypy, gitleaks, a check that `uv.lock` is up to date, and a check for large files.
5. CI workflow: lint, types, unit, property, integration (service container), golden-on-cassette, `pip-audit`, `gitleaks`, docs-check.
6. `CLAUDE.md` (Appendix F), `CONTRIBUTING.md`, and an ADR template.
7. An **architecture test suite** with empty-but-wired tests that will bite later:
   - No `float` annotations under `compliance/` and `ledger/`.
   - No naive `datetime` usage.
   - Forbidden imports from the domain core.
   - No module-level mutable state.
   - Every file under `src/` has a matching test module or an explicit allowlist entry.
8. The **guarantee registry**: `docs/guarantees.md` lists guarantees G-01... with an owning test marker. A CI script fails if a guarantee has no test or a guarantee marker references a missing guarantee.

### 6.3 Design notes

- **Why guardrails first:** retrofitting strict typing and architecture rules onto written code produces churn and exceptions. Adding them to an empty repo makes them the path of least resistance.
- **Why a guarantee registry:** it converts "every claim has a test" from a promise into a build constraint.
- **Docker:** multi-stage build, non-root user, no dev dependencies in the runtime image, `HEALTHCHECK`, pinned base by digest.
- **Config:** one `Settings` object (pydantic-settings), constructed once in the composition root and passed down. No reads of `os.environ` outside `config.py`.

### 6.4 ADRs to write in this phase

- ADR-0001: Deterministic rules decide, the LLM explains.
- ADR-0002: Pydantic at boundaries, frozen dataclasses inside.
- ADR-0003: `uv` and hermetic builds.
- ADR-0004: Four disjoint result categories.

### 6.5 Acceptance criteria

- [ ] Clean clone, then `make setup && make lint && make types && make test` passes.
- [ ] CI is green on an empty domain.
- [ ] Introducing a `float` annotation in `compliance/` fails the architecture test.
- [ ] A guarantee with no test fails `make docs-check`.
- [ ] `docker compose up` brings up Postgres with the `vector` extension available.
- [ ] No secret-like strings are present (gitleaks clean).

---

## 7. Phase 1: Domain core

> **Standards Reminder:** S-2 (types), S-3 (errors), S-5 (naming), S-6 (tests-first). The domain package has no I/O and no third-party dependencies beyond the standard library. Tests are written before code.

### 7.1 Objective

Define the vocabulary of the system as immutable, validated types so every later phase builds on a closed, well-typed foundation.

### 7.2 Deliverables

**Money.** `Money` wraps a `Decimal` and a currency (`USD` only initially). Rules:
- Construct only from `Decimal` or `str`. `float` raises `TypeError`.
- Quantization policy is explicit and documented (ADR): store full precision, compare exactly, and round only at defined presentation points with a named rounding mode. Never round before comparison. A one-cent shortfall must be detectable.
- Arithmetic returns `Money`. Mixed currencies raise.
- A `HourlyRate` and `Salary` distinction can use distinct `NewType`s over `Money` to prevent unit confusion.

**Identifiers.** `DecisionId` (UUIDv7 or ULID for sortable IDs, generated through an injected `IdGenerator` port), `RuleId`, `RulesetVersion`, `PassageId` (format `source_key@vN#pNNN`, parsed and validated, not a free string), `SourceVersionId`, `PromptVersion`.

**Dates.** `EffectiveRange(start: date, end: date | None)` with half-open semantics `[start, end)`, documented once and tested at boundaries. `contains(date)`, `overlaps(other)`. An effective range with `end <= start` is invalid.

**Outcome sum type.**

```python
@dataclass(frozen=True, slots=True)
class Pass_: ...
@dataclass(frozen=True, slots=True)
class Flag: ...
@dataclass(frozen=True, slots=True)
class CannotDetermine:
    reasons: tuple[ReasonCode, ...]
    fields: tuple[FieldName, ...]
@dataclass(frozen=True, slots=True)
class NeedsLegalReview:
    reasons: tuple[ReasonCode, ...]

Outcome = Pass_ | Flag | CannotDetermine | NeedsLegalReview
```

Every consumer uses exhaustive `match` with `assert_never`. Names avoid shadowing builtins (hence `Pass_`, or use `Verdict` variants like `Passed`, `Flagged`; pick one and keep it).

**Reason codes.** A closed `StrEnum` (Appendix A). Each code has a stable string value, a category (decision, abstention-data, abstention-scope, rejection, fault), and a human template. Adding a code requires a test that it is categorized and templated.

**Error hierarchy.**

```text
WageGuardError
├── InputRejected            # malformed input (Rejection)
├── ConfigurationError
├── EvidenceError
│   ├── RetrievalUnavailable
│   └── SourceVersionMismatch
├── LlmError
│   ├── LlmTimeout
│   ├── LlmMalformedOutput
│   └── LlmRefused
├── VerificationFailed
│   ├── CitationNotRetrieved
│   ├── QuoteMismatch
│   └── OutcomeContradiction
└── LedgerError
    ├── ChainBroken
    └── AppendFailed
```

Faults are the `EvidenceError`, `LlmError`, `VerificationFailed`, and `LedgerError` subtrees. They are distinct from `InputRejected`.

### 7.3 Test plan (written first)

- `Money`: float rejected; Decimal equality; `0.1 + 0.2` style precision cases handled exactly; mixed currency raises; comparison across one-cent boundaries.
- `EffectiveRange`: boundary dates (start inclusive, end exclusive), open-ended ranges, invalid ranges, overlap detection including adjacent ranges (which must **not** overlap).
- `PassageId`: parse/format round trip (property test); malformed IDs rejected.
- Outcome exhaustiveness: a test function using `match` with `assert_never` compiles under mypy; adding a variant in a scratch test fails type check (documented, not automated).
- Reason code table: every code has a category and template.

### 7.4 Design notes

- **Why a closed sum type:** the compiler becomes the guard against forgotten cases. It is the cheapest and strongest safety mechanism available.
- **Why half-open ranges:** rules change on a date. `[start, end)` makes adjacent rule versions tile without gaps or overlap, and a date belongs to exactly one version. Document this prominently, since off-by-one on effective dates is a classic compliance bug.
- **Why a Fault is not an Outcome:** a network timeout cannot be allowed to look like "cannot determine", because downstream consumers would treat it as a normal abstention and not page anyone.

### 7.5 Acceptance criteria

- [ ] 100% branch coverage on `domain/`.
- [ ] `mypy --strict` clean with no ignores in `domain/`.
- [ ] Hypothesis round-trip tests for `PassageId`, `EffectiveRange` ordering, and canonical `Money` serialization.
- [ ] Architecture test: `domain/` imports only the standard library.
- [ ] ADR for Decimal quantization policy and half-open ranges merged.

---

## 8. Phase 2: Intake and the required-facts graph

> **Standards Reminder:** S-2 (Pydantic only at the boundary), S-3 (reject versus abstain), S-6 (property tests), S-9 (no silent assumptions). Do not default a missing fact. Abstention must fall out of structure, not prompts.

### 8.1 Objective

Convert untrusted JSON into validated domain facts, then determine, per check, which required facts are present, missing, invalid, or ambiguous, with every offending field reported at once.

### 8.2 Intake pipeline

1. **Parse:** JSON into a Pydantic model (`CheckRequestModel`) with `extra="forbid"` and strict types. Unknown fields are rejected, so typos never silently become "missing".
2. **Validate:** types, enums, units, date formats (ISO 8601 `YYYY-MM-DD` only), money format (decimal strings, not JSON floats).
3. **Normalize:** trim whitespace, normalize Unicode to NFC, uppercase two-letter state codes, canonicalize enum casing. Normalization is documented and tested, and it never invents data.
4. **Convert** to domain `RawFacts`: a mapping from `FieldName` to a `FactValue` or an explicit absence marker.

**Reject versus abstain.** Structurally malformed input (wrong type, unparseable date, unknown field, negative pay) is a **Rejection** (`InputRejected`). It carries field-level errors and never produces a compliance outcome. A well-formed record that lacks required facts is an **Abstention**. The boundary is deliberate: `{"pay_rate": "abc"}` is rejected; `{}` for a minimum-wage check is `CANNOT_DETERMINE`.

> Edge case to resolve in an ADR: a field that is present but `null`. Policy: explicit `null` is treated as MISSING, and an empty string is INVALID. Both are tested.

### 8.3 Fact statuses

```python
class FactStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    INVALID = "invalid"        # present but unusable for this check
    AMBIGUOUS = "ambiguous"    # present but could mean more than one thing
```

`INVALID` versus `MISSING` matters operationally: missing data needs collection, invalid data needs correction. `AMBIGUOUS` examples: a work location given as a city name that exists in multiple states, a pay basis labeled "annual" where the check expects hourly, a record listing two work states for the same period.

### 8.4 Required-facts declaration

Each check declares its needs as data:

```python
@dataclass(frozen=True, slots=True)
class RequiredFact:
    name: FieldName
    validator: Callable[[FactValue], FactStatus]   # pure
    why: str                                       # shown in explanations

MINIMUM_WAGE_FACTS: tuple[RequiredFact, ...] = (
    RequiredFact(FieldName.WORK_STATE, validate_us_state, "Determines applicable rules"),
    RequiredFact(FieldName.WORK_DATE, validate_work_date, "Rules are effective-dated"),
    RequiredFact(FieldName.PAY_RATE, validate_money, "Compared against the minimum"),
    RequiredFact(FieldName.PAY_BASIS, validate_pay_basis, "Rate must be hourly to compare directly"),
    RequiredFact(FieldName.WORKER_CATEGORY, validate_category, "Special categories are out of scope"),
)
```

Resolution returns `FactResolution` with a mapping of every required fact to its status. If any fact is not `PRESENT`, the resolver emits `CannotDetermine` listing **all** offending fields in a stable order. It does not stop at the first.

### 8.5 Scope guard

Runs before fact resolution for categorical scope (worker category, jurisdiction support) and after for value-dependent scope (work date outside any ingested rule range).

- Unsupported worker category (tipped, youth, student, and others) means `NEEDS_LEGAL_REVIEW` with `OUT_OF_SCOPE_WORKER_CATEGORY`.
- Unsupported jurisdiction means `NEEDS_LEGAL_REVIEW` with `OUT_OF_SCOPE_JURISDICTION`.
- Work date before the earliest or after the latest covered rule range means `NEEDS_LEGAL_REVIEW` with `DATE_OUTSIDE_RULE_COVERAGE`.
- Pay basis not hourly: do **not** convert salary to hourly silently. Converting needs hours assumptions that are themselves a legal question. Return `CANNOT_DETERMINE` naming `hours_worked` unless the check explicitly supports a documented conversion with the required fact present. For the MVP, only hourly pay is evaluated, and salaried records route to the exemption path or legal review.

### 8.6 Test plan

- Table-driven tests for each validator over valid, boundary, and invalid values.
- Property test: for any subset of required facts removed, the resolver reports exactly that subset as missing, in stable sorted order.
- Property test: field order in the input JSON never affects the result.
- Unit tests for `null` versus empty string versus absent.
- Normalization idempotence: `normalize(normalize(x)) == normalize(x)`.
- Rejection tests: unknown fields, float JSON money, non-ISO dates, negative or zero rates (policy documented), oversized strings.

### 8.7 Acceptance criteria

- [ ] Every abstention path produces machine-readable reason codes and field names.
- [ ] No code path supplies a default for a required fact (architecture test greps for default assignments in resolvers).
- [ ] Rejection and abstention are provably distinct types.
- [ ] Property tests pass with at least 500 generated examples in CI.
- [ ] Schema documentation is generated from the Pydantic models into `docs/schemas/`, and CI checks it is current.

---

## 9. Phase 3: Rules as data and the minimum-wage engine

> **Standards Reminder:** S-2 (Decimal), S-4 (pure functions), S-6 (property and metamorphic tests), S-11 (no legal claims from memory). **Every number in a rule file comes from an official source you read. Claude Code must not supply or "remember" thresholds.**

### 9.1 Objective

Encode applicable minimum-wage rules as effective-dated, source-linked data and evaluate them with a pure, exhaustively tested engine that answers *"what rule applied on this work date, and does this pay rate satisfy it?"*.

### 9.2 Jurisdiction selection

Choose three: **federal**, plus **two states** deliberately chosen to exercise different engine paths:

- **State A** where the state minimum is above the federal minimum (tests "higher controls" with the state winning).
- **State B** where the state minimum equals or is below the federal minimum, or has no state minimum of its own (tests "higher controls" with the federal rate winning, and the no-state-rule path).

`VERIFY:` confirm each state's current and historical rates and exact effective dates from the state labor department. Record every source in the manifest. Avoid states with a heavy local-ordinance patchwork unless local rules are explicitly out of scope and flagged (see 9.6).

### 9.3 Rule file format

```yaml
# data/rules/minimum_wage/us-federal.yaml
ruleset_version: "2026.11.0"
rules:
  - rule_id: "us-fed.minimum_wage.general"
    jurisdiction: "US"
    topic: "minimum_wage"
    worker_category: "general"
    value: "<VERIFY: decimal string from DOL source>"
    unit: "USD/hour"
    effective_from: "<VERIFY: ISO date>"
    effective_to: null            # open-ended, or a date
    supporting_passages:
      - "<passage_id resolved at ingestion>"
    review_status: "not_reviewed_by_counsel"
    notes: "Why this row exists; what it does not cover."
```

Load-time validation (pure, tested):

- `value` is a decimal string, never a number.
- No two rules with the same `(jurisdiction, topic, worker_category)` have overlapping effective ranges.
- No unexplained gaps between consecutive ranges. Gaps are either explicitly allowed with a note or fail the load.
- Every `supporting_passage` resolves to an ingested passage (checked at the integration level, since the rule loader itself stays pure).
- `review_status` is one of a closed set.
- The ruleset is hashed (canonical serialization) and the hash is the `ruleset_hash` recorded in decisions. Editing a rule changes the hash, so decisions are always tied to exact rule content.

### 9.4 Engine design

```python
def applicable_rule(
    rules: Rules, jurisdiction: Jurisdiction, topic: Topic,
    category: WorkerCategory, on: date,
) -> RuleLookup: ...        # Found(rule) | NoRule | Ambiguous(rules)

def evaluate_minimum_wage(facts: MinimumWageFacts, rules: Rules) -> EngineResult: ...
```

`evaluate_minimum_wage` steps:

1. Resolve the set of jurisdictions that apply to the work location: always federal, plus the state if supported. Local jurisdictions are out of scope (9.6).
2. For each, look up the applicable rule on `work_date`. `Ambiguous` (overlapping rows) is a ruleset defect and a **Fault** (`ConfigurationError`), not an abstention.
3. If the state is supported but has **no** state rule for the date, apply the documented no-state-rule path: federal controls. The reason is recorded as `STATE_RULE_ABSENT_FEDERAL_APPLIES`, and the evidence must include the passage supporting that absence. If the corpus cannot support the absence, abstain.
4. Compute the controlling rate as the maximum of the applicable rates, and record **which rule controlled** and the full candidate list (for the audit).
5. Compare `pay_rate >= controlling_rate`: `PASS`; otherwise `FLAG`. Comparison is exact `Decimal`. Never round before comparing.

`EngineResult` carries: outcome, controlling rule ID, candidate rules considered, comparison values, shortfall amount (for `FLAG`), and the list of passage IDs that must be cited (from the rules' `supporting_passages`). **Required citations come from the engine, not from retrieval.** Retrieval supplies additional context, but the minimum evidence for a decision is dictated by the rules that decided it. This closes the gap where a retriever returns plausible-but-irrelevant text.

### 9.5 The conflict principle (encode as code with an ADR)

> Where more than one encoded rule applies to the same worker, work location, and date, the highest applicable rate controls.

This is a legal principle you must source: `VERIFY:` find and cite the DOL/statutory text stating the federal floor and that higher state rates apply, and store it as a rule-level supporting passage. The ADR records the principle, its source, and its limits. Anything the principle does not cover goes to `NEEDS_LEGAL_REVIEW`.

### 9.6 Explicitly out of scope, routed to legal review

- Local (city/county) minimums. If the work location carries a locality field that is not in the supported set, `NEEDS_LEGAL_REVIEW` with `LOCAL_RULES_NOT_ENCODED`.
- Multi-state work in a pay period.
- Pay periods straddling a rule change date. The MVP evaluates a single `work_date`, so a `period_start`/`period_end` input spanning a boundary returns `NEEDS_LEGAL_REVIEW` with `PERIOD_STRADDLES_RULE_CHANGE`. This case is a must-have in the golden set.
- Tipped, youth, student, and other special categories.
- Employer-size or industry-dependent state thresholds. If a state rate depends on employer size and that fact is not supplied, `CANNOT_DETERMINE` for `employer_size`, or the state is excluded from the MVP. Prefer choosing states that avoid this.

### 9.7 Test plan

**Unit:** boundary rate exactly at, one cent below, one cent above the controlling rate; date exactly on an effective-from date and the day before; no-state-rule path; state-above-federal; federal-above-state (if the data allows, otherwise synthetic rules in a test ruleset).

**Property (Hypothesis):**
- Never `PASS` when `pay_rate < controlling_rate`.
- Monotonic: if a rate passes, any higher rate passes.
- Adding a lower-rate applicable rule never changes the outcome (max semantics).
- Output is independent of rule list ordering.

**Metamorphic:**
- Changing state to one with a different rate changes `controlling_rule` accordingly.
- Shifting `pay_rate` by one cent across the threshold flips `PASS` and `FLAG`.
- Reordering input fields changes nothing.

**Ruleset validation tests:** overlapping ranges, gaps, non-decimal values, missing source links, unknown review status all fail loading with specific errors.

Use a **synthetic test ruleset** (fake jurisdictions "TESTLAND-A/B" with invented rates) for engine logic tests. The engine's correctness must not depend on real legal values. Real rule files are tested separately for structural validity.

### 9.8 Acceptance criteria

- [ ] Every rule row has a supporting passage and a `review_status`.
- [ ] No legal value exists in code. Search of `src/` finds none.
- [ ] 100% branch coverage on `compliance/`.
- [ ] Mutation testing (`mutmut` or `cosmic-ray`) on the engine reaches a score you can state in the README. Surviving mutants are triaged.
- [ ] The straddle, local-rule, and special-category cases return `NEEDS_LEGAL_REVIEW` with distinct reason codes.
- [ ] Ruleset hash changes when any rule value changes.

---

## 10. Phase 4: Evidence corpus and ingestion

> **Standards Reminder:** S-7 (reproducibility), S-8 (small commits), S-11 (honesty about freshness). Sources are immutable once ingested. Never rewrite evidence behind an old decision.

### 10.1 Objective

Build a small, fully documented corpus of official sources, ingested into PostgreSQL+pgvector as immutable, content-hashed source versions with stable passage IDs.

### 10.2 Source manifest

`data/sources/manifest.yaml` lists every source:

```yaml
sources:
  - source_key: "dol_flsa_minwage"
    publisher: "US Department of Labor"
    title: "<exact page title>"
    url: "<canonical official URL>"
    jurisdiction: "US"
    topics: ["minimum_wage"]
    source_type: "agency_guidance"      # statute | regulation | agency_guidance | state_agency
    fetch_method: "html"
    notes: "Why included."
```

Selection rules: **primary and official only**. Statute or regulation text where possible, then agency guidance and fact sheets. No law-firm blogs, no aggregators, no AI-generated summaries. Record the publisher and source type so the README can state the provenance hierarchy.

### 10.3 Fetching and snapshotting

- A separate `ingest` command fetches each URL, stores the **raw bytes** in `data/snapshots/<sha256>.<ext>` (content-addressed), and records HTTP status, final URL after redirects, response headers relevant to freshness (`Last-Modified`, `ETag`), retrieval timestamp, and SHA-256.
- Fetching honors `robots.txt`, uses a descriptive User-Agent, rate-limits, and has timeouts and bounded retries.
- Snapshots are committed (or stored as release artifacts if large) so a clean checkout reproduces the exact corpus offline. **`make reproduce` uses snapshots only, with no network.** Live refetch is a separate explicit command, `wageguard ingest --refresh`.
- Network access at test time is forbidden. Tests use snapshots or fixtures.

### 10.4 Versioning

- A source version is identified by `(source_key, content_hash)`, with a monotonically increasing `version_no` per source.
- Re-ingestion where the content hash is unchanged records a "verified unchanged" event, with no new version.
- Where it changed, a **new** source version is created. Old versions and their passages are never modified or deleted. Decisions reference exact source versions, so old decisions remain reproducible.
- A rule referencing a passage of an old version continues to resolve. Updating a rule to a new version is a deliberate, reviewed ruleset change with a new ruleset version.

### 10.5 Text extraction and chunking

- HTML: extract main content with a documented extractor, preserving heading hierarchy; strip navigation, scripts, and boilerplate; keep a mapping from extracted text to source structure. PDFs, if used: a documented extractor, with verification that text extraction did not mangle numbers (a spot-check test on every numeric passage).
- **Chunking is structure-aware**: split on headings and paragraphs, then merge or split to a bounded size with small overlap only where needed. Each chunk keeps its heading path (`"Fact Sheet > Coverage > Employees"`).
- **Passage IDs are stable and deterministic:** `source_key@v{version_no}#p{ordinal:03d}`, ordinal by document order. The same snapshot always yields the same IDs and the same chunk text. This is a tested property: chunking is a pure function of the snapshot bytes plus the chunker version.
- Each passage stores: text, normalized text (for quote matching), heading path, character offsets in the extracted text, token count, content hash, and the chunker version.

### 10.6 Embeddings

- The embedding model is **pinned and recorded** (model ID, dimension, normalization). Dimension is a config value verified against the model at startup.
- One embedding model per index. The index records its `embedding_model_id`. Attempting to insert or query with a different model raises `ConfigurationError`. This prevents silently mixing vector spaces.
- Embeddings are cached by `(model_id, passage_content_hash)` so re-ingestion does not recompute unchanged passages, and so the cache can be part of reproducibility.
- Test embeddings use a deterministic fake embedder (hash-based), so retrieval logic is testable without a network or model.

### 10.7 Schema (see Appendix C for full DDL)

Tables: `sources`, `source_versions`, `passages` (with `embedding vector(N)`), `embedding_models`, `ingestion_events`. Foreign keys everywhere, `NOT NULL` by default, check constraints for hash lengths and ID formats, and an index strategy documented in an ADR (HNSW versus IVFFlat; for a corpus this small an exact scan is fine and simpler, so say so, and note when you would switch).

### 10.8 Corpus hygiene and documentation

- `docs/source-register.md` is **generated** from the manifest and database: publisher, title, URL, jurisdiction, retrieval timestamp, content hash, version, passage count. CI verifies it is current.
- Every passage that a rule depends on is reviewed by a human: read it, confirm the number and effective date in the passage match the rule row. A review log records reviewer, date, and passage hash. Surface this in the README as "rule values checked against these passage hashes on this date".

### 10.9 Test plan

- Chunker determinism: same bytes yield identical passages; property test that concatenated chunk text covers the extracted text (no silent drops).
- Passage ID stability across runs.
- Hash verification: tampering with a snapshot file is detected at load.
- Version semantics: changed content yields a new version, unchanged yields none, and old passages remain queryable.
- Numeric-fidelity spot test: every passage containing a currency figure is compared against the raw snapshot.
- Embedding model mismatch raises.
- Ingestion is idempotent and transactional: a failure midway leaves no partial source version.

### 10.10 Acceptance criteria

- [ ] The corpus ingests from snapshots with no network access.
- [ ] Re-running ingestion is a no-op that records "unchanged".
- [ ] A modified snapshot creates a new version and leaves old passages untouched.
- [ ] `docs/source-register.md` is generated and current.
- [ ] Every rule-supporting passage has a recorded human review entry.
- [ ] The embedding model ID is stored and enforced.

---

## 11. Phase 5: Retrieval

> **Standards Reminder:** S-4 (ports), S-6 (adversarial tests), S-3 (fail closed). A semantically similar passage from the wrong jurisdiction must be impossible to retrieve, not merely unlikely.

### 11.1 Objective

Return the minimal, correctly scoped evidence bundle for a decision, with hard metadata filters applied before similarity ranking.

### 11.2 Design

**Hard filters first.** Retrieval is a single parameterized SQL query that filters on `jurisdiction IN (applicable set)`, `topic`, and the **source version's validity for the work date** (where source effective dates are known), and only then orders by vector distance. The filter is part of the query (`WHERE`), not a post-filter in Python, so a wrong-jurisdiction passage can never enter the candidate set.

**Required evidence is separate from supplemental evidence.**

- *Required passages* come from the engine (the decision's controlling and compared rules, plus the passage supporting the conflict principle). They are fetched by ID, not by similarity.
- *Supplemental passages* come from similarity search within the filtered set, capped at `k` (small, e.g. 3 to 5, configured), and limited by a distance threshold. A passage beyond the threshold is not included, even if it is the nearest.

The evidence bundle is `required + supplemental`, deduplicated, ordered deterministically (required first in rule order, then supplemental by distance with a stable tiebreak on passage ID).

**If a required passage cannot be fetched** (missing, hash mismatch, source version mismatch), the run is a **Fault** (`EvidenceError`), never a degraded decision. If the engine produced `PASS`/`FLAG` and cannot be evidenced, the system does not emit it.

**Query construction.** The retrieval query text is built from the check type and rule identifiers, not from free-text user input, so no user-controlled string reaches the embedder. (This also shrinks the prompt-injection surface.)

### 11.3 The retriever port

```python
class EvidenceRetriever(Protocol):
    def fetch_required(self, ids: Sequence[PassageId]) -> tuple[Passage, ...]: ...
    def search(self, q: SearchQuery) -> tuple[ScoredPassage, ...]: ...
```

`SearchQuery` is a frozen dataclass: `jurisdictions`, `topic`, `as_of: date`, `text`, `k`, `max_distance`. Tests use an in-memory implementation that honors the same filter semantics, and integration tests prove the Postgres implementation agrees with the in-memory one via a shared contract test suite.

### 11.4 Test plan

- **Contract tests** run against both the in-memory and Postgres implementations.
- **Wrong-jurisdiction adversarial test:** seed a passage from State X that is a near-perfect semantic match for a State Y query; assert it is never returned for State Y.
- **Topic filter test:** same, across topics.
- **Date filter test:** a source version not valid at `as_of` is excluded.
- **Determinism:** identical queries yield identical ordered results, including tie cases.
- **Threshold test:** passages beyond `max_distance` are excluded even when `k` is not filled.
- **Missing required passage** returns `RetrievalUnavailable`/`SourceVersionMismatch`, never partial results silently.
- **Embedding model mismatch** at query time raises.
- Injection regression: retrieval text built only from controlled fields. A test asserts that user-supplied free-text fields cannot influence the query string.

### 11.5 Acceptance criteria

- [ ] No code path filters jurisdiction after ranking.
- [ ] Contract suite passes on both implementations.
- [ ] A missing required passage produces a Fault and no decision.
- [ ] Retrieval results are fully deterministic for a fixed corpus.
- [ ] The evidence bundle is serializable canonically (hash stable) for the ledger.

---

## 12. Phase 6: Explainer and verifier

> **Standards Reminder:** S-3 (fail closed), S-6 (adversarial tests, behavior over mocks), S-7 (pin and record everything), S-9 (no sensitive data in prompts beyond need). The LLM writes prose. It never decides and never invents citations.

### 12.1 Objective

Produce a plain-language, cited explanation of an engine-determined outcome using a constrained LLM call, then verify the output so that no unsupported or inconsistent explanation can reach the ledger as a decision.

### 12.2 Explainer contract

Input to the model (assembled by code, never by free text from the user):

- The engine outcome (fixed), the controlling rule, the numeric comparison, and the shortfall if any.
- The evidence bundle: each passage with its `passage_id` and text.
- Instructions: explain the outcome using only supplied passages; cite by `passage_id`; do not state facts not in the passages or facts; do not change or question the outcome; if the passages do not support the outcome, output the `INSUFFICIENT_EVIDENCE` flag.

Required structured output (JSON Schema enforced at the API where supported, then validated again locally):

```json
{
  "asserted_outcome": "PASS|FLAG",
  "summary": "string, max N chars",
  "claims": [
    {
      "text": "string",
      "citations": [{"passage_id": "string", "quote": "string|null"}]
    }
  ],
  "insufficient_evidence": false
}
```

Settings: temperature 0, pinned model identifier (not an alias), a `max_tokens` bound, a timeout, and bounded retries with backoff for transport errors only. **A malformed or schema-invalid response is not retried indefinitely.** Allow at most one retry, then fail as `LlmMalformedOutput` (a Fault).

### 12.3 Prompt management

- Prompts live in `prompts/<name>/vN.txt`, are immutable once released, and are registered in `prompts/registry.yaml` with their SHA-256.
- The loaded prompt's hash is verified against the registry at startup. A mismatch is `ConfigurationError`.
- Prompt text uses clearly delimited sections and treats passage text as **data, not instructions** (delimited blocks plus an explicit instruction that content within them is untrusted source text). Passage text comes from official sources but may still contain imperative language, so the delimiting is not optional.
- A change to prompt text requires a new version file. Editing an old version is blocked by a hash check in CI.

### 12.4 Verifier

The verifier is deterministic code. Checks, **in order**, each with a distinct reason code:

1. **Schema:** output parses and validates against the local schema. Fail: `LlmMalformedOutput`.
2. **Outcome consistency:** `asserted_outcome` equals the engine outcome. Fail: `OutcomeContradiction`.
3. **Insufficient evidence:** if the model flags `insufficient_evidence`, the run is a Fault `VerificationFailed` (the model declined to support the decision). The engine outcome is **not** emitted as a sourced decision.
4. **Citation existence:** every cited `passage_id` is in the evidence bundle for **this run**. Fail: `CitationNotRetrieved`. This includes IDs that exist in the database but were not retrieved for this decision, and IDs from other jurisdictions or other source versions.
5. **Required citations present:** every passage the engine marked required appears in at least one citation. Fail: `MissingRequiredCitation`.
6. **Quote verification:** each non-null `quote` must appear in the cited passage's text after documented normalization only (Unicode NFC, collapsing whitespace, normalizing quote and dash characters). Matching is exact substring after normalization, with no fuzzy matching. Fail: `QuoteMismatch`.
7. **Claim coverage:** every claim has at least one citation. Uncited claims are rejected.
8. **Numeric agreement:** any dollar figures stated in `summary` or `claims` must match the engine's values exactly (extracted by a documented regex and compared as `Decimal`). A figure that appears in prose and is absent from both the engine result and the cited passages is rejected. This catches the model "helpfully" rounding or inventing numbers.

All checks run and **all** failures are collected before raising, so the ledger fault record is complete. A verification failure produces a Fault record with the raw model output stored (subject to the privacy mode) for debugging.

> The verifier proves citation integrity, not semantic support. Document this in the README and in the module docstring.

### 12.5 Abstention explanations

For `CANNOT_DETERMINE` and most `NEEDS_LEGAL_REVIEW` outcomes, the explanation is **templated** from reason codes and field names. No LLM call is made. This is deterministic, free, and removes a hallucination surface. Templates are versioned data, hashed, and recorded like prompts.

### 12.6 LLM port and cassettes

```python
class LlmClient(Protocol):
    def generate_structured(self, req: LlmRequest) -> LlmResponse: ...
```

- `AnthropicClient` (real), `CassetteClient` (replays recorded responses keyed by a hash of the canonical request), and `FakeClient` (scripted responses for unit tests).
- The cassette key includes model ID, prompt hash, settings, and the canonical evidence bundle. Any change to the request makes the cassette miss, and a miss in CI is a **test failure**, not a silent live call. Cassettes are recorded via an explicit `make record-cassettes` run, with an API key, reviewed in the diff.
- Usage (tokens, latency) and cost are captured from the provider response where available, and recorded as `NULL` when not returned. They are never estimated silently.

### 12.7 Adversarial verifier tests (must all exist)

- Fabricated passage ID that matches no passage.
- Real passage ID from the database that was not retrieved for this run.
- Real passage ID from the wrong jurisdiction.
- Passage ID from a **superseded source version**.
- Altered quote (one word changed), altered number, truncated quote.
- Quote correct but attached to the wrong passage ID.
- Model asserts the opposite outcome.
- Model states a dollar figure not in the engine result.
- Model emits an uncited claim.
- Model emits extra fields or a wrong schema.
- Model output containing instruction-like text embedded in a quote (must still be treated as data).
- Empty citations list on a decisive outcome.

Each test constructs the model output directly (via `FakeClient`) and asserts on the verifier result. These do not depend on any live model.

### 12.8 Acceptance criteria

- [ ] All adversarial cases above fail verification with the correct reason code.
- [ ] No decisive outcome reaches the ledger without passing all verifier checks.
- [ ] Abstentions emit templated explanations with no LLM call (asserted by a client that raises if called).
- [ ] The prompt hash is verified against the registry at startup.
- [ ] A cassette miss fails the test run.
- [ ] Verification collects all failures before raising.

---

## 13. Phase 7: Ledger and replay

> **Standards Reminder:** S-2 (canonical serialization, Decimal), S-3 (append failure is a Fault), S-7 (reproducibility), S-9 (privacy mode). The ledger is the system's source of truth. Treat it like financial infrastructure.

### 13.1 Objective

Record every completed check and every fault as an append-only, hash-chained record, and provide `replay` and `ledger verify` commands that make decisions reproducible and tampering evident.

### 13.2 What is recorded

Every record stores:

| Group | Fields |
|---|---|
| Identity | `decision_id`, `sequence_no`, `created_at` (UTC), `app_version`, `git_commit`, `record_kind` (`decision`, `abstention`, `fault`, `rejection`, `replay`) |
| Check | `check_type`, `input_schema_version`, `ruleset_version`, `ruleset_hash` |
| Input | `input_hash`, `input_snapshot` (synthetic mode) or `NULL` (privacy mode) |
| Facts | fact statuses, missing/invalid/ambiguous field names |
| Engine | outcome, reason codes, controlling rule ID, candidate rules, comparison values |
| Evidence | passage IDs, source version IDs, passage content hashes, retrieval parameters, embedding model ID |
| LLM | provider, exact model ID, settings, prompt version and hash, raw output (privacy mode permitting), usage, latency, cost (nullable) |
| Verification | per-check results and reason codes |
| Fault | fault category, error class, message, stage |
| Lineage | `replay_of` (nullable `decision_id`), `replay_mode` |
| Chain | `prev_hash`, `record_hash` |

### 13.3 Canonical serialization (Appendix D)

Hashing needs a canonical form, otherwise hashes drift for irrelevant reasons.

- JSON with sorted keys, no insignificant whitespace, UTF-8, Unicode NFC.
- `Decimal` serialized as a normalized string (no exponent, no trailing zeros beyond a documented rule). **Floats are rejected** at serialization time with an error.
- Dates as ISO 8601, datetimes as UTC RFC 3339 with fixed precision.
- Enums by value, tuples as arrays, sets forbidden (use sorted tuples).
- `None` is explicit `null`. Absent and null are distinct, and the schema decides which is used.
- Canonicalization carries a **version** (`canon_v1`) stored in every record, so future changes do not break verification of old records.

`record_hash = SHA-256(prev_hash_bytes || canonical_bytes(record_without_hashes))`. The genesis `prev_hash` is 32 zero bytes. Hex-encode for storage.

### 13.4 Append-only enforcement (defense in depth)

1. **Database privileges:** the application role has `INSERT` and `SELECT` only on the ledger table, with `UPDATE`, `DELETE`, and `TRUNCATE` revoked.
2. **Trigger:** a `BEFORE UPDATE OR DELETE` trigger raises an exception, so even a privileged mistake is blocked and the attempt is visible.
3. **Chain linkage:** each record's `prev_hash` must equal the previous record's `record_hash`. A unique constraint on `sequence_no` plus a check on linkage at insert time.
4. **Serialized appends:** a single-row `ledger_head` table is locked (`SELECT ... FOR UPDATE`) inside the append transaction to read the previous hash and bump the sequence, so concurrent writers cannot fork the chain. (Document the throughput implication, which is acceptable for this workload.)
5. **Verify command:** `wageguard ledger verify` walks the chain, recomputes every hash from canonical content, checks linkage and sequence continuity, and reports the first break with its sequence number.

Be honest in the README: this makes tampering **evident**, not impossible. A privileged actor could rewrite the whole chain consistently. The mitigation is **head anchoring**: periodically export the head hash and sequence number (to a git-tracked file, a signed tag, or an external timestamping service), so a rewrite would conflict with the anchor. Implement `wageguard ledger anchor` that writes a signed, timestamped head record; the signing mechanism is documented as optional for the prototype.

### 13.5 Transactionality and the commit point

The append is one transaction: lock head, compute hash, insert record, update head, commit. If the append fails, the check returns a Fault to the caller, and **no decision is considered made**. The API response includes the `decision_id` only after a successful commit. A response without a durable record is a defect.

For faults that occur before a decision exists, a fault record is appended on a best-effort basis. If even that fails (database down), the failure is logged to stderr in structured form and the process exits non-zero. The system never reports success without a ledger record.

### 13.6 Privacy mode

Two modes, set per deployment:

- **`synthetic`:** stores the full input snapshot and raw model output. Used for the demo, golden runs, and development. Documented as synthetic-only.
- **`hash_only`:** stores `input_hash` and fact *statuses* but not values, plus a redacted model output. Replay in this mode requires the caller to supply the original input, which is verified against the stored hash before use.

The mode is recorded in each record so verification and replay behave correctly. A retention note in the README states that the prototype has no deletion workflow, and that any real deployment would need one plus legal review.

### 13.7 Replay

`wageguard replay <decision_id> [--mode exact|fresh]`

**Exact mode:**
1. Load the original record. If `record_kind` is `rejection`, return `CANNOT_REPLAY` (no decision to replay).
2. Obtain input from the snapshot (or the supplied input in `hash_only`, verified against `input_hash`).
3. Load the **stored** rule content by `ruleset_hash` (rulesets are archived by hash), the **stored** passages by content hash, and the stored prompt by version, verifying every hash. Any mismatch or missing artifact yields `CANNOT_REPLAY` with the reason.
4. Re-run the pipeline with the recorded model ID and settings, using stored evidence instead of retrieving.
5. Compare normalized results field by field.
6. Report `MATCH`, `DIFFERENT`, or `CANNOT_REPLAY`.
7. Write a **new** `replay` record linked via `replay_of`. The original is never mutated.

**Fresh mode:** re-evaluate against the **current** corpus and ruleset. Produces a new decision linked to the original, with a layered diff naming which layer changed: `input`, `ruleset`, `source`, `prompt`, `model`, or `output`. This answers "would we decide differently today, and why?".

**Diff semantics.** Differences are categorized:
- *Deterministic-layer difference* (engine outcome, rule IDs, evidence IDs): always significant and always reported as `DIFFERENT`.
- *Explanation-text difference* with a matching outcome and matching, valid citations: reported as `MATCH_WITH_TEXT_VARIATION`. Hosted models may vary wording even at temperature 0. State this rather than hiding it. The README defines exactly what "match" means, and the decisive fields are the outcome, reason codes, rule IDs, and citation sets.
- If the model is no longer available, `CANNOT_REPLAY` with `MODEL_UNAVAILABLE`.

For abstentions and engine-only results, replay is fully deterministic and byte-comparable (no LLM involved), and a test asserts exact equality.

### 13.8 Test plan

- Canonicalization: property tests that equivalent structures hash equally, that float input raises, key-order invariance, Decimal normalization equivalence (`"1.50"` versus `"1.5"` policy), Unicode normalization.
- Chain: append N records, verify passes; mutate any byte of any stored field (via a test-only superuser connection), verify fails at the correct sequence; delete a middle record, verify fails; reorder, verify fails.
- Append-only enforcement: `UPDATE` and `DELETE` as the application role fail; the trigger blocks even a privileged role.
- Concurrency: parallel appends from multiple connections produce a linear chain with no gaps or forks (integration test with threads or processes).
- Replay: exact replay of a decisive record using cassettes returns `MATCH`; changing the stored prompt hash yields `CANNOT_REPLAY`; changing a source passage in a test fixture yields `DIFFERENT` with source layer identified; replay never changes the original record (compare before and after).
- Commit-point test: simulate an append failure after the LLM call; assert no `decision_id` is returned.
- Privacy mode: `hash_only` records contain no input values (assert by scanning the serialized record for seeded sentinel values).
- Canonicalization versioning: a record stamped `canon_v1` verifies under the `canon_v1` implementation even after a hypothetical `canon_v2` exists (test with both).

### 13.9 Acceptance criteria

- [ ] `ledger verify` detects every class of tampering in the test matrix.
- [ ] The application DB role cannot update or delete ledger rows.
- [ ] Concurrent appends never fork the chain.
- [ ] Exact replay of engine-only outcomes is byte-identical.
- [ ] Replay never mutates existing records.
- [ ] Every record stores `canon_version`, `ruleset_hash`, and passage content hashes.
- [ ] The README states precisely what "tamper-evident" does and does not mean.

---

## 14. Phase 8: Evaluation, golden set, baseline, Evalforge

> **Standards Reminder:** S-6 (tests are the product here), S-7 (cassettes, held-out discipline), S-11 (report uncertainty honestly). The headline number is only credible if the evaluation is honest about its limits.

### 14.1 Objective

Measure how often the system is confidently wrong, with useful coverage, uncertainty intervals, a held-out split, and a head-to-head baseline, all executed through Evalforge without leaking wage-law concepts into it.

### 14.2 Golden set construction

**Size:** 40 cases. **Split:** 28 development, 12 held-out. Assign the split before tuning anything, record it in the case files, and run the held-out set only at defined milestones (end of Phase 8, before README numbers are finalized). Every held-out run is logged, so repeated peeking is visible. If you tune against held-out results, it stops being held out. Say so and re-split.

**Labeling discipline.** Cases are labeled by **you reading the rule and source**, not by running the system. Each case records the rule ID and passage ID that justify its expected outcome, plus a rationale. Where the correct label is itself uncertain, the expected outcome is `NEEDS_LEGAL_REVIEW`, and the case says why. A second pass (a day later, reread cold) catches labeling mistakes, and any change is logged.

**Case schema:**

```yaml
case_id: "mw-boundary-below-001"
split: "dev"                       # dev | heldout
category: "threshold_boundary"
description: "Pay one cent below the controlling state rate."
input: { ... synthetic record ... }
expected:
  outcome: "FLAG"
  reason_codes: []                 # for abstentions, exact expected codes
  missing_fields: []
  required_citations: ["<passage_id>"]
  forbidden_citations: []
label_basis:
  rule_id: "<rule id>"
  passage_ids: ["<passage_id>"]
  rationale: "Why this label is correct."
answerable: true                   # does the input contain enough to decide?
```

**Composition (40 cases, adjust counts to your supported scope):**

| Category | Count | Purpose |
|---|---:|---|
| Threshold boundary (below / exactly at / above, per jurisdiction) | 8 | Off-by-one and Decimal precision |
| Effective-date boundary (day before / day of rule change) | 4 | Effective dating |
| Federal vs state conflict (state higher, federal higher, no state rule) | 5 | Conflict principle |
| Missing required fact (each field singly, and several at once) | 6 | Abstention and complete field naming |
| Invalid / ambiguous field values | 4 | Invalid vs missing vs ambiguous |
| Out-of-scope category, locality, multi-state, straddle | 5 | Legal-review routing |
| Exemption salary-level (Tier 3) | 5 | Asymmetric exemption logic |
| Evidence/citation adversarial (wrong jurisdiction, fabricated ID, altered quote, superseded version) | 3 | Verifier |

Each category is split roughly 70/30 between dev and held-out, ensuring held-out covers every category at least once where counts allow.

Note that the adversarial-citation cases are partially covered by verifier unit tests (Phase 6). Their golden versions test the **end-to-end** fail-closed behavior, with a scripted model response in the cassette.

### 14.3 Scoring and metrics

Per case the scorer assigns one of:

- `CORRECT_DECISIVE`: decisive outcome equals expected.
- `CONFIDENTLY_WRONG`: system emitted `PASS`/`FLAG` and it differs from expected, **including** emitting a decisive result when the expected outcome is an abstention.
- `CORRECT_ABSTENTION`: expected abstention, produced the same abstention type with the correct reason codes and fields.
- `WRONG_ABSTENTION_TYPE`: abstained, but with the wrong type, codes, or fields.
- `OVER_ABSTENTION`: abstained when the case was answerable and a decisive result was expected.
- `FAULT`: infrastructure fault (counted separately, never as abstention).

Metrics:

```text
non_abstained          = CORRECT_DECISIVE + CONFIDENTLY_WRONG
confidently_wrong_rate = CONFIDENTLY_WRONG / non_abstained          (headline)
answerable_coverage    = CORRECT_DECISIVE / answerable_cases
correct_abstention_rate= CORRECT_ABSTENTION / should_abstain_cases
over_abstention_rate   = OVER_ABSTENTION / answerable_cases
citation_integrity_rate= runs passing all verifier checks / runs that reached verification
schema_valid_rate      = valid model outputs / model calls
fault_count            = FAULT
```

Report numerator and denominator alongside every rate, and report the metrics for the dev and held-out splits separately. Never pool them silently.

**Denominator edge cases:** if `non_abstained == 0`, the confidently-wrong rate is **undefined**, not zero. Report it as "undefined (system abstained on all cases)" and let coverage show the real picture. A system that abstains on everything must never look good.

### 14.4 Confidence intervals

Use the **Wilson score interval** for binomial proportions (95%, z = 1.96):

```text
p̂ = x / n
center = (p̂ + z²/(2n)) / (1 + z²/n)
half   = z * sqrt( p̂(1-p̂)/n + z²/(4n²) ) / (1 + z²/n)
interval = [center - half, center + half]
```

Implement it as a pure, unit-tested function with known reference values, including `x = 0` and `x = n` edge cases (Wilson handles these without collapsing to zero width). Report intervals for the confidently-wrong rate, coverage, and correct-abstention rate. With roughly 25 to 40 cases the intervals are wide, and the README says so directly: a point estimate of `0/20` is compatible with a true rate well above zero. This is the single most credible thing in the evaluation write-up.

### 14.5 Metamorphic and property evaluations

Beyond the golden cases:

- **Metamorphic suite** generated from base cases: state swap (outcome and controlling rule must change as the rules dictate), one-cent shift across thresholds, field reordering, irrelevant-field addition (rejected), whitespace and casing variants (normalization must make them equal), and renaming the synthetic record ID (no effect on outcome).
- **Property tests (Hypothesis)** over the full pipeline using the fake LLM and in-memory retriever: never `PASS` below the controlling rate; abstention fields are exactly the missing set; the pipeline is total (always returns exactly one of the four result categories).
- These run in CI on every commit. They are fast because they use the fakes.

### 14.6 The baseline

Build `baseline.py`: a deliberately plain **"LLM + RAG answers directly"** pipeline on the same corpus and model: retrieve top-k passages for the query (no hard filters beyond what a naive implementation would use), then ask the model to decide `PASS`/`FLAG`/`CANNOT_DETERMINE` with citations, with no deterministic engine, no required-facts graph, and no verifier. Treat it fairly: give the baseline a sensible prompt, the same model, the same corpus, and temperature 0. A strawman baseline is worse than none.

Run both on the **same golden set** and publish a side-by-side table: confidently-wrong rate (with intervals), coverage, correct abstention, citation integrity. Report honestly if the baseline does well on easy categories, which it may. The architecture's value shows in the abstention, boundary, and conflict categories. Break results down **by category** so the reader sees where the hybrid helps.

Record baseline runs through the same cassette mechanism and the same ledger-free harness, so the comparison is reproducible.

### 14.7 Evalforge integration

Boundary rules (from the project brief):

- Evalforge remains domain-agnostic. No wage, jurisdiction, or compliance vocabulary appears in the Evalforge repository.
- WageGuard supplies: the case files, an `evalforge_adapter.py` that converts cases into Evalforge's generic test-case format, and WageGuard-specific scorers (the outcome taxonomy above) supplied as a plugin or callable.
- Evalforge supplies: suite execution, schema validation of outputs, per-run latency and token cost, run-over-run regression comparison.

Integration via Evalforge's public interface (CLI or importable API), behind a small adapter so WageGuard does not depend on Evalforge internals. If Evalforge lacks a generic capability you need, add it **to Evalforge in its own commit**, with its own tests and no domain terms:

- Prompt/model version metadata attached to runs.
- A generic "replay a stored run" interface.
- Pluggable custom scorers.
- Regression comparison that is keyed on case IDs and stable across suite edits.

Then WageGuard consumes the released feature.

**Regression demonstration (Milestone 3 criterion):** commit a deliberate regression (for example, change a comparison from `>=` to `>` in a branch, or alter a prompt version) and show Evalforge reporting the pass-to-fail transitions. Save the output in `docs/evaluation/regression-demo.md` with the exact commands. Then revert.

### 14.8 Reporting

`make golden` produces `reports/golden-<timestamp>.json` plus a rendered markdown summary: per-case results, aggregate metrics with numerators, denominators, and Wilson intervals, per-category breakdown, dev versus held-out, baseline comparison, and the run metadata (git commit, ruleset hash, prompt hash, model ID, cassette set ID, corpus snapshot hashes). The README's numbers are copied from a committed report, and CI fails if the README's embedded numbers differ from the committed report (a small docs-check script).

### 14.9 Test plan for the evaluation code itself

The evaluation harness is code that can be wrong. Test it:

- Scorer: table of `(expected, actual) -> classification` covering every cell, including decisive-when-abstention-expected being `CONFIDENTLY_WRONG`.
- Metrics: known tallies produce known rates; `non_abstained == 0` yields undefined, not zero or an exception.
- Wilson interval: reference values (from a trusted statistical source you compute independently, such as `statsmodels` in a one-off script, with the script and result recorded), edge cases `x=0`, `x=n`, `n=1`.
- Split integrity: a test that every case file has a split, that no case ID appears in both, and that the held-out set is not referenced by any tuning script (grep-based check).
- Report-to-README consistency check.

### 14.10 Acceptance criteria

- [ ] One command, `make golden`, runs the full suite through Evalforge on cassettes and writes the report.
- [ ] The report includes per-case results, all metrics with numerators and denominators, and Wilson intervals.
- [ ] Dev and held-out are reported separately, and the held-out run log shows how many times it was run.
- [ ] The baseline runs on the identical cases, with a per-category comparison table.
- [ ] A deliberate regression is detected by Evalforge, and the demo is documented.
- [ ] Evalforge's repository contains no domain vocabulary (grep check in WageGuard's docs-check or a note in the Evalforge PR).
- [ ] The metrics code has its own tests, including the undefined-rate case.

---

## 15. Phase 9: Exemption screen (Tier 3)

> **Standards Reminder:** S-3 (asymmetric outcomes), S-11 (honesty about legal scope), S-6 (golden cases first). The point of this phase is to demonstrate domain judgment: knowing what a salary test can and cannot prove.

### 15.1 Objective

Add one narrow, conservative exemption screen that respects the asymmetry between a necessary condition and a sufficient one.

### 15.2 Legal shape (VERIFY every item against DOL sources)

Exemption from minimum wage and overtime under the FLSA generally depends on **both** a pay-related test and a duties test, with details varying by exemption category. The key engineering insight is logical, not legal:

- Failing a **necessary** condition (the minimum salary level, where the exemption requires one) is enough to say the exemption screen does not support the exempt classification.
- Passing a necessary condition proves nothing about the sufficient set. Salary level alone cannot establish exemption.

`VERIFY:` the current salary-level threshold and its effective dates, the salary-basis requirements, and whether any threshold is currently subject to litigation or an injunction. Exemption salary thresholds have been the subject of rulemaking and court challenges, so do not assume the figure in any source, including this document. If the status of the threshold is uncertain on the work date, that itself is a `NEEDS_LEGAL_REVIEW` reason (`THRESHOLD_STATUS_UNCERTAIN`), and the ruleset records the status explicitly.

### 15.3 Scope

Support **one** screen: the salary-level and salary-basis test for one exemption category of your choosing, chosen because its pay-related component is cleanly stated in the sources. State explicitly that duties are not evaluated unless you encode structured duties facts, and if you do, encode only facts the source text defines objectively. Do not encode judgment-laden duties tests ("exercises discretion and independent judgment") as automatable. Those route to legal review.

### 15.4 Outcome logic

Inputs: `current_exempt_status` (employer-recorded, treated as an assertion, not evidence), `pay_basis`, `salary_amount`, `pay_period`, `work_date`, `work_state`, and the category.

| Condition | Outcome | Reason code |
|---|---|---|
| Required facts missing | `CANNOT_DETERMINE` | per field |
| Salary basis not satisfied (e.g. hourly pay) | `FLAG` | `EXEMPT_SALARY_BASIS_NOT_MET` |
| Salary amount below the encoded threshold for the work date | `FLAG` | `EXEMPT_SALARY_LEVEL_NOT_MET` |
| Salary level and basis met, duties not evaluated | `NEEDS_LEGAL_REVIEW` | `EXEMPT_DUTIES_NOT_EVALUATED` |
| Salary level and basis met, structured duties encoded and objectively failed | `FLAG` | `EXEMPT_DUTIES_NOT_MET` |
| All encoded necessary conditions met and encoded duties facts affirm | `NEEDS_LEGAL_REVIEW` by default; `PASS` only with a documented, counsel-reviewable justification | `EXEMPT_NEEDS_HUMAN_CONFIRMATION` |
| State rule may impose a higher threshold, not encoded | `NEEDS_LEGAL_REVIEW` | `STATE_EXEMPTION_RULES_NOT_ENCODED` |
| Threshold status uncertain on work date | `NEEDS_LEGAL_REVIEW` | `THRESHOLD_STATUS_UNCERTAIN` |

The meaning of `FLAG` here is carefully worded: *"the facts do not satisfy the encoded necessary condition for the exemption"*, which is not "this worker is non-exempt". The explanation templates must reflect that phrasing, and a test asserts the explanation never claims a legal classification conclusion.

Default to `NEEDS_LEGAL_REVIEW` instead of `PASS` for exemption. The honest position is that a system should rarely, if ever, certify an exemption. Whether to allow any `PASS` path is an ADR decision, and refusing to certify is a legitimate and defensible choice.

### 15.5 Reuse and boundaries

This check reuses the same required-facts graph, rule store (effective-dated threshold rows), evidence retriever, explainer, verifier, ledger, and replay. If adding it requires changes to those, the earlier abstractions were wrong. Fix them rather than special-casing. A good test of the architecture: this phase should add one check module, one rules file, one prompt version, one facts declaration, and golden cases, with no edits to the ledger or verifier.

### 15.6 Test plan

- Salary exactly at, one cent below, one cent above the threshold, on the day before and the day of any threshold change.
- Hourly pay claimed as exempt returns `FLAG` for salary basis.
- `current_exempt_status = true` with insufficient salary returns `FLAG` (the employer's label does not override).
- `current_exempt_status = true` with sufficient salary and no duties facts returns `NEEDS_LEGAL_REVIEW`, never `PASS`.
- Threshold-status-uncertain ruleset row returns `NEEDS_LEGAL_REVIEW`.
- Property test: no input produces `PASS` unless the documented `PASS` path conditions are all met.
- Explanation tests: templates contain no classification conclusions.

### 15.7 Acceptance criteria

- [ ] The exemption check adds no changes to the ledger, verifier, or retrieval code.
- [ ] No input yields `PASS` without the documented conditions (property-tested).
- [ ] Five exemption cases appear in the golden set across both splits.
- [ ] Threshold values and status are sourced, hashed, and reviewed like every other rule.
- [ ] README states what the exemption screen does not evaluate.

---

## 16. Phase 10: Failure injection and resilience

> **Standards Reminder:** S-3 (fail closed, faults are not abstentions), S-6 (deterministic fault injection), S-10 (observability). A system is defined by how it fails.

### 16.1 Objective

Prove, by injected faults, that every failure mode produces a logged Fault and never a decision.

### 16.2 Fault matrix

| Injected fault | Stage | Expected behavior |
|---|---|---|
| Retrieval backend unavailable | Evidence | `RetrievalUnavailable` Fault logged; no decision |
| Required passage missing | Evidence | `EvidenceError` Fault |
| Source version swapped mid-run (hash differs from what the rule references) | Evidence | `SourceVersionMismatch` Fault |
| Embedding model mismatch | Evidence | `ConfigurationError` Fault |
| LLM timeout | Explainer | Bounded retry, then `LlmTimeout` Fault |
| LLM returns malformed JSON | Explainer | One retry, then `LlmMalformedOutput` Fault |
| LLM returns valid JSON with the wrong outcome | Verifier | `OutcomeContradiction` Fault |
| LLM refuses | Explainer | `LlmRefused` Fault |
| Rate limit / 429 | Explainer | Backoff within budget, then Fault |
| Ledger insert fails | Ledger | `AppendFailed`; no `decision_id`; non-zero exit |
| Database down at fault-logging time | Ledger | structured stderr log; non-zero exit |
| Ruleset has overlapping effective ranges at load | Startup | `ConfigurationError`; process refuses to start |
| Prompt file hash mismatch | Startup | `ConfigurationError` |
| Chain tamper detected at startup/verify | Ledger | `ChainBroken`; API refuses new decisions until resolved (configurable) |
| Clock skew / non-monotonic timestamps | Ledger | recorded; sequence number, not time, defines order |
| Concurrent duplicate submissions | Ledger | both recorded as separate decisions; no fork |

### 16.3 Implementation approach

- Faults are injected through the **ports**. A `FaultInjectingRetriever`, `FaultInjectingLlmClient`, and `FaultInjectingLedgerRepository` wrap the real or fake implementations and fail on schedule (always, first N calls, Nth call, with a given exception). No monkeypatching of internals.
- Each scenario asserts the *whole* contract: the returned category is `Fault`, the fault stage and class are correct, a fault record exists in the ledger (where the ledger is up), **no** record of kind `decision` exists for that request, and the process-level result (exit code or HTTP status) is correct.
- The distinction between a Fault and an Abstention is asserted explicitly in each test, because that is the property most likely to regress.

### 16.4 Resilience policies

- **Timeouts** on every external call, configured, and recorded.
- **Retries** only for idempotent, transient transport errors, with exponential backoff and jitter, a hard attempt cap, and a total time budget. No retry on verification failures, malformed outputs beyond the single allowance, or validation errors.
- **Idempotency:** a client-supplied `request_id` (optional) lets the API detect a duplicate submission and return the existing `decision_id` instead of creating a second record. Without it, duplicates are separate decisions. Document both behaviors.
- **No hidden fallbacks:** there is no "use a cheaper model if the main one fails" and no "skip verification if slow". A fallback that changes the evidence or the verifier changes the decision's defensibility, and silent fallbacks are banned by an ADR.
- **Graceful degradation applies only to explanation, never to the decision:** the engine's outcome is independent of the LLM. If the LLM is down, the system can still return an engine-only abstention. For decisive outcomes the system fails closed, because an unexplained and uncited decision does not meet the evidence requirement. (Document this decision and its tradeoff in an ADR.)

### 16.5 Acceptance criteria

- [ ] Every row in the fault matrix has an automated test.
- [ ] No fault scenario produces a record of kind `decision`.
- [ ] Faults are distinguishable from abstentions in the API response, the CLI exit code, and the ledger.
- [ ] Retries are bounded and the total latency budget is enforced (asserted with a fake clock).
- [ ] The system refuses to start with an invalid ruleset or prompt hash mismatch.

---

## 17. Phase 11: Interfaces, security, observability

> **Standards Reminder:** S-4 (thin edges, composition root), S-9 (security), S-10 (observability). Interfaces contain no business logic. The CLI comes first, and the API is a thin second adapter.

### 17.1 Composition root

One module wires everything: settings, DB engine, repositories, embedder, LLM client (real, cassette, or fake selected by config), clock, ID generator, ruleset, prompt registry. Both the CLI and the API call the same `CheckService`. No other module constructs infrastructure.

### 17.2 CLI

```text
wageguard check <input.json> [--check minimum_wage|exemption_salary] [--json]
wageguard replay <decision_id> [--mode exact|fresh]
wageguard ledger verify
wageguard ledger anchor
wageguard ledger show <decision_id> [--json]
wageguard ingest [--refresh]
wageguard rules validate
wageguard golden [--split dev|heldout|all] [--baseline]
```

Exit codes are a documented contract: `0` decision or abstention returned and logged; `2` input rejected; `3` fault (infrastructure); `4` verification failure; `5` ledger integrity failure; `1` unexpected error. Abstention exits `0`, because it is a correct, logged result, but the output makes the outcome unmistakable. Use `--json` for machine output and a concise human format by default, using Rich or plain text, with no decorative noise.

### 17.3 API (minimal)

FastAPI with a small surface:

- `POST /v1/checks` returns the check response (201 on a recorded decision/abstention; 422 for rejection; 503 for fault with a body naming the fault category; 409 for a duplicate `request_id` conflicting with different input).
- `GET /v1/decisions/{id}` returns the record (authorization required).
- `POST /v1/decisions/{id}/replay`.
- `GET /v1/ledger/verify` (admin).
- `GET /healthz` (liveness) and `GET /readyz` (DB, pgvector, ruleset and prompt hashes verified).

Response models are explicit Pydantic schemas generated into the OpenAPI document, and the OpenAPI output is committed and checked for drift in CI. HTTP statuses map to the four categories consistently: never return a 200 body that hides a fault.

### 17.4 Security

- Authentication on every non-health endpoint (API key with scopes is sufficient for the prototype, compared in constant time; keys hashed at rest if stored). Roles: `checker` (create checks), `auditor` (read decisions, verify ledger), `admin` (anchor, replay). Document that a real deployment would integrate with proper identity.
- Rate limiting and request size limits. Strict CORS (off by default).
- Input hardening: size limits, strict schemas, no dynamic evaluation, parameterized SQL only (asserted by a test that scans for string-formatted SQL), and SQLAlchemy Core or ORM with bound parameters.
- Prompt-injection posture documented: user-supplied free text never enters prompts, passage text is delimited as data, and the verifier does not trust model output. State plainly that the corpus is trusted-official content, so a compromised source could still poison explanations, which the content hashes and human review of rule-supporting passages mitigate but do not eliminate.
- Secrets via environment only. The database role used by the API is least-privilege (insert/select on the ledger, no DDL). Migrations run under a separate role.
- Dependency and image scanning in CI. SBOM generation is a nice-to-have.
- A short `docs/threat-model.md`: assets (ledger integrity, evidence integrity, input privacy), threats (tampering, evidence poisoning, prompt injection, data leakage, replay abuse), controls, and residual risks.

### 17.5 Observability

- Structured JSON logs (`structlog` or standard logging with a JSON formatter), with fields: `ts`, `level`, `event`, `decision_id`, `stage`, `outcome_category`, `duration_ms`, `model_id`, `ruleset_hash`. The `decision_id` is bound at the start of each request.
- Log the **category** of every result and every retry. Never log input values in `hash_only` mode, and never log API keys or full prompts.
- Metrics (Prometheus-style counters and histograms, optional): results by outcome, faults by stage, verifier failures by reason, LLM latency, retrieval latency, ledger append latency, chain length. Even if not scraped in the prototype, define them so the instrumentation points are clear.
- A `ledger_stats` view and `wageguard ledger show` support audit questions directly.
- A runbook entry in `docs/` for each fault class: symptoms, likely causes, actions.

### 17.6 Test plan

- API contract tests (status codes per category, auth failures, role enforcement, duplicate request handling) using the FastAPI test client with fakes at the composition root.
- A log test asserting that no seeded sentinel PII value appears in captured logs in `hash_only` mode.
- Exit-code contract tests for the CLI via subprocess.
- OpenAPI drift check.
- A test that no endpoint returns 2xx with a Fault body.
- SQL-injection style tests on any string input path (should all be rejected at validation or bound as parameters).

### 17.7 Acceptance criteria

- [ ] CLI and API share one service and produce identical results for the same input.
- [ ] Exit codes and HTTP statuses implement the documented contract.
- [ ] Role enforcement is tested for every endpoint.
- [ ] No sensitive values appear in logs (tested).
- [ ] `/readyz` fails if the ruleset or prompt hash verification fails.
- [ ] The threat model exists and lists residual risks honestly.

---

## 18. Phase 12: Documentation, ADRs, README, CV

> **Standards Reminder:** S-11 (documentation honesty), S-8 (ADRs), S-6 (claim-to-test mapping). The README is judged by a skeptical reader in five minutes. Lead with scope and limits.

### 18.1 README structure (in this order)

1. **One-paragraph description and the disclaimer.** Research and engineering prototype. Not legal advice. Not affiliated with any employer or vendor.
2. **Status table:** Implemented, Partially implemented, Not implemented, with the real state of every feature.
3. **Scope and non-scope:** exact checks, exact jurisdictions, exact date coverage, and everything unsupported and where it routes.
4. **Limitations (before features):** citation integrity versus semantic support; hosted-model nondeterminism; hash chain tamper-evidence only; small evaluation sample; source freshness (retrieval dates); rules not reviewed by counsel; no local ordinances; no multi-state or straddling periods.
5. **Questions for legal** (also in `docs/legal-questions.md`): the prominent, specific list of interpretations the system refuses to make, each tied to the reason code that escalates it.
6. **Architecture:** diagram plus a paragraph on each stage and the deterministic-core principle.
7. **Quickstart:** `make reproduce` and a worked example for a decision, an abstention, a legal-review case, and a fault.
8. **Data contract:** example input and output with field explanations.
9. **Audit record:** a real, annotated example ledger record, plus a `ledger verify` transcript and a replay transcript (`MATCH` and `DIFFERENT` with source-layer attribution).
10. **Evaluation:** the committed report's numbers with intervals, the baseline table, per-category breakdown, held-out discipline, and explicit caveats about sample size.
11. **Primary source register** (generated).
12. **Guarantees table:** each guarantee, its test, and its limits.
13. **Reproducibility:** pinned versions, what is and is not deterministic, and the cassette workflow.
14. **Security and privacy:** summary plus a link to the threat model.
15. **Design decisions:** links to the ADRs.
16. **Development:** standards summary, how to run each test tier, and how to contribute.

Tone: plain, specific, no hype. Numbers come from committed reports, not memory.

### 18.2 ADR set (write each in your own words)

0001 Deterministic rules decide, the LLM explains. 0002 Pydantic at boundaries, frozen dataclasses inside. 0003 Hermetic builds with uv. 0004 Four disjoint result categories. 0005 Decimal and quantization policy. 0006 Half-open effective ranges. 0007 Highest applicable rate controls (with source). 0008 Required evidence comes from the engine, not retrieval. 0009 Hard metadata filters before vector ranking. 0010 pgvector and index choice. 0011 Content-addressed immutable source versions. 0012 Hash-chained ledger and its limits. 0013 Canonicalization and versioning. 0014 Privacy modes. 0015 Replay semantics and what MATCH means. 0016 Cassette-based CI evaluation. 0017 Confidently-wrong rate as the headline metric, and undefined-rate handling. 0018 Wilson intervals and held-out discipline. 0019 Baseline design. 0020 Exemption: refusal to certify. 0021 No silent fallbacks. 0022 Evalforge boundary. Each has Context, Decision, Alternatives considered, Consequences.

### 18.3 CV integration (only after acceptance criteria pass)

Add the project only when the definition of done is met. Use exact, verified numbers:

> **WageGuard: Evidence-backed US Wage Compliance Screening** | Python, FastAPI, PostgreSQL, pgvector, Evalforge
> - Built a screening pipeline over `<N>` official DOL and state sources for `<J>` jurisdictions, with effective-dated rules as data, deterministic Decimal evaluation, and explicit abstention naming every missing input.
> - Implemented citation verification against run-specific retrieved passages and a hash-chained, append-only decision ledger with exact and fresh replay.
> - Evaluated on a `<N>`-case golden set (`<M>` held out) through Evalforge: confidently-wrong rate `<x/y>` (95% Wilson `<lo>` to `<hi>`) versus `<x2/y2>` for a plain LLM+RAG baseline; failure-injection suite covers `<K>` fault modes.

Replace every placeholder with a real number from the committed report. Remove any bullet that is not fully true. Do not claim legal review, production use, or compliance guarantees.

### 18.4 Interview preparation checklist

Be able to explain, without notes: why Decimal and half-open ranges; why retrieval filters before ranking; why required citations come from the engine; why abstentions skip the LLM; what the hash chain does and does not prove; why the headline metric is confidently-wrong rate and why it is undefined when nothing is answered; why the baseline might win some categories; why exemption `PASS` is nearly unreachable by design; what you would ask legal first; and what you would do to take this to production (real identity, retention, counsel-reviewed rulesets, external anchoring, monitoring, change control for rules).

### 18.5 Acceptance criteria

- [ ] Every guarantee in the README maps to a passing test marker.
- [ ] README numbers match the committed report (CI-checked).
- [ ] All 22 ADRs exist, each in your own words.
- [ ] A reviewer can run `make reproduce` from a clean clone and obtain the documented results from cassettes.
- [ ] No planned feature is described as implemented.

---

## 19. Appendices

### Appendix A. Reason codes (closed set; extend only with a test)

**Rejection (never an outcome):** `MALFORMED_JSON`, `UNKNOWN_FIELD`, `INVALID_TYPE`, `INVALID_DATE_FORMAT`, `INVALID_MONEY_FORMAT`, `NEGATIVE_OR_ZERO_AMOUNT`, `FIELD_TOO_LONG`.

**CANNOT_DETERMINE:** `MISSING_REQUIRED_FACT`, `INVALID_REQUIRED_FACT`, `AMBIGUOUS_REQUIRED_FACT`, `AMBIGUOUS_JURISDICTION`, `PAY_BASIS_NOT_COMPARABLE`, `EMPLOYER_SIZE_REQUIRED`, `NO_APPLICABLE_RULE_EVIDENCE`.

**NEEDS_LEGAL_REVIEW:** `OUT_OF_SCOPE_WORKER_CATEGORY`, `OUT_OF_SCOPE_JURISDICTION`, `DATE_OUTSIDE_RULE_COVERAGE`, `LOCAL_RULES_NOT_ENCODED`, `MULTI_STATE_WORK`, `PERIOD_STRADDLES_RULE_CHANGE`, `RULE_CONFLICT_UNRESOLVED`, `STATE_EXEMPTION_RULES_NOT_ENCODED`, `EXEMPT_DUTIES_NOT_EVALUATED`, `EXEMPT_NEEDS_HUMAN_CONFIRMATION`, `THRESHOLD_STATUS_UNCERTAIN`.

**Decision detail:** `MEETS_CONTROLLING_RATE`, `BELOW_CONTROLLING_RATE`, `STATE_RULE_ABSENT_FEDERAL_APPLIES`, `EXEMPT_SALARY_LEVEL_NOT_MET`, `EXEMPT_SALARY_BASIS_NOT_MET`, `EXEMPT_DUTIES_NOT_MET`.

**Fault categories:** `RETRIEVAL_UNAVAILABLE`, `SOURCE_VERSION_MISMATCH`, `EMBEDDING_MODEL_MISMATCH`, `LLM_TIMEOUT`, `LLM_MALFORMED_OUTPUT`, `LLM_REFUSED`, `CITATION_NOT_RETRIEVED`, `MISSING_REQUIRED_CITATION`, `QUOTE_MISMATCH`, `OUTCOME_CONTRADICTION`, `NUMERIC_DISAGREEMENT`, `UNCITED_CLAIM`, `LEDGER_APPEND_FAILED`, `CHAIN_BROKEN`, `CONFIGURATION_ERROR`, `MODEL_UNAVAILABLE`.

### Appendix B. Example input and response shapes

Input (synthetic):

```json
{
  "request_id": "synthetic-0001",
  "check_type": "minimum_wage",
  "record_ref": "SYN-EMP-0042",
  "work_state": "XX",
  "work_date": "2026-03-15",
  "pay_rate": "0.00",
  "pay_basis": "hourly",
  "worker_category": "general"
}
```

(`work_state` and `pay_rate` above are placeholders. Use real supported states and values only from your verified rule files.)

Response (decisive):

```json
{
  "decision_id": "<id>",
  "outcome": "FLAG",
  "reason_codes": ["BELOW_CONTROLLING_RATE"],
  "summary": "<verified explanation>",
  "controlling_rule": "<rule_id>",
  "ruleset_version": "<v>",
  "citations": [{"passage_id": "<id>", "source_url": "<url>", "quote": "<verified>"}],
  "missing_fields": [],
  "replayable": true
}
```

Response (abstention):

```json
{
  "decision_id": "<id>",
  "outcome": "CANNOT_DETERMINE",
  "reason_codes": ["MISSING_REQUIRED_FACT"],
  "missing_fields": ["pay_basis", "work_state"],
  "summary": "<templated explanation>",
  "citations": [],
  "replayable": true
}
```

Response (fault): HTTP 503 with `{"category": "fault", "stage": "...", "fault_code": "...", "decision_id": null_or_fault_record_id}` and **no** `outcome` field.

### Appendix C. Core DDL (illustrative; finalize in Alembic)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embedding_models (
  model_id    text PRIMARY KEY,
  dimension   integer NOT NULL CHECK (dimension > 0),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sources (
  source_key   text PRIMARY KEY,
  publisher    text NOT NULL,
  title        text NOT NULL,
  jurisdiction text NOT NULL,
  source_type  text NOT NULL CHECK (source_type IN
                 ('statute','regulation','agency_guidance','state_agency')),
  canonical_url text NOT NULL
);

CREATE TABLE source_versions (
  source_version_id bigserial PRIMARY KEY,
  source_key    text NOT NULL REFERENCES sources(source_key),
  version_no    integer NOT NULL CHECK (version_no >= 1),
  content_hash  char(64) NOT NULL,
  retrieved_at  timestamptz NOT NULL,
  http_status   integer,
  final_url     text,
  UNIQUE (source_key, version_no),
  UNIQUE (source_key, content_hash)
);

CREATE TABLE passages (
  passage_id        text PRIMARY KEY,           -- source_key@vN#pNNN
  source_version_id bigint NOT NULL REFERENCES source_versions(source_version_id),
  ordinal           integer NOT NULL,
  heading_path      text NOT NULL,
  text              text NOT NULL,
  normalized_text   text NOT NULL,
  content_hash      char(64) NOT NULL,
  chunker_version   text NOT NULL,
  topic             text NOT NULL,
  jurisdiction      text NOT NULL,
  embedding_model_id text NOT NULL REFERENCES embedding_models(model_id),
  embedding         vector NOT NULL,            -- dimension fixed per model; see ADR-0010
  UNIQUE (source_version_id, ordinal)
);
CREATE INDEX passages_filter_idx ON passages (jurisdiction, topic);

CREATE TABLE ledger_head (
  id            boolean PRIMARY KEY DEFAULT true CHECK (id),
  sequence_no   bigint NOT NULL,
  record_hash   char(64) NOT NULL
);

CREATE TABLE ledger (
  sequence_no   bigint PRIMARY KEY,
  decision_id   text NOT NULL UNIQUE,
  record_kind   text NOT NULL CHECK (record_kind IN
                  ('decision','abstention','fault','rejection','replay')),
  canon_version text NOT NULL,
  payload       jsonb NOT NULL,
  prev_hash     char(64) NOT NULL,
  record_hash   char(64) NOT NULL UNIQUE,
  created_at    timestamptz NOT NULL
);

CREATE FUNCTION ledger_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'ledger is append-only';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_no_update_delete
  BEFORE UPDATE OR DELETE ON ledger
  FOR EACH ROW EXECUTE FUNCTION ledger_immutable();

REVOKE UPDATE, DELETE, TRUNCATE ON ledger FROM wageguard_app;
```

Note: store the canonical bytes (or the exact canonical string) used for hashing alongside the `jsonb` payload, because `jsonb` does not preserve key order or number formatting and re-serializing from `jsonb` could change hashes. Prefer a `payload_canonical text` column that is the hashed source of truth.

### Appendix D. Canonicalization specification (`canon_v1`)

1. Input is a tree of: `dict[str, V]`, `list`/`tuple`, `str`, `int`, `Decimal`, `bool`, `None`, `date`, aware `datetime`, `Enum`.
2. **Reject** `float`, `set`, naive `datetime`, and non-string dict keys.
3. Strings: Unicode NFC. No other transformation.
4. `Decimal`: reject NaN/Infinity; emit `format(d.normalize(), 'f')` with `-0` normalized to `0`; documented examples: `1.50 -> "1.5"`, `1E+2 -> "100"`.
5. `date`: `YYYY-MM-DD`. `datetime`: converted to UTC, `YYYY-MM-DDTHH:MM:SS.ffffffZ`.
6. `Enum`: its `.value`.
7. Objects: keys sorted by Unicode code point; separators `,` and `:`; no whitespace; `ensure_ascii=False`; UTF-8 bytes.
8. `record_hash = SHA256(bytes.fromhex(prev_hash) || canonical_bytes)`.
9. Test vectors (committed as fixtures) with expected hashes, so any change to the canonicalizer fails loudly.

### Appendix E. Metrics reference

Definitions are in Section 14.3. Implementation notes: counts are integers; rates are computed as `Fraction` or `Decimal` and formatted at the edge; the Wilson function takes `(successes, trials, z)` and returns `(lo, hi)` as `Decimal`/`Fraction`, validated against reference values. Report the interval for every headline rate. Never report a rate without its denominator.

### Appendix F. `CLAUDE.md` (place at repo root)

```markdown
# Working rules for Claude Code in this repository

## Non-negotiables
- NEVER supply, recall, or guess a legal fact: wage rates, thresholds, effective
  dates, citations, or passage text. Those come only from files under data/ that
  a human fetched and reviewed. If a value is missing, STOP and ask.
- Money is Decimal. No floats in src/wageguard/compliance or src/wageguard/ledger.
- Outcomes are a closed sum type. Faults are never abstentions.
- No bare `except`. No `except Exception` except the single documented boundary.
- Domain code is pure: no I/O, no clock, no randomness, no env access. Inject ports.
- Do not add a dependency without asking. Do not edit the lockfile by hand.
- Do not edit prompts/ or data/rules/ files already released; create a new version.
- Do not edit data/snapshots/. They are content-addressed evidence.

## Workflow
- One phase at a time, per docs/SPEC.md. Do not start the next phase early.
- Tests first for phases 1, 2, 3, 6, 7: write the failing test, show it fails, then implement.
- Run `make lint types test` before declaring anything done. Report actual output.
- Small, atomic commits with imperative subjects and a why-body. Do not commit
  unless asked.

## Style
- Names from the domain. No utils/helpers/manager/common modules.
- Comments explain why, not what. No docstring boilerplate on trivial functions.
- Prefer deleting code to adding abstractions. No speculative generality.
- Follow the existing pattern; do not introduce a second way to do the same thing.
- No emoji, no hype wording in code, docs, or commit messages.

## Honesty
- Do not claim a feature works unless a test proves it. Do not mark a README
  guarantee as met without a linked test marker.
- If something is uncertain, say so and list it in docs/legal-questions.md.
```

### Appendix G. Claude Code prompt templates

**Phase kickoff:**
> Read docs/SPEC.md, section for Phase N, and CLAUDE.md. Summarize the Phase N acceptance criteria and list the files you will create. Do not write code yet. Wait for my confirmation.

**Tests-first step:**
> Write only the failing tests for <component> per the Phase N test plan. Run them and show the failure output. Do not implement anything.

**Implementation step:**
> Implement the minimum code to make these tests pass without changing the tests. Then run `make lint types test` and paste the real output. Flag anything you were tempted to add that the spec does not call for.

**Review step:**
> Review the diff as a skeptical senior engineer. List: unjustified abstractions, missing edge cases, any float or naive datetime, any swallowed exception, any comment that restates the code, any test asserting mock calls instead of behavior, and any claim without a test.

**Legal-fact guard:**
> I need the value for <rule>. Do not provide it. Tell me exactly which official source page and which passage I should read to find it, and what format the rule row expects.

### Appendix H. Pull request review checklist

- [ ] Tests were committed before implementation (where required) and fail without the change.
- [ ] No float, no naive datetime, no bare except, no new module-level state.
- [ ] No legal value in code; all rule changes are data with passage links and review status.
- [ ] Every new outcome path has a reason code, a template, and a test.
- [ ] Faults and abstentions remain distinct in types, logs, API, and exit codes.
- [ ] Tests assert behavior and persisted state, not mock calls.
- [ ] No new dependency without justification; lockfile updated by tooling.
- [ ] Architecture tests pass; import boundaries respected.
- [ ] Docs updated; any new guarantee registered with a test marker.
- [ ] Commit messages are atomic, imperative, and explain why.
- [ ] No comment merely restates the code; no template docstrings.
- [ ] A reviewer could explain every line without Claude Code's help.

### Appendix I. Definition of done (project level)

- [ ] All twelve phase acceptance lists are satisfied.
- [ ] `make reproduce` works from a clean clone with no network (snapshots + cassettes).
- [ ] `ledger verify` passes on the demo ledger, and the failing-tamper demo is documented.
- [ ] Golden report, baseline comparison, and held-out results are committed, with intervals.
- [ ] Evalforge regression demo is documented; Evalforge repo is free of domain vocabulary.
- [ ] Failure-injection matrix is fully automated.
- [ ] README leads with limits and legal questions; every guarantee maps to a test.
- [ ] CV bullets use real numbers; nothing planned is claimed as done.

### Appendix J. Suggested build order and rough sizing

| Order | Phase | Notes |
|---:|---|---|
| 1 | 0 Foundations | Guardrails first; resist writing domain code early |
| 2 | 1 Domain core | Small but sets every later invariant |
| 3 | 2 Intake and facts | Abstention is born here |
| 4 | 3 Rules and engine | Slowest part is sourcing and verifying real rule values |
| 5 | 4 Corpus and ingestion | Source review is manual and time-consuming |
| 6 | 5 Retrieval | Short once ingestion is solid |
| 7 | 6 Explainer and verifier | Adversarial tests are the bulk |
| 8 | 7 Ledger and replay | Careful about canonicalization and concurrency |
| 9 | 8 Evaluation | Labeling the golden set takes real thought; do not rush it |
| 10 | 9 Exemption screen | Reuses everything, which validates the architecture |
| 11 | 10 Failure injection | Mostly wiring faults through existing ports |
| 12 | 11 Interfaces and security | Thin, once the service is solid |
| 13 | 12 Documentation | Do the ADRs as you go, not at the end |

Write each ADR when its decision is made, not at the end. Reconstructed rationale reads as reconstructed.

---

*End of specification. Remember: every `VERIFY` is a gate. Nothing marked VERIFY enters a rule file until you have read the primary source and recorded the passage hash.*