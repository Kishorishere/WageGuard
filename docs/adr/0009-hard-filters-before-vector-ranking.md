# ADR-0009: Hard metadata filters before vector ranking

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Vector retrieval ranks by semantic similarity. Two passages that talk
about minimum wage in slightly different jurisdictions can embed very
close together — the embedding model does not know Washington from
Oregon unless the text happens to say so, and even then, "minimum
wage" is overwhelmingly the signal.

For a compliance screen, "close enough" is not acceptable. A Washington
rule passage returned for an Oregon query is not a slightly suboptimal
retrieval — it's a wrong-jurisdiction citation that could underpin a
confidently wrong explanation.

## Decision

Hard metadata filters are applied **before** vector ranking, not after.
Specifically, the retriever's `search(...)` restricts the candidate
set by:

- `jurisdiction IN applicable_set`
- `topic = requested_topic`
- source version is valid for the requested `as_of` date (once
  source-version validity windows ship)

Only within that filtered set does the retriever compute distances and
rank. In the SQL implementation this is one query whose `WHERE` clause
carries the filters; there is no post-rank Python filter. In the
in-memory implementation the candidate loop skips non-matching
`source_key`s before computing any distances.

Verified by:

- A unit test (G-09) that seeds a near-perfect textual match for a
  wrong-jurisdiction passage and asserts it is never returned.
- A contract test shared across in-memory and SQL implementations.
- An architecture note: `search` builds query text from check type +
  rule identifiers only (never user-supplied free text), shrinking the
  prompt-injection surface.

## Alternatives considered

- **Over-retrieve then post-filter in Python** — rejected. Any bug in
  the filter would silently leak wrong-jurisdiction hits past the
  verifier. SQL `WHERE` is auditable; post-filter is not.
- **Distance thresholding as the only filter** — rejected. Cosine
  distance across the embedding space does not track jurisdictions;
  a threshold tight enough to exclude a wrong state would also exclude
  genuinely relevant intra-jurisdiction passages.
- **Rely on prompt engineering** — rejected. "Please only cite
  Washington sources" is not a safety mechanism; the retriever has to
  make it structurally impossible.

## Consequences

- A passage from the wrong jurisdiction cannot be returned by the
  retriever, regardless of its similarity to the query (G-09).
- The retriever's query text is a controlled value: check type + rule
  identifiers. User input never reaches the embedder, eliminating
  injection via the embedding path.
- The SQL implementation uses parameterized queries; `pgvector`
  distance operators run against the pre-filtered set.
- The in-memory implementation produces byte-identical results given
  the same corpus and query, enabling deterministic replay.
