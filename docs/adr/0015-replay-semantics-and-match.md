# ADR-0015: Replay semantics; what "MATCH" means

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Replay is a load-bearing audit feature. A reviewer asks "if we
re-ran decision X today, do we get the same answer?" The honest
answer has three shapes (`MATCH`, `DIFFERENT`, `CANNOT_REPLAY`),
and the definition of `MATCH` has to be precise — especially for
decisive outcomes whose explanation prose comes from a hosted LLM
that is nondeterministic even at temperature 0.

## Decision

Two replay modes with distinct semantics:

**Exact mode** reconstructs the decision from stored artifacts and
compares.

- The stored ruleset, passages, and prompt are loaded by hash. Any
  hash mismatch is `CANNOT_REPLAY` with the specific reason.
- For engine-only outcomes (no LLM involved — abstentions and
  future decisive paths with templated explanations), replay is
  byte-identical on canonical serialization (G-17). This is the
  strongest `MATCH`.
- For LLM-involved outcomes, the comparison is on the **decisive
  fields**: `asserted_outcome`, `reason_codes`, `controlling_rule`,
  the citation set. These must match. If they match but the
  explanation prose differs, the result is
  `MATCH_WITH_TEXT_VARIATION` (not `DIFFERENT`); the README says
  so plainly.
- Replay writes a new `REPLAY` record linked via `replay_of`. The
  original is never mutated (G-18).

**Fresh mode** re-evaluates against the **current** corpus and
ruleset. A layered diff names which layer changed:

- `input` differs (shouldn't happen if the input hash matches),
- `ruleset` differs (ruleset_hash changed),
- `source` differs (a passage's content hash changed),
- `prompt` differs,
- `model` differs,
- `output` differs (decisive fields disagree).

The caller sees exactly which layer moved.

## Alternatives considered

- **Byte-identical only; everything else is DIFFERENT.** Punishes
  the system for an LLM wording change the audit doesn't care
  about. Rejected.
- **Compare only the asserted outcome.** Loses the "did the
  citations stay the same" check which is the audit's real
  question. Rejected.
- **Re-run the LLM and compare top-1 similarity.** Flaky; easy to
  argue about; depends on the embedder. Rejected.

## Consequences

- Replay is a useful tool, not a tautology. `MATCH` means "the
  decisive content is the same"; `MATCH_WITH_TEXT_VARIATION` is an
  honest acknowledgement that hosted-model nondeterminism exists.
- The caller gets precise information about which layer drifted,
  so investigations start at the right place.
- Phase 7 ships exact replay for engine-only outcomes
  (`replay_exact`). The LLM-involved + fresh-mode variants land
  with the full composition root's SQL store.
