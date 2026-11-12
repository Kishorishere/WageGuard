# ADR-0011: Content-addressed immutable source versions

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Compliance decisions cite official passages. A decision from six months
ago must still resolve to the *exact* text that was retrieved at the
time, even if the agency has since rewritten the page. If a source
version can be mutated in place, old decisions silently become
undefensible: the citation is the same, the words beneath it are not.

## Decision

Sources are ingested as **content-addressed, immutable source versions**.

- Each fetched snapshot is stored at
  `data/snapshots/<sha256>.<ext>` — the filename *is* the hash of the
  bytes. Two snapshots with identical content are the same file.
- A `SourceVersion` record ties `(source_key, version_no, content_hash,
  retrieved_at)` together. `version_no` is monotonically increasing
  per source; old versions are never modified or deleted.
- Re-ingestion of unchanged content records a `"verified unchanged"`
  event. The content hash on disk is recomputed and compared to the
  expected one — any mismatch is `EvidenceError`, not a silent reset.
- Re-ingestion of changed content creates a **new** `SourceVersion`
  with a new `version_no`. The old passages remain queryable; a rule
  that referenced the old version continues to resolve.
- Passages carry their own content hash (SHA-256 of the normalized
  passage text) so a corrupted passage row is detectable independently
  of the source-file hash.

Pointer files (`<source_key>.current`) record which content hash is the
latest snapshot for a source. Only the pointer moves when a new version
lands; the content-addressed file beneath never changes.

## Alternatives considered

- **Keep one snapshot per source and overwrite** — rejected. Breaks
  replay of old decisions and makes "did the source change?" an
  unanswerable question.
- **Keep snapshots keyed by retrieval timestamp** — rejected. Two
  identical re-fetches would create two files for the same bytes,
  wasting storage and inviting bugs where equivalent content hashes
  differently. Content addressing makes this impossible by construction.
- **Delete old versions after N days** — rejected for the prototype
  (and documented as a real-deployment concern in the README retention
  note). Without a counsel-reviewed retention policy, deleting evidence
  of past decisions is a defensibility hazard.

## Consequences

- Replay of any logged decision can reconstruct the exact evidence,
  byte-for-byte, as long as its content hashes are present.
- Tampering with a stored snapshot is evident: reading the file
  recomputes the hash and raises on mismatch (G-08). A privileged actor
  could rewrite both the file and its pointer, so this is
  tamper-**evident**, not tamper-proof; external anchoring (ADR-0012)
  mitigates the rewrite class.
- Pure chunker + canonical hashes make `make reproduce` genuinely
  reproducible from a clean checkout and committed snapshots.
- Storage grows monotonically. For the scale of this prototype
  (`N ≤ 10` sources, each ≤ 1 MiB) that is immaterial; a real
  deployment would need a vetted retention workflow.
