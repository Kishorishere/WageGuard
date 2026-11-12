# ADR-0012: Hash-chained ledger and its limits

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Compliance decisions need an audit trail that is auditable *after* the
fact: a reviewer six months from now must be able to say, with evidence,
"this decision was made with this rule content, these passages, and
this prompt, on this date, and no one has edited it since." A plain
database table does not clear that bar — an operator with write access
can rewrite history and leave no trace.

## Decision

Every completed check — decision, abstention, fault, rejection, replay —
is **appended** to a single hash-chained ledger. Each record stores a
`prev_hash` that points at the previous record's `record_hash`; its own
`record_hash` is SHA-256 over the canonical serialization of
`{header, body, prev_hash}` (ADR-0013). `verify_chain` walks the
sequence, recomputing each hash and comparing linkage; any mismatch
is reported with the sequence index of the first break (G-15).

Append-only enforcement is layered:

1. **Compute-then-lock discipline in the application.** `append()`
   acquires an append lock, reads the current head, computes the new
   hash, inserts, releases the lock. `InMemoryLedgerRepository` uses a
   threading `RLock`; the SQL adapter uses `SELECT ... FOR UPDATE` on a
   single-row `ledger_head` table. Concurrent writers produce a linear
   chain with no forks (G-16, property-tested with eight threads x four
   appends each).
2. **Database privileges** (deployment-time): the application role has
   `INSERT` and `SELECT` on the ledger table only; `UPDATE`, `DELETE`,
   and `TRUNCATE` are revoked.
3. **Trigger** (defense in depth): a `BEFORE UPDATE OR DELETE` trigger
   raises; even a privileged mistake fails loudly.

## Alternatives considered

- **Mutable table with a "last_modified" column** — rejected. Trivially
  rewritable; no evidence of change.
- **Append-only table without chaining** — rejected. Detects row
  deletion but not row rewrites.
- **Full external anchoring on every record** — rejected for the
  prototype. A single network call per decision changes latency and
  failure semantics. The compromise: `ledger anchor` periodically
  exports the head hash to an external store (git tag, timestamping
  service) so a rewrite of the whole chain would conflict with the
  anchor.

## Honest limits

**This is tamper-evident, not tamper-impossible.** A privileged actor
with sufficient access can rewrite the entire chain *consistently* —
new hashes, new linkage, new content — and the chain will verify
cleanly. The mitigations are external:

- **Head anchoring** (`ledger anchor`) commits the current head hash
  to a place the application cannot rewrite (a signed git tag, an
  external timestamping service). A whole-chain rewrite now conflicts
  with the anchor, which is evidence.
- **Database privilege separation**: the application role cannot
  `UPDATE`, `DELETE`, or `TRUNCATE`. Only a DBA-level role can, and
  that operation is auditable at the database level.
- **Trigger** at the DB level catches privileged mistakes.

The README states these limits plainly.

## Consequences

- Append throughput is bounded by the single-writer lock. For the
  volumes this project targets (hundreds of checks a day), the
  tradeoff is immaterial; a real high-throughput deployment would
  shard by `(jurisdiction, topic)` and run one chain per shard.
- Every record stores `canon_version` (ADR-0013) so a future
  canonicalization change does not invalidate old records.
- The ledger write is the **commit point**: no `decision_id` is
  returned to the caller until the append has durably committed. A
  response without a durable record is a defect, not a feature.
