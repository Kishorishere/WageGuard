# ADR-0001: Deterministic rules decide, the LLM explains

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

A compliance screening system has to be defensible to a reviewer who
is going to ask, in effect, "why is this answer right?". If the
outcome itself is produced by a language model, the honest answer is
"the model said so" plus a probability. That is not a defence.

## Decision

**The engine decides the outcome before the LLM is called.** The
outcome is a function of the validated facts and the versioned
ruleset — pure Python, Decimal math, no model in the loop. The LLM
receives the outcome as a fixed input and writes a plain-language,
cited *explanation*. It cannot change the outcome.

- `evaluate_minimum_wage` and `evaluate_exemption_salary` are pure
  functions returning an `EngineResult` whose `verdict` is the
  decision.
- `build_llm_request` / `explain_decision` embed the engine's
  `asserted_outcome` in the prompt. The prompt instructs the model
  to *explain*, not decide, and the verifier enforces it.
- The verifier rejects any explanation whose `asserted_outcome`
  disagrees with the engine's (G-11).

## Alternatives considered

- **Model decides end-to-end.** Fastest to build, undefensible under
  audit, and the headline metric (confidently-wrong rate) would be
  bounded by whatever the model gives us. Rejected.
- **Model decides, rules check post-hoc.** Still surfaces the model
  as the primary decider; failures look like overrides, which invite
  arguments. Rejected.
- **Rules decide, no LLM at all.** Clean, but the system's
  explanations become template prose — fine for abstentions, weak
  for decisive outcomes that benefit from citation-weaving. Hybrid is
  better.

## Consequences

- The ledger records `verdict` from the engine and the LLM's prose
  as separate fields. Replay of engine-only decisions is byte-
  identical (G-17); explanation drift is reported separately
  (ADR-0015).
- A verifier failure never "falls back" to an unverified decisive
  outcome (ADR-0021).
- The LLM is a bounded surface: constrained prompt, structured
  output schema, verifier gate. If the LLM is down, decisive
  outcomes fail closed; abstentions (templated, ADR-0014) still
  resolve.
