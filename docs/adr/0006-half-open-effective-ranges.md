# ADR-0006: Half-open effective ranges `[start, end)`

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Compliance rules change on a date. A minimum-wage rate set on
`2024-07-01` replaces the previous rate; a worker paid on `2024-07-01`
must be evaluated against the new rate, not the old one. We need a
range semantics that

- makes consecutive rules tile without gaps,
- makes every date belong to exactly one rule, and
- is unambiguous at the boundary where human intuition is weakest
  ("is the new rule effective ON July 1, or the day AFTER?").

Off-by-one bugs on effective dates are a classic compliance footgun.

## Decision

`EffectiveRange(start, end)` represents the half-open interval
`[start, end)`. That is:

- `start` is **inclusive**: the rule takes effect on `start`.
- `end` is **exclusive**: the rule does not apply on `end`. If `end` is
  `None`, the range is open on the right.
- `end <= start` is invalid; the constructor raises.

As a consequence (G-02), **two adjacent ranges never overlap**:
`[Jan 1, Jul 1)` and `[Jul 1, Dec 31)` share no date; `Jul 1` belongs
only to the second. Rule files declare a new rule by setting its
`effective_from` to the effective date and the predecessor's
`effective_to` to the same date.

## Alternatives considered

- **Closed-closed `[start, end]`** — rejected. Adjacent rules either
  overlap on the boundary (ambiguous) or leave a one-day gap
  (unanswered). Either case is a bug waiting to happen.
- **Closed-open with `end` inclusive-by-convention** — the same bug as
  above, dressed differently.
- **Half-open on the other side `(start, end]`** — equivalent
  mathematically, but every spec and SQL dialect we interact with reads
  `[start, end)` more naturally (SQL `BETWEEN` notwithstanding, which is
  closed-closed and should not be used here).

## Consequences

- Load-time validation catches overlapping and zero-length ranges
  immediately. A rule row with `effective_to <= effective_from` fails
  the load.
- The comparison `work_date in range` is a two-sided check with
  `None` on the right handled explicitly. The engine never applies a
  rule outside its range.
- Documentation and error messages must repeat the convention
  prominently, because "half-open" is the kind of convention that feels
  obvious when you know it and invisible when you don't.
