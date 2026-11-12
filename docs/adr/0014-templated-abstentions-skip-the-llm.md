# ADR-0014: Templated abstentions skip the LLM

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Abstentions (`CannotDetermine`, `NeedsLegalReview`) already carry
machine-readable reason codes and the names of every offending field
(Phase 2). An LLM asked to "explain why we can't decide" would
paraphrase those reasons at best and invent context at worst — a
hallucination surface the system has no reason to expose.

## Decision

Abstention outcomes are explained by **a deterministic template built
from the reason codes and field names**. No LLM call is made. This
is enforced by passing a `FakeClient(raises_if_called=True)` into
abstention paths in tests (G-12), proving at the type/behaviour level
that the LLM is never reached.

Decisive outcomes (`Passed` / `Flagged`) still route through the
explainer → verifier pipeline because they need cited prose. The
templated-abstention path is the cheap, deterministic, free, and
hallucination-free branch; use it whenever it applies.

## Alternatives considered

- **Use the LLM for abstentions too, for consistent tone** —
  rejected. Tone is not worth a hallucination surface in the defensive
  path of the system.
- **Templated decisive outcomes** — rejected. Decisive explanations
  need to weave in citations and quotes from actual retrieved passages;
  templates there would be sterile and brittle.

## Consequences

- Abstention latency is sub-millisecond; abstention cost is zero.
- The ledger record for an abstention records no `model_id`,
  `prompt_hash`, or `usage` — those fields are nullable and
  legitimately empty on this path.
- Templates live in `src/wageguard/verification/templates.py` and derive
  from `wageguard.domain.reason_codes.template_of`. Adding a new reason
  code adds a new template automatically (the domain test ensures every
  code has one).
