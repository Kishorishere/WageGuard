# Questions for legal

This file lists interpretations WageGuard **refuses to make**. Each row
ties to the reason code that escalates the case to `NEEDS_LEGAL_REVIEW`
and names the ADR or spec section that justifies the refusal.

The list is a load-bearing honesty document: a reviewer can see exactly
which legal calls the system defers and why.

| Reason code | Interpretation we refuse | Justification |
|-------------|--------------------------|---------------|
| `LOCAL_RULES_NOT_ENCODED` | How to apply a city or county minimum-wage ordinance that is more protective than state law | Local ordinances are not encoded in the ruleset. Spec §9.6, ADR-0007. |
| `PERIOD_STRADDLES_RULE_CHANGE` | How to handle a pay period that spans a rule-change date | The MVP evaluates a single `work_date`; splitting across a boundary is a legal judgement, not a split-by-days arithmetic. Spec §9.6. |
| `OUT_OF_SCOPE_WORKER_CATEGORY` | Whether tipped, youth, student, apprentice, learner, or disabled workers meet the general-category minimum | Each category has a different statutory scheme the MVP does not encode. Spec §9.6. |
| `OUT_OF_SCOPE_JURISDICTION` | How a state we have not encoded applies federal law | Only the jurisdictions the ruleset lists are supported; everything else escalates. Spec §9.2, §9.6. |
| `STATE_EXEMPTION_RULES_NOT_ENCODED` | Whether a state imposes a higher exemption-salary threshold than federal | State exemption variations are not encoded; `allow_certify_exemption` remains false. ADR-0020. |
| `EXEMPT_DUTIES_NOT_EVALUATED` | Whether a worker satisfies the exemption **duties** test | The MVP encodes only salary-level and salary-basis (necessary conditions); duties are judgement-laden. ADR-0020. |
| `EXEMPT_NEEDS_HUMAN_CONFIRMATION` | Whether all necessary and sufficient conditions for an exemption are met | Opt-in path; still routes to legal review because duties are not encoded. ADR-0020. |
| `THRESHOLD_STATUS_UNCERTAIN` | Whether a salary threshold subject to litigation or injunction is in force on the work date | The ruleset records the status; the engine refuses when it reads `uncertain`. Spec §15.2. |
| `DATE_OUTSIDE_RULE_COVERAGE` | Which rule applies on a date outside every encoded effective range | No applicable rule means the engine cannot decide; the audit trail says which range is missing. Spec §8.5. |
| `STATE_RULE_ABSENT_FEDERAL_APPLIES` | *(decisive)* The federal rate controls when a state has no minimum-wage law of its own | This is a **decisive** outcome, not an abstention. Listed here for completeness so a reviewer can see the no-state path is deliberate. ADR-0007. |

## What the exemption screen **does not** evaluate

- The duties test for any exemption category (executive,
  administrative, professional, outside sales, computer-employee).
- Fluctuating workweek arrangements.
- Highly-compensated-employee tests when the salary-level and
  duties tests have category-specific interactions.
- State-level exemption thresholds and salary-basis rules different
  from federal.
- Any question about whether a worker's job title accurately reflects
  the worker's duties.

## What the minimum-wage engine **does not** evaluate

- Tipped-worker minimum (tip credits, dual-job rules).
- Youth, student, learner, or apprentice minimum.
- Overtime, including fluctuating workweek and compensatory time.
- Industry-specific rates (agriculture, ski resorts, seasonal).
- Employer-size-dependent state thresholds without the size fact.
- Any question about whether the worker is an employee or an
  independent contractor.

## How to extend this list

1. Add the reason code in `src/wageguard/domain/reason_codes.py`.
2. Add a row here naming the interpretation refused and the ADR or
   spec section that justifies the refusal.
3. Add a test that exercises the new reason code end-to-end.
4. No new ADR is required if the refusal mirrors an existing one;
   write a new ADR only when the decision changes the surface area
   (for example, moving from refuse-to-certify to a counsel-reviewed
   certification path).
