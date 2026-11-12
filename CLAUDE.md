# CLAUDE.md — Rules for the AI pair programmer on this repo

Read this file before editing any code in this repository. These rules
exist to protect the project's defensibility. Violations are review
failures regardless of who wrote them.

---

## 1. Claude Code never supplies a legal fact

Wage figures, salary thresholds, effective dates, statutory citations,
and the exact text of any quoted passage **must** come from official
sources that a human fetched and reviewed. If a task needs a number or
a date Claude Code does not have in hand (via an ingested snapshot or
rule file the human prepared), **stop and ask**.

Hard rules:

- Never invent a wage rate, a threshold, or an effective date.
- Never copy a legal figure from this specification document
  (`compliance-project.md`) — it is a design document, not a source.
- Every value in `data/rules/**` traces to a passage in `data/snapshots/**`
  that a human confirmed. The `supporting_passages` field is not optional.
- `VERIFY:` markers in code or docs are tasks for the human. Do not
  "resolve" them by filling in a value from memory.

---

## 2. Provider-agnostic LLM port

WageGuard does **not** depend on any specific LLM vendor SDK. The
`LlmClient` port lives in `src/wageguard/llm/port.py` and development
adapters are **Gemini** and **Groq** only (user directive). Specifically:

- Do not `pip install` or `import` the `anthropic` or `openai` packages.
  The architecture test `tests/architecture/test_forbidden_imports.py`
  fails CI if either appears anywhere under `src/`.
- Any client the spec document refers to as `AnthropicClient` is a
  placeholder name; the real implementations are `GeminiClient` and
  `GroqClient`, both behind the same `Protocol`.
- Prompts are written to be model-agnostic: no provider-specific
  system-prompt tags, no model-specific tool-calling schemas.

---

## 3. Docker images build in GitHub Actions

Local `docker compose` runs only Postgres+pgvector for development. The
application container image is built by `.github/workflows/docker.yaml`.
Do not add an `app:` service to `compose.yaml` and do not tell a user to
run `docker compose build` — that is a review failure.

Running the app locally during development: `uv run wageguard <cmd>`.

---

## 4. Tests-first phases

Phases **1, 2, 3, 6, 7** are tests-first. The failing test commit lands
before the implementation commit; `git log` on the branch shows the red
commit preceding the green one. In those phases, do not write a line of
implementation without the failing test already in place.

---

## 5. Four disjoint result categories

`Decision` (PASS/FLAG), `Abstention` (CANNOT_DETERMINE / NEEDS_LEGAL_REVIEW),
`Rejection` (malformed input), and `Fault` (infrastructure) are **not** the
same type. A `Fault` must never be constructible as an `Abstention`. If you
find yourself tempted to collapse them "for convenience," re-read §3.1 and
§4.1 of `compliance-project.md`.

---

## 6. Money is `Decimal`; datetimes are timezone-aware

The architecture tests reject:

- `float` annotations under `src/wageguard/compliance/` or
  `src/wageguard/ledger/`;
- `datetime.utcnow()`, `datetime.utcfromtimestamp()`, and any `datetime(...)`
  / `datetime.now()` / `datetime.fromtimestamp()` call without a tz argument
  anywhere under `src/`.

Rounding: full precision is preserved; rounding happens only at defined
presentation points. Compare as `Decimal`, never as `float`. A one-cent
shortfall must be detectable.

---

## 7. Dependency direction

`domain/` depends on the standard library only. `compliance/` depends on
`domain/` and the standard library only. Neither imports `sqlalchemy`,
`fastapi`, `httpx`, `pgvector`, `pydantic`, or anything under
`wageguard.llm`, `wageguard.evidence`, or `wageguard.interfaces`.

Enforced in `tests/architecture/test_forbidden_imports.py`.

---

## 8. Every README guarantee maps to a test

Guarantees live in `docs/guarantees.md`. An Active guarantee without a
matching `@pytest.mark.guarantee("G-NN")` test fails `make docs-check`.
Moving a guarantee from Planned to Active is a PR that also lands the
owning test, in the same commit.

---

## 9. ADRs for non-obvious decisions

If a choice is not obvious from reading the code, it needs an ADR in
`docs/adr/NNNN-title.md` using the template. Write the ADR in your own
words; copying the spec document is not an ADR.

---

## 10. Small commits, honest commit messages

- Imperative subject under 72 characters.
- Prefix with `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, or `chore:`.
- The body says *why*, not *what*.
- No "fix typo" chains; squash locally first.
- Never commit secrets, real worker data, or generated noise.
- Attribution footer (per harness instructions):
  `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.

---

## 11. When in doubt, stop and ask

The point of this project is defensibility under uncertainty. Silent
guesses break that. If a required fact is missing, a source is unclear,
a threshold has been litigated, or a test seems to depend on luck —
stop and ask.
