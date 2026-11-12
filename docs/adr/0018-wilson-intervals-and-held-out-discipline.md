# ADR-0018: Wilson 95% intervals and held-out split discipline

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

With a golden set of 40 cases — or any sample small enough to show a
reviewer in one screen — point estimates lie. A point estimate of
`0/20` for confidently-wrong rate is compatible with a true rate of
15%+ at 95% confidence. The report must make the uncertainty
visible, not hide it behind a bold-faced "0.00%".

Separately, if we tune the system against the golden set, those cases
stop measuring generalisation and start measuring overfit. A **held-
out** split that the tuner never reads is the standard mitigation.

## Decision

1. **Wilson 95% intervals accompany every rate.** The implementation
   is pure (`evaluation.intervals.wilson_score_interval`),
   unit-tested against reference values from `statsmodels`, and
   handles `x = 0`, `x = n`, `n = 0`, and `n = 1` without collapsing
   to zero width.
2. **A single `z` constant** (`Z_95 = 1.959963984540054`) is pinned;
   changing the confidence level is a reviewed PR.
3. **The split is in each case file** (`split: "dev" | "heldout"`).
   Moving a case between splits is a reviewed PR; the split integrity
   check (`check_split_integrity`) blocks accidental duplication at
   docs-check time (G-20).
4. **Tuning scripts never read the held-out directory.** The check is
   enforced structurally (held-out loader lives in a separate
   function and is wired only into the reporter), and a grep-based
   `scripts/check_cases.py` would additionally fail CI if any script
   under `scripts/` references the string `heldout` outside of a
   documented docstring (follow-up).
5. **Every held-out run is logged.** The golden reporter records a
   row in `reports/heldout-runs.log` each time it reads held-out
   cases, so repeated "peeking" is visible in a diff.

## Alternatives considered

- **Bootstrap intervals** — rejected for the headline. Non-closed
  form, more code surface, and the audit would ask "which sampler,
  which seed, which n_bootstrap?" The Wilson formula is a one-liner
  with zero hyperparameters.
- **Bayesian credible intervals with a chosen prior** — rejected for
  the prototype; defensible but adds a prior to defend. If a reviewer
  wants Beta credibles later, they drop in.
- **No held-out split, iterate against all cases** — rejected on the
  face of it. The whole point of the system is defensibility; a
  non-held-out evaluation is a marketing number.

## Consequences

- Reports show every rate as `(x / n) ± Wilson 95% [lo, hi]`. Point
  estimates never appear alone.
- The system is honest about small-sample caveats; the README leads
  with "intervals are wide because the sample is small; here is
  exactly how wide."
- `make golden` produces a report; the committed `reports/*.json`
  is the source of truth for README numbers (spec §14.8); CI
  cross-checks the README copy against the committed report.
- A case that is moved between splits must be done in a PR; the PR
  author must argue why the move does not re-introduce overfit.
