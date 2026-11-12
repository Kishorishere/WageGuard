# ADR-0008: Required evidence comes from the engine, not from retrieval

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

A compliance decision has to cite the passages that justify it. Two
sources of citations are available:

1. The **engine**, which produced the outcome, knows exactly which
   rule rows it consulted. Each rule carries its `supporting_passages`;
   if a decision rests on that rule, the passage is required.
2. The **retriever**, which can return passages similar to a query
   string. Its candidate set depends on the embedding model, the
   corpus, and the query phrasing.

If the explainer's cited passages were drawn only from retrieval, a
decision would be defensible iff the retriever happened to surface the
rule's supporting passages. On a bad day — a thin corpus, an unlucky
query, a retriever bug — the explanation would cite a tangentially
related paragraph and the decision would look sourced without being
grounded.

## Decision

**The engine dictates the required passages.** The `evaluate_minimum_wage`
function (and every future check) returns `required_passages` on its
`EngineResult`; those IDs flow into `fetch_required(...)` by id, not by
similarity. The retriever's `search(...)` is used only for
*supplemental* context, bounded by `k` and `max_distance`.

The `EvidenceBundle` holds both:

- `required: tuple[Passage, ...]` — engine-ordered, deduplicated.
- `supplemental: tuple[ScoredPassage, ...]` — similarity hits, excluding
  anything already in `required`.

The verifier (Phase 6) enforces that every passage the engine marked
required appears in at least one citation of the final explanation.
If any required id is missing from the store, `fetch_required` raises
`EvidenceError` and the run becomes a Fault — the system does not
emit a decisive outcome with incomplete evidence.

## Alternatives considered

- **Retrieval-only citations** — rejected. Explanations become hostage
  to retrieval quality for the correctness of a decision; weak corpus
  coverage silently degrades defensibility.
- **Engine-only citations, no retrieval** — rejected. Supplemental
  context is useful for the explanation's clarity; it just must never
  be mistaken for the evidentiary basis of the outcome.
- **Rank and prune required passages by distance** — rejected. The
  engine already named them; downgrading or dropping a required passage
  because similarity is low would silently weaken the audit trail.

## Consequences

- Required ids trace from a rule's YAML row directly into the ledger's
  `required_passages` field. A changed rule → changed required set →
  changed ruleset hash; replay can detect the drift.
- The retriever cannot "accidentally" degrade a decision: missing a
  required passage is a Fault with a clear reason code.
- Supplemental hits are decoration, not evidence. The verifier is free
  to accept or ignore them; the engine never depends on them.
