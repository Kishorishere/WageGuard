# ADR-0019: Baseline design — plain LLM + RAG on the same corpus

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

The headline metric (confidently-wrong rate, ADR-0017) has no
meaning without a baseline. A reviewer will ask "but how does this
compare to just asking the model?" and the answer has to be
specific, same-dataset, and fair — otherwise it's a strawman.

## Decision

Build `evaluation.baseline` — a deliberately plain
**"LLM + RAG answers directly"** pipeline on the same corpus and
the same model:

- Retrieve top-k passages for the query (naive: no hard metadata
  filter beyond the topic).
- Ask the model to decide `PASS` / `FLAG` / `CANNOT_DETERMINE`
  with citations.
- No deterministic engine; no required-facts graph; no verifier.
- Same prompt pattern (passage text delimited as data), same
  model id, temperature 0.

Treat the baseline **fairly**:

- Same model id as the main system. Not a weaker model.
- Same corpus. Not a thin subset.
- A sensible prompt. Not a strawman "please guess".
- Same cassette workflow for CI determinism (ADR-0016).

Run both pipelines on the **same golden set** and publish a
side-by-side table in the golden report:

- Confidently-wrong rate (with Wilson 95% intervals, ADR-0018),
- Coverage,
- Correct abstention rate,
- Citation integrity.

Break the results down **by category** (threshold boundary,
missing field, state conflict, out-of-scope, ...). The architecture's
value shows most clearly in the abstention, boundary, and conflict
categories; be honest when the baseline wins on easy categories.

## Alternatives considered

- **No baseline.** Report WageGuard's numbers alone; the reader has
  no comparison. Rejected.
- **Compare against a weaker model.** Makes WageGuard look good by
  handicapping the baseline. Rejected on principle.
- **Compare against a "blind" model with no retrieval.** Too easy
  to beat; not a credible point of comparison. Rejected.

## Consequences

- The evaluation report answers "is the architecture doing work
  the model alone wouldn't?" with specific numbers in specific
  categories.
- A future improvement to the main system is validated by
  improving on the same-dataset baseline, not by improving on
  itself.
- Baseline runs use the same `evalforge_adapter` and cassette
  mechanism (ADR-0022, ADR-0016). The baseline lands with the
  full composition root when the real corpus is ingested.
