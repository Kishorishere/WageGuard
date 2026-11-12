# ADR-0010: pgvector; exact-scan index for the prototype corpus

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Retrieval filters hard metadata before similarity (ADR-0009). Given
the filtered set is small (≤ a few hundred passages across three
jurisdictions), the choice of vector index matters less than the
correctness of the filter. But the choice has to be explicit so a
future reader knows when to switch.

## Decision

**pgvector on PostgreSQL, with an exact-scan query for the
prototype corpus.** No `IVFFlat` or `HNSW` index is created.

- The SQL query filters on `jurisdiction`, `topic`, and source-
  version validity in the `WHERE` clause (ADR-0009), then orders by
  `embedding <-> :query` cosine distance.
- For `N ≤ ~1000` passages, pgvector's exact scan is fast enough
  and introduces zero index tuning concerns.
- When the corpus grows past that, switch to `HNSW` first (it
  beats `IVFFlat` on recall at this scale; `IVFFlat` would be the
  choice if we were memory-constrained and had millions of
  vectors).

The in-memory retriever used in unit tests implements the same
contract (ADR-0009) with a Python loop; the shared contract test
suite enforces equivalence.

## Alternatives considered

- **Build an `HNSW` index from day one.** Index-build time, tuning
  (`m`, `ef_construction`, `ef_search`), and more runtime surface
  for little benefit at this scale. Rejected for now.
- **Use a dedicated vector DB (Qdrant, Weaviate, Milvus).** Adds a
  second storage system and its ops burden. The ledger and the
  corpus share a Postgres anyway; one database is simpler. Rejected.
- **Full-text search only (`tsvector`).** The corpus is small
  enough that TF-IDF would work. Semantic retrieval wins on recall
  for paraphrased queries; keep the embedder. Rejected.

## Consequences

- No index-build step; `make migrate` creates the table and the
  system is ready.
- Switching to `HNSW` later is a reviewed migration + a one-line
  change to the retriever's `ORDER BY` operator class. The in-
  memory retriever is unaffected.
- The SQL `SQLEvidenceRetriever` and Alembic migration are the
  deferred pieces that land with the real deployment (spec §10.7).
