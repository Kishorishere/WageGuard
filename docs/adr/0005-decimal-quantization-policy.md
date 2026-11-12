# ADR-0005: Decimal quantization policy for Money

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Compliance decisions turn on exact monetary comparisons. A minimum-wage
check that cannot distinguish `$15.24` from `$15.25` is useless: the
difference between PASS and FLAG routinely sits on that boundary.
Floats cannot represent most decimal fractions exactly; `0.1 + 0.2` is
`0.30000000000000004`, which is enough to flip an outcome. The ledger
also hashes money values as part of its tamper-evident record, so
equivalent values must serialize identically.

## Decision

1. **Money wraps `Decimal` only.** `Money.__init__` accepts `Decimal` or
   `str` and rejects `float` at runtime with a `TypeError` (G-01). An
   architecture test rejects `float` in annotations under
   `compliance/` and `ledger/` as a second line of defense.
2. **Full precision is preserved.** Arithmetic uses `Decimal`'s default
   precision (28 significant digits). No rounding before comparison.
3. **Canonical serialization uses a fixed number of places** (currently
   `4`, matching cent-plus-two-fractional-cents). `Money.to_canonical_string`
   quantizes to that many places and emits a non-scientific string, so
   `"1.5"`, `"1.50"`, and `"1.5000"` all serialize to `"1.5000"` and
   compare equal in the ledger hash. Round-tripping through this form
   is tested as a property (`test_money_properties.py`).
4. **Rounding happens only at defined presentation points**, and when
   it does, the mode is `ROUND_HALF_EVEN` (banker's rounding) — the
   Python default and the one that avoids systematic bias.

## Alternatives considered

- **Use `float` and tolerate epsilon** — rejected. Compliance cannot
  tolerate silent rounding; a one-cent shortfall must be detectable,
  and epsilon logic is exactly what makes bugs like "15.244999" sneak
  through comparisons.
- **Store as integer cents** — simpler, but loses expressive power for
  sub-cent precision needed by annualized rates and tax-adjacent math.
  `Decimal` with a fixed canonical places value gives the same safety
  with more headroom.
- **Round aggressively at construction** — rejected. The ledger becomes
  less faithful to the input, and bugs in rounding get baked into stored
  records that cannot be fixed without rewriting history.

## Consequences

- Money arithmetic is correct at any precision we care about in this
  project. The `one_cent_boundary` test is the canary; if it ever flakes,
  something upstream is lossy.
- The canonical form ties ledger hashes to a stable representation.
  Changing `_CANONICAL_PLACES` is a backwards-incompatible change that
  bumps the canonical-serialization version (`canon_v2` in future).
- `Decimal` is slower than `float`. For the volumes this prototype
  targets, the difference is immaterial; a real deployment that needs
  per-microsecond money math would use `Decimal` anyway for correctness
  and cache or precompute hot paths.
