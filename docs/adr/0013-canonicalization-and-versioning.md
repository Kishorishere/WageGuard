# ADR-0013: Canonicalization and versioning

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

The ledger hashes records. For hashes to be meaningful, the byte
sequence they operate on must be a canonical function of the record's
*content*, not its *representation*. Two records with the same facts
must serialize identically — regardless of the order their fields were
constructed in, whether `Decimal("1.5")` or `Decimal("1.50")` was
used, or whether a datetime was expressed in UTC or a local zone.

## Decision

Canonical serialization lives in `wageguard.ledger.canonical`,
version-tagged `canon_v1`. The rules:

1. **Floats are rejected at serialization time** (`ValueError`). Money
   is Decimal (ADR-0005); any float that reaches the ledger is a bug.
2. **Decimal** → fixed-places normalized string: `Decimal("1.5")` and
   `Decimal("1.50")` both serialize to `"1.5000"`. The number of
   places is defined by the canonical form (currently four).
3. **date** → ISO 8601 (`YYYY-MM-DD`); **datetime** must be timezone-
   aware and serializes as UTC RFC 3339 with microsecond precision
   (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). Naive datetimes are rejected.
4. **Enums** serialize by value (not name).
5. **Tuples and lists** serialize as JSON arrays; **sets and
   frozensets** are rejected (use a sorted tuple instead).
6. **Strings** are Unicode-normalized to NFC.
7. **`None`** serializes as explicit `null`. Absence and `null` are
   distinct at the schema level.
8. JSON output has **sorted keys, no insignificant whitespace, UTF-8**.
9. **Dataclasses** serialize via their fields in declaration order
   (which, combined with the key-sort rule, means field name drives
   hashing, not source-code position).

The canonical version is stored in every record's header. Verifying an
old record uses the same canonicalization version it was written with;
a `canon_v2` can ship alongside `canon_v1` so old records continue to
verify.

## Alternatives considered

- **Bencode / MsgPack** — rejected. Human readability in the ledger
  matters for audits; JSON wins. Canonicalized JSON is well understood.
- **Protocol Buffers** — rejected. Adds a code-generation step and a
  schema registry for marginal size savings; not worth the surface
  area at this scale.
- **Accept floats and round to a fixed precision** — rejected. Silent
  rounding is the class of bug Decimal exists to prevent (ADR-0005).

## Consequences

- Equivalent records hash equally; the hash is a content fingerprint,
  not a representation one. Property-tested.
- `canon_version` lets the canonicalization evolve without breaking
  old-record verification. Changing a rule requires a reviewed PR; the
  same discipline applies to the canonicalization itself.
- The implementation lives in a single file and is pure; mutation
  testing is feasible.
- `set` is forbidden so a reviewer can trust that element order in the
  hashed form is deterministic from the written code. Developers who
  want set semantics use a sorted tuple.
