# ADR-0021: No silent fallbacks

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

When a component fails mid-pipeline, there is a tempting shortcut:
degrade the behaviour "gracefully" — fall back to a cheaper model,
skip verification if it's slow, cache the last answer, return a
default. Those are the behaviours that let a compliance system
quietly stop meeting its evidence requirement while continuing to
emit confidently-looking decisions.

## Decision

**No silent fallbacks.** Every failure surfaces as a `Fault` with a
specific reason code; a `Fault` is never a `Decision` or an
`Abstention`. Specifically:

- **No fallback model.** If the pinned model is unavailable, the run
  is a Fault. There is no "try the cheaper model" path.
- **No skip-verification.** If the verifier times out or crashes,
  the run is a Fault. There is no "accept the explanation if the
  verifier is slow" path.
- **No cached answer.** The ledger is append-only and not a
  response cache. A new request re-runs the whole pipeline.
- **No default outcome on error.** If retrieval fails, the engine
  does not "assume PASS" or any other value; the caller gets a
  Fault.
- **No synthetic evidence.** If a required passage is missing,
  the engine does not retrieve something similar instead; the run
  is a Fault (`EvidenceError` / `SourceVersionMismatch`).

Retries are bounded and scoped:

- Retries fire ONLY for whitelisted idempotent transport errors
  (e.g. `LlmTimeout` from a dropped TCP connection). The policy is
  codified in `resilience.retry.RetryPolicy`; `retry_on` is explicit.
- `VerificationFailed`, `LlmMalformedOutput`, and any validation
  error class **never** retries. Retrying a verification failure
  would be an invitation to drift.
- Every retry has a hard attempt cap AND a total time budget. The
  property test `test_does_not_retry_non_whitelisted_errors` pins
  this with a fake clock.

Graceful degradation applies ONLY to explanation, never to the
decision:

- If the LLM is down and the outcome is a decisive `PASS` / `FLAG`,
  the system returns a Fault. An unexplained decisive outcome does
  not meet the evidence requirement.
- Abstentions, by contrast, use the templated path (ADR-0014) and
  do not require the LLM at all; a down LLM does not affect them.

## Alternatives considered

- **Fallback model when the primary is overloaded** — rejected. The
  decision's defensibility depends on the exact model id in the
  ledger; a silent switch would make replay lie.
- **Cache last-known-good decision** — rejected. The ledger is the
  record, not the cache. A re-asked question deserves a re-answered
  decision through the real pipeline.
- **Open-loop retry on verifier failures** — rejected. If the
  verifier rejects an explanation, a retry is unlikely to succeed
  on the same input; worse, it hides the structural problem in the
  explainer's output.

## Consequences

- Every fault class in the matrix (spec §16.2) has a dedicated
  test that it never produces a `DECISION` record (G-22).
- The resilience layer stays small: one retry policy, one bounded
  budget, one Clock port. No fallback orchestration graph.
- Operators get honest signals from the ledger: a rise in
  `fault_count` means "the infrastructure is unhappy", not "the
  system got a little less confident today."
- Reviewers can audit any decisive outcome and know, by
  construction, that the explainer and verifier both ran to
  completion on the recorded model, prompt, and evidence.
