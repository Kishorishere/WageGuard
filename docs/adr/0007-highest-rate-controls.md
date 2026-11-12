# ADR-0007: The highest applicable minimum-wage rate controls

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

For a given worker, work location, and work date, more than one encoded
minimum-wage rule may apply simultaneously — typically the federal rule
plus a state rule. The engine must decide which rate to compare pay
against. Getting this wrong would either flag compliant employers
(state-above-federal case) or pass non-compliant ones (federal-above-state
case). The principle underlying the choice is a legal one, not an
engineering one, and it must be sourced before any real rule file is
trusted.

## Decision

When more than one encoded rule applies to the same `(work_location,
work_date, worker_category)`, the engine applies the **highest**
Decimal rate among the applicable rules. The winning row is recorded
as the `controlling_rule`; every applicable row is recorded as a
`candidate_rule` so the audit trail shows what was considered.

`VERIFY:` the DOL/statutory text establishing the federal floor and
that higher state rates apply must be fetched, stored as a passage in
`data/snapshots/`, and referenced from the rule rows'
`supporting_passages`. Until that source is captured and reviewed by a
human, every rule in `data/rules/**` carries
`review_status: not_reviewed_by_counsel` and the README says so.

If no state rule applies for a date in a supported state — the "no state
rule" path — the federal rule controls, with the reason code
`STATE_RULE_ABSENT_FEDERAL_APPLIES` recorded in the decision. The rule
file for that state must still exist (even if empty) so this path is
deliberate rather than silent.

If more than one rule shares a key and date (`Ambiguous` in the lookup
sum type), that is a ruleset defect: the engine raises
`ConfigurationError` rather than pick a winner. The loader's
overlap/gap validation (`Ruleset.from_rules`) blocks this at startup;
the engine's guard is defense in depth.

## Alternatives considered

- **Pick federal always** — rejected. It systematically under-protects
  workers in states with higher minimums and hides state-level rules
  from the audit trail entirely.
- **Pick state always** — rejected. It inverts the problem in states
  with no minimum or with a minimum below federal, and the "no state
  rule" case has no state value to pick.
- **Pick the most recent rule** — rejected. Recency doesn't model
  precedence here; a lower state rate enacted this year does not
  supersede a higher federal floor.
- **Expose the ambiguity to the caller** — rejected for the decisive
  path (would push a legal question onto an API consumer). Retained as
  the Ambiguous-and-fail case when the ruleset itself is defective.

## Consequences

- The engine's correctness does not depend on the real rate values —
  it depends on `max`. The synthetic TESTLAND-A/B rulesets in Phase 3
  tests exercise every path (state-above, state-below, no-state)
  without any real figures.
- The audit payload (`candidate_rules`, `controlling_rule`,
  `controlling_rate`, `actual_rate`, `shortfall`) is enough to replay
  a decision end-to-end without re-running the engine.
- The legal principle is real-world sourced; the ADR records where the
  source lives and when it was last reviewed. A rule row whose
  controlling passage is missing or hash-mismatched is a Fault
  (`SourceVersionMismatch`) at retrieval time, not a silent downgrade.
