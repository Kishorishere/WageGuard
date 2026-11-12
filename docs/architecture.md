# Architecture

```text
CLI / API
   |
Intake ........ parse -> validate -> normalize            (reject malformed)
   |
Scope guard ... supported jurisdiction / date / worker category?   (else NEEDS_LEGAL_REVIEW)
   |
Required-facts resolver ... PRESENT / MISSING / INVALID / AMBIGUOUS  (else CANNOT_DETERMINE)
   |
Jurisdiction resolver ... applicable rules for (location, work_date)
   |
Rule engine ... pure functions, Decimal money, effective-dated rules -> Outcome
   |
Evidence retriever ... hard filter (jurisdiction, topic, date) then pgvector rank
   |
Explainer (LLM) ... structured output, may cite only supplied passage IDs
   |
Verifier ... schema, citation integrity, quote match, outcome consistency
   |
Ledger ... append-only, hash-chained, content-addressed evidence
   |
Result + decision_id
```

## Properties that must hold

1. **The engine decides the outcome before the LLM is called.** The LLM
   receives the outcome as a fixed input and writes only an explanation.
2. **The verifier can veto but never upgrade.** A verification failure
   is a Fault, never a fallback decision.
3. **Abstentions skip the LLM where possible.** Templated from reason
   codes; deterministic, free, and removes a hallucination surface.
4. **The ledger write is the commit point.** No `decision_id` is
   returned until a durable record exists.

See `compliance-project.md` for the authoritative specification and
`docs/adr/` for the decisions behind each property.
