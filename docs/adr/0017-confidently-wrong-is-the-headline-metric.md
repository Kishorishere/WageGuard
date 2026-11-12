# ADR-0017: Confidently-wrong rate is the headline; undefined when nothing was answered

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

A screening system has two levers: how often it answers at all, and
how often its answers are wrong. The headline metric must capture the
cost of wrongness, not accuracy on cases the system chose to touch. A
system with 100% accuracy that abstains 95% of the time is not
"nearly perfect" — it's non-functional.

## Decision

The headline metric is **`confidently_wrong_rate`**, defined as

```
confidently_wrong_rate = CONFIDENTLY_WRONG / (CORRECT_DECISIVE + CONFIDENTLY_WRONG)
```

`CONFIDENTLY_WRONG` includes both

- a decisive outcome that disagrees with the labeled decisive outcome,
  **and**
- a decisive outcome when the label was an abstention. Emitting
  `PASS` / `FLAG` on a case that should route to legal review is
  worse than abstaining — it feeds the ledger with a confidently
  incorrect statement.

**When `non_abstained == 0`, the rate is reported as undefined, not
zero** (G-19). A system that abstains on everything has no business
looking clean on the headline; coverage and abstention rates tell
the real story.

Supporting metrics, always reported alongside their numerators,
denominators, and Wilson 95% intervals:

- `answerable_coverage = CORRECT_DECISIVE / answerable_cases`
- `correct_abstention_rate = CORRECT_ABSTENTION / should_abstain_cases`
- `over_abstention_rate = OVER_ABSTENTION / answerable_cases`
- `fault_count` (absolute; not a rate)
- `citation_integrity_rate` and `schema_valid_rate` (operational
  health, orthogonal to the headline).

## Alternatives considered

- **Overall accuracy** — rejected. Rewards a system for abstaining;
  obscures the cost of wrong decisive outcomes.
- **F1 on `FLAG`** — rejected. Compliance screening does not have a
  clean positive class; a precision/recall tradeoff would push the
  system toward the behaviour we specifically do not want.
- **"Is it ever wrong?" (boolean)** — rejected. With small samples,
  one wrong answer out of five looks catastrophic; one out of fifty
  looks safe. The Wilson interval is the honest conversation.

## Consequences

- Every rate is reported with `(x / n)` and a Wilson 95% interval
  (ADR-0018). Small samples produce wide intervals; the README says
  so and shows them.
- The scorer treats "answered when should have abstained" as
  confidently wrong — no soft-scoring that category.
- Faults are reported separately; they are infrastructure failures,
  not model/engine mistakes, and must not inflate or deflate any
  rate.
