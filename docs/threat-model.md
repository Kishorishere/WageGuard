# Threat model

A short, honest inventory. The project is a prototype; real deployment
hardening is deliberately out of scope and listed under Residual risks.

## Assets

- **Ledger integrity.** Decisions, abstentions, and faults are
  append-only and chained; a reviewer six months from now can trust
  what the record says (ADR-0012, ADR-0013). Losing or silently
  mutating a record invalidates the audit.
- **Evidence integrity.** Source snapshots are content-addressed with
  SHA-256; passages carry their own content hash (ADR-0011). Silent
  rewrites are detectable at load.
- **Rule integrity.** Rules are versioned data with a canonical hash
  recorded on every decision (ADR-0005). A changed rule means a new
  ruleset hash; the ledger shows the change.
- **Input privacy.** All inputs in this project are synthetic. In
  `hash_only` privacy mode the ledger stores an input hash plus fact
  statuses, not the raw values (spec §13.6).

## Actors

- **Checker** — creates checks via the CLI or `POST /v1/checks`.
- **Auditor** — reads decisions, verifies the ledger via
  `GET /v1/decisions/{id}` and `ledger verify`.
- **Admin** — anchors the ledger head, runs replay.
- **Operator** — infrastructure role with DB access. Not represented
  as an API role; DBA-level changes are out-of-band and auditable at
  the database level.

## Threats and controls

| Threat | Control | Evidence |
|---|---|---|
| Ledger row rewrite by a privileged actor | Chain linkage + `ledger verify` + external anchoring (ADR-0012). Tamper-evident, not tamper-impossible. | G-15 bite-test |
| Append-only bypass via `UPDATE` / `DELETE` | DB role granted `INSERT` / `SELECT` only; `BEFORE UPDATE OR DELETE` trigger raises. | Deployment-time GRANTs (deferred) |
| Chain fork by concurrent writers | Single-row `ledger_head` locked `FOR UPDATE` in SQL; threading `RLock` in in-memory impl. | G-16 (8×4 threaded property test) |
| Evidence poisoning via rewritten snapshot | Content-addressed file + hash verification at read (G-8). | `test_snapshot.py::test_read_detects_tampered_bytes` |
| Wrong-jurisdiction passage returned by retrieval | Hard metadata filter in SQL `WHERE` / in-memory pre-rank skip; adversarial test (G-9). | `test_retrieval.py::test_wrong_jurisdiction_never_returned` |
| Fabricated or superseded citations | Verifier checks citation existence against *this run's* evidence bundle; required citations come from the engine (G-10). | 12 adversarial tests (spec §12.7) |
| Prompt injection via passage text | Passage text delimited as `<passage_text_begin>...<passage_text_end>`; verifier treats passage text as data; the retriever text is built from controlled fields only (ADR-0009). | `test_retrieval.py::test_query_text_is_controlled_not_free_form` |
| Model refusal / downtime routed to a weaker fallback | **No silent fallbacks** (ADR-0021). The system fails closed; the ledger records a fault, not a degraded decision. | `test_fault_matrix.py` rows 5–9 |
| API key leakage via log | `hash_only` privacy mode redacts raw model output; the API-key compare is constant-time; authorization required on every non-health endpoint. | FastAPI `Depends(_auth)` + `hmac.compare_digest` |
| Privileged exfil of synthetic inputs | `hash_only` mode stores `input_hash` + fact statuses only; raw inputs are not persisted. | Phase 13.6 config |

## Residual risks (prototype)

- **No SQL migration or DB GRANTs yet.** The in-memory ledger is
  hard-coded in the composition root. A real deployment would wire
  `SQLLedgerRepository` and run the Alembic migration that creates
  the single-row `ledger_head` + append-only trigger.
- **No head anchoring service.** `wageguard ledger anchor` is a CLI
  stub; a real deployment would either (a) commit the head hash to
  a signed git tag on a periodic schedule, or (b) send it to an
  external timestamping service.
- **No authn beyond API keys.** Real deployment integrates with a
  real identity provider (OIDC, mTLS).
- **No prompt-injection guarantees.** The corpus is trusted-official
  content; a compromised source could still poison explanations,
  which the content-hash + human-review of rule-supporting passages
  mitigates but does not eliminate.
- **No PII handling policy.** All inputs are synthetic; `hash_only`
  mode is scaffolded but not legally reviewed.
- **No retention workflow.** The ledger grows unbounded; a real
  deployment needs a counsel-reviewed retention policy.

## Out of scope

Supply-chain security of our dependencies (handled by `pip-audit` +
`gitleaks`), DoS protection (handled by a real deployment's load
balancer), physical security (handled by the hosting provider),
insider threats beyond "tamper-evident, not tamper-impossible"
(mitigated only by anchoring).
