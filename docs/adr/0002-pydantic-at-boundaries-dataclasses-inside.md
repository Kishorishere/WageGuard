# ADR-0002: Pydantic at trust boundaries, frozen dataclasses inside

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Pydantic is excellent at the edge: it validates untrusted JSON into
typed values and surfaces field-level errors. It is heavy in the
middle of a pure domain: every field becomes a `FieldInfo`, dataclass
equality is replaced by Pydantic's rules, and serialization gets
tangled with hashing (ADR-0013 depends on being able to serialize
domain objects canonically ourselves).

## Decision

**Pydantic only at trust boundaries.** Specifically:

- `wageguard.intake.model.CheckRequestModel` (the untrusted-JSON
  boundary)
- `wageguard.llm.schemas.ExplanationDraft` (the untrusted-LLM-output
  boundary)
- The JSON schema of each is committed under `docs/schemas/` and
  diff-checked in CI

**Everywhere else, frozen dataclasses + `NewType` + `StrEnum`.** The
architecture test `test_forbidden_imports.py` enforces the rule:
`pydantic` is in the forbidden list for both `domain/` and
`compliance/`.

## Alternatives considered

- **Pydantic everywhere.** Uniform; expensive; obscures canonical
  serialization. Rejected.
- **Dataclasses everywhere; roll our own validation.** Lots of
  boilerplate at the edge; worse error messages than Pydantic.
  Rejected.
- **attrs + cattrs at the edge, dataclasses inside.** Adds a
  dependency without a clear win over Pydantic for this project's
  input shape. Rejected.

## Consequences

- The domain is unit-testable with zero third-party dependencies.
- Canonical serialization lives in `ledger.canonical` and operates
  on plain dataclasses + stdlib types — no Pydantic round-trip
  surprises for hashing.
- The trust boundary is obvious: if a type can be constructed from
  arbitrary JSON, it's a Pydantic model; if it can't, it's a
  dataclass. The architecture test holds this invariant.
