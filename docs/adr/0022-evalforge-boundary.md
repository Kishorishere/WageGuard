# ADR-0022: Evalforge boundary stays domain-agnostic

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Evalforge is a generic evaluation harness: suite execution, schema
validation of outputs, latency and token cost, run-over-run
regression comparison. WageGuard is a domain-specific compliance
screener with its own case schema, scorer classifications, and
confidence-interval policy. Letting wage-law vocabulary leak into
Evalforge would tie the harness to one project and defeat the point
of a generic evaluator.

## Decision

WageGuard talks to Evalforge through a **thin, domain-agnostic
adapter** (`evaluation.evalforge_adapter`, lands with Phase 11+).

- Evalforge sees:
  - test-case IDs (opaque strings),
  - inputs and outputs as JSON blobs,
  - a pluggable scorer callable that returns a generic verdict.
- WageGuard keeps:
  - `GoldenCase` + `Split` + `ExpectedSpec` + `LabelBasis`
    (spec §14.2 vocabulary),
  - the Classification taxonomy and `classify()` table (spec §14.3),
  - the Wilson interval + "undefined when nothing was answered"
    policy (spec §14.4, ADR-0017, ADR-0018),
  - the baseline design (spec §14.6, forthcoming).

No module under the Evalforge repository path imports a compliance
or wage term. The `evalforge_adapter` module is the only place where
WageGuard and Evalforge meet; everything else stays on one side or
the other.

If Evalforge lacks a generic capability WageGuard needs, the pattern
is: **add it to Evalforge in a separate commit with its own tests
and no domain vocabulary**, then consume the released feature here.

Specifically-wanted generic Evalforge capabilities (spec §14.7):

- Prompt/model version metadata attached to runs.
- A generic "replay a stored run" interface.
- Pluggable custom scorers (we supply `classify()` as the callable).
- Regression comparison keyed on case IDs, stable across suite edits.

## Alternatives considered

- **Build a WageGuard-specific evaluator from scratch.** Faster
  initially; permanently coupled, and the Evalforge investment at
  the organisation gets zero leverage.
- **Fork Evalforge into WageGuard.** Rejected. Forks diverge; a
  domain-agnostic tool stays useful across teams only if its
  boundary is defended.
- **Let compliance terms into Evalforge "just for now".** Rejected.
  Every "just for now" exception is a permanent one.

## Consequences

- The adapter module is small and reviewed carefully; it is the
  single leak point between the two codebases.
- When WageGuard asks Evalforge for a new generic capability, the
  contribution lands in Evalforge with tests and docs that read
  as if WageGuard did not exist.
- The deliberate-regression demo (spec §14.7 Milestone 3) exercises
  Evalforge's run-over-run comparison on WageGuard cases without
  Evalforge needing to understand what a wage is.
- Cross-team adoption of Evalforge is unimpeded; nothing in the
  Evalforge code hints at a specific domain.
