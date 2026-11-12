"""Exemption salary-level screen (spec §15, Tier 3).

Narrow and conservative. The screen evaluates the salary-level +
salary-basis **necessary conditions** for exemption; it does NOT
certify exemption (ADR-0020). Default is `allow_certify_exemption=False`,
which makes `PASS` structurally unreachable (G-21). Duties are not
evaluated in the MVP; satisfying the necessary conditions routes to
`NEEDS_LEGAL_REVIEW` with the explicit reason
`EXEMPT_DUTIES_NOT_EVALUATED`.

`FLAG` here means **"the facts do not satisfy an encoded necessary
condition for exemption"** — NOT "this worker is non-exempt". The
templated explanation reflects that phrasing (spec §15.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from wageguard.compliance.rules import (
    Ambiguous,
    Found,
    NoRule,
    Rule,
    Ruleset,
    applicable_rule,
)
from wageguard.domain.enums import PayBasis, PayPeriod, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId
from wageguard.domain.jurisdiction import Jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import Flagged, NeedsLegalReview, Passed
from wageguard.domain.reason_codes import ReasonCode


@dataclass(frozen=True, slots=True)
class ExemptionSalaryFacts:
    work_state: Jurisdiction
    work_date: date
    salary_amount: Money
    pay_basis: PayBasis
    pay_period: PayPeriod
    worker_category: WorkerCategory
    current_exempt_status: bool


@dataclass(frozen=True, slots=True)
class ExemptionEngineResult:
    verdict: Passed | Flagged | NeedsLegalReview
    reason_codes: tuple[ReasonCode, ...]
    controlling_rule: Rule | None
    threshold_rate: Money | None
    salary_amount: Money
    required_passages: tuple[PassageId, ...]


def evaluate_exemption_salary(
    facts: ExemptionSalaryFacts,
    rules: Ruleset,
    *,
    federal_code: Jurisdiction,
    allow_certify_exemption: bool = False,
) -> ExemptionEngineResult:
    # 1. Resolve the applicable federal rule (state-specific thresholds
    #    land as STATE_EXEMPTION_RULES_NOT_ENCODED routes for MVP).
    federal_lookup = applicable_rule(
        rules,
        jurisdiction=federal_code,
        topic=Topic.EXEMPTION_SALARY_LEVEL,
        category=facts.worker_category,
        on=facts.work_date,
    )
    match federal_lookup:
        case Found(rule=threshold_rule):
            pass
        case NoRule():
            return _needs_legal_review(
                facts,
                controlling_rule=None,
                threshold_rate=None,
                reason_codes=(ReasonCode.DATE_OUTSIDE_RULE_COVERAGE,),
            )
        case Ambiguous(rules=amb):
            ids = ", ".join(str(r.rule_id) for r in amb)
            raise ConfigurationError(f"ambiguous exemption-salary rules: {ids}")

    threshold_rate = Money(threshold_rule.value)

    # 2. Salary-basis test. Hourly pay cannot clear a salary-basis
    #    requirement regardless of amount (spec §15.4).
    if facts.pay_basis is not PayBasis.SALARY:
        return _flag(
            facts,
            controlling_rule=threshold_rule,
            threshold_rate=threshold_rate,
            reason=ReasonCode.EXEMPT_SALARY_BASIS_NOT_MET,
        )

    # 3. Salary-level test. Exact Decimal comparison (ADR-0005).
    if facts.salary_amount < threshold_rate:
        return _flag(
            facts,
            controlling_rule=threshold_rule,
            threshold_rate=threshold_rate,
            reason=ReasonCode.EXEMPT_SALARY_LEVEL_NOT_MET,
        )

    # 4. State-specific thresholds (higher state exemption rules) are
    #    not encoded; the honest default is to route to legal review.
    #    This keeps the asymmetry: passing the federal necessary
    #    condition does NOT establish exemption.
    extra_reasons: list[ReasonCode] = [ReasonCode.EXEMPT_DUTIES_NOT_EVALUATED]
    if facts.work_state != federal_code:
        extra_reasons.append(ReasonCode.STATE_EXEMPTION_RULES_NOT_ENCODED)

    # 5. PASS is unreachable unless explicitly allowed. The system's
    #    defensible default is to refuse to certify exemption (G-21).
    if not allow_certify_exemption:
        return _needs_legal_review(
            facts,
            controlling_rule=threshold_rule,
            threshold_rate=threshold_rate,
            reason_codes=tuple(extra_reasons),
        )

    # If a caller explicitly opts in, we route to NEEDS_LEGAL_REVIEW
    # with EXEMPT_NEEDS_HUMAN_CONFIRMATION because duties are still not
    # evaluated. A future `allow_certify_exemption=True` path that
    # actually certifies would need an encoded duties facts graph and
    # a counsel-reviewable justification; see ADR-0020.
    extra_reasons.append(ReasonCode.EXEMPT_NEEDS_HUMAN_CONFIRMATION)
    return _needs_legal_review(
        facts,
        controlling_rule=threshold_rule,
        threshold_rate=threshold_rate,
        reason_codes=tuple(extra_reasons),
    )


def _flag(
    facts: ExemptionSalaryFacts,
    *,
    controlling_rule: Rule,
    threshold_rate: Money,
    reason: ReasonCode,
) -> ExemptionEngineResult:
    return ExemptionEngineResult(
        verdict=Flagged(),
        reason_codes=(reason,),
        controlling_rule=controlling_rule,
        threshold_rate=threshold_rate,
        salary_amount=facts.salary_amount,
        required_passages=controlling_rule.supporting_passages,
    )


def _needs_legal_review(
    facts: ExemptionSalaryFacts,
    *,
    controlling_rule: Rule | None,
    threshold_rate: Money | None,
    reason_codes: tuple[ReasonCode, ...],
) -> ExemptionEngineResult:
    required = controlling_rule.supporting_passages if controlling_rule is not None else ()
    return ExemptionEngineResult(
        verdict=NeedsLegalReview(reasons=reason_codes),
        reason_codes=reason_codes,
        controlling_rule=controlling_rule,
        threshold_rate=threshold_rate,
        salary_amount=facts.salary_amount,
        required_passages=required,
    )
