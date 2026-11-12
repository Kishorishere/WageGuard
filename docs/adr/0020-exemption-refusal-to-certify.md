# ADR-0020: Exemption screen refuses to certify

- **Status:** accepted
- **Date:** 2026-11-12
- **Deciders:** WageGuard engineering

## Context

Exemption from minimum wage and overtime under the FLSA depends on
both a pay test (salary level + salary basis) and a duties test, with
details varying by exemption category. The duties test turns on
judgment-laden questions — "exercises discretion and independent
judgment", "primary duty is management of the enterprise". An
automated system cannot responsibly resolve those.

The asymmetry matters: failing a necessary condition (salary level)
is enough to say the exemption screen does not support the exempt
classification. Passing a necessary condition proves **nothing** about
the sufficient set. Salary level alone cannot establish exemption.

## Decision

The exemption-salary engine implements the pay tests
(salary-level + salary-basis) and **refuses to certify exemption**.

- Failing the salary-basis test (hourly pay) → `FLAG` with
  `EXEMPT_SALARY_BASIS_NOT_MET`.
- Failing the salary-level test (salary below the threshold) → `FLAG`
  with `EXEMPT_SALARY_LEVEL_NOT_MET`.
- Meeting both necessary conditions → **`NEEDS_LEGAL_REVIEW`** with
  `EXEMPT_DUTIES_NOT_EVALUATED` (plus
  `STATE_EXEMPTION_RULES_NOT_ENCODED` when the worker's state differs
  from federal). Never `PASS`.
- A `current_exempt_status: true` flag supplied by the employer is
  **treated as an assertion, not as evidence**. It does not override
  the necessary-condition checks.
- A caller can `allow_certify_exemption=True` to opt in to a future
  certification path; today that still routes to `NEEDS_LEGAL_REVIEW`
  with `EXEMPT_NEEDS_HUMAN_CONFIRMATION`, because the duties facts
  graph is not encoded. The property test (G-21) uses the default
  `False` to prove `PASS` is structurally unreachable.

## Alternatives considered

- **Certify exemption when both necessary conditions are met** —
  rejected. It would misrepresent sufficient conditions as having
  been checked; that is exactly the "confidently wrong" class of
  failure the system exists to avoid.
- **Encode a duties test from statute text** — rejected for the MVP.
  The judgment-laden phrases ("discretion and independent judgment")
  are not automatable without a counsel-reviewed rubric; the screen
  would silently encode one engineer's interpretation.
- **Return the raw facts and let the caller decide** — rejected. The
  caller asked for a compliance screen; "here are the facts" is not
  a screen.

## Consequences

- The meaning of `FLAG` on this check is carefully phrased in the
  explanation template: *"the facts do not satisfy the encoded
  necessary condition for the exemption"* — not "this worker is
  non-exempt". The templated explanation never states a legal
  classification conclusion.
- `PASS` is unreachable in the current build (G-21, property-tested
  with 200+ hypothesis examples across hourly/salary and every
  salary amount from \$0.00 to \$10,000.00).
- If a future version adds a duties facts graph and a counsel-
  reviewed path to certification, this ADR is superseded with a new
  decision record that lists the specific duties criteria and the
  reviewing counsel.
- The README states what this screen **does not** evaluate (spec
  §15.7 acceptance criterion).
