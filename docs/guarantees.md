# Guarantees

Every README claim about WageGuard's behaviour lives here first. A row in
**Active** is a build constraint: `scripts/check_guarantees.py` fails CI if

1. a guarantee listed as Active has no test marked `@pytest.mark.guarantee("G-NN")`;
2. a test is marked with a guarantee ID that is not Active;
3. the ID format is not `G-NN` (zero-padded, two digits).

A guarantee under **Planned** names a future contract. It is not enforced
until it is moved into Active together with the owning test, in the same PR.

The README copies rows out of this file. `make docs-check` runs the script.

---

## Active

| ID | Guarantee | Owning test marker |
|----|-----------|--------------------|
| G-01 | Money uses `Decimal`; constructing `Money` from `float` raises. | `tests/unit/domain/test_money.py::TestConstruction::test_float_rejection_is_a_guarantee` |
| G-02 | `EffectiveRange` is half-open `[start, end)`; adjacent ranges never overlap. | `tests/unit/domain/test_ranges.py::TestOverlap::test_adjacent_ranges_do_not_overlap` |
| G-03 | Decision / Abstention / Rejection / Fault are disjoint types; no fault is representable as an abstention. | `tests/unit/domain/test_outcomes.py::TestDisjointFromFault::test_fault_types_are_not_outcome_types` |
| G-04 | Intake rejects unknown fields (`extra="forbid"`) and distinguishes MISSING / INVALID / AMBIGUOUS. | `tests/unit/intake/test_model.py::TestExtraForbid::test_unknown_fields_rejected` |
| G-05 | `CANNOT_DETERMINE` always names every missing / invalid / ambiguous field at once. | `tests/unit/compliance/test_facts.py::TestMultipleOffendersReportedAtOnce::test_resolver_reports_all_missing_fields` |
| G-06 | No legal value (wage rate, salary threshold) is hard-coded in `src/`. | `tests/architecture/test_no_legal_values_in_src.py::test_no_wage_shaped_decimal_literal_under_src` |
| G-08 | Corpus ingestion is deterministic: identical snapshot bytes produce identical passage IDs. | `tests/unit/evidence/test_chunking.py::TestDeterminism::test_same_bytes_produce_identical_passages` |
| G-09 | Retrieval applies jurisdiction/topic/date filters **before** ranking; a wrong-jurisdiction passage cannot be returned. | `tests/unit/evidence/test_retrieval.py::TestHardFiltersBeforeRanking::test_wrong_jurisdiction_never_returned` |
| G-10 | Required citations come from the engine, not from retrieval. | `tests/unit/evidence/test_retrieval.py::TestBundle::test_required_passages_lead_the_bundle` |

---

## Planned

These are promises the specification makes. Each will become Active in the
phase that implements and tests it.

| ID | Guarantee | Target phase |
|----|-----------|--------------|
| G-07 | The highest applicable rate controls; this is sourced from an official passage. | Phase 3 (engine) + Phase 4 (sourcing) |
| G-11 | The verifier can veto but never upgrade; no decisive outcome reaches the ledger without passing every verifier check. | Phase 6 |
| G-12 | Abstentions emit templated explanations with no LLM call. | Phase 6 |
| G-13 | The prompt hash is verified against the registry at startup. | Phase 6 |
| G-14 | Every decision, abstention, and fault is appended to a hash-chained ledger; the application role cannot UPDATE or DELETE ledger rows. | Phase 7 |
| G-15 | `ledger verify` detects any single-byte tamper and reports the first break. | Phase 7 |
| G-16 | Concurrent appends never fork the chain. | Phase 7 |
| G-17 | Exact replay of engine-only outcomes is byte-identical to the original record. | Phase 7 |
| G-18 | Replay writes a new record; the original is never mutated. | Phase 7 |
| G-19 | Golden metrics are reported with numerators, denominators, and Wilson 95% intervals; `non_abstained == 0` is reported as undefined, not zero. | Phase 8 |
| G-20 | The held-out split is not read by any tuning script; every held-out run is logged. | Phase 8 |
| G-21 | Exemption `PASS` is unreachable without the documented conditions (property-tested). | Phase 9 |
| G-22 | Every row of the fault matrix produces a Fault record and no decision record. | Phase 10 |
| G-23 | The CLI and API share one service and return identical results for the same input. | Phase 11 |
| G-24 | API returns a 2xx response only when a ledger record exists; a 503 names the fault stage. | Phase 11 |
| G-25 | `/readyz` fails when the ruleset or prompt hash verification fails. | Phase 11 |
| G-26 | `make reproduce` from a clean clone builds the env, migrates, ingests from committed snapshots, and runs the golden suite offline. | Phase 12 |
