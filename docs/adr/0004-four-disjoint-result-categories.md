# ADR-0004: Four disjoint result categories

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Compliance systems routinely conflate "I don't know" with "something
broke" — both end up looking like degraded answers to downstream
consumers. A network timeout comes back as "cannot determine", the
alerting system treats it as a normal abstention, and nobody pages.
Separately, a malformed input and a complete but inconclusive input
have very different downstream actions: one needs correction, the
other needs more facts.

## Decision

Four **disjoint** result categories, implemented as separate types
in `wageguard.domain`:

1. **Decision** — `Passed` | `Flagged`. A decisive outcome that
   entered the ledger as a `DECISION` record.
2. **Abstention** — `CannotDetermine(reasons, fields)` |
   `NeedsLegalReview(reasons)`. Honest "I won't decide, here's why"
   with machine-readable reason codes and field names.
3. **Rejection** — `InputRejected` (exception). Structurally
   malformed input; no decision outcome, logged as a `REJECTION`
   record.
4. **Fault** — `EvidenceError` / `LlmError` / `VerificationFailed`
   / `LedgerError` subtrees. Infrastructure failure; logged as a
   `FAULT` record (best effort) and distinguishable from everything
   above (G-03).

The CLI exit code contract and HTTP status contract map 1-to-1 to
these categories (spec §17.2, §17.3; G-24). The scorer's
`Classification` enum (`evaluation.scoring`) keeps `FAULT` separate
from every rate denominator so an outage never inflates or deflates
accuracy numbers.

## Alternatives considered

- **Unified "result" sum type including faults as outcomes.** Easier
  to pattern-match on; silently teaches downstream code to treat
  infrastructure failures as abstentions. Rejected.
- **Exception-based abstentions.** Conflates control flow and data;
  harder to serialise and test. Rejected.
- **`Optional[Outcome]` with `None` for "no answer".** Erases the
  reason for the no-answer. Rejected.

## Consequences

- Downstream logic uses exhaustive `match` with `assert_never`;
  adding a variant breaks every unhandled case under `mypy --strict`.
- The scorer treats "decisive when abstention expected" as
  `CONFIDENTLY_WRONG`, not as a soft-scored middle ground
  (ADR-0017).
- The ledger carries `record_kind` on every row; replay paths know
  not to re-run a rejection as if it were a decision (spec §13.7).
- Operators get honest signals: `fault_count` is not an accuracy
  number, and a rise in it means the infrastructure is unhappy.
