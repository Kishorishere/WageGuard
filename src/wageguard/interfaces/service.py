"""CheckService — single entry point shared by CLI and API.

Threads intake, scope, facts, engine, and ledger. Decisive outcomes
go on to retrieval, explainer, and verifier before the ledger write
(wired at composition when an LlmClient is present). Faults append a
fault record (best effort) and never emit a decision.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wageguard.compliance.checks.exemption_salary import (
    ExemptionSalaryFacts,
    evaluate_exemption_salary,
)
from wageguard.compliance.checks.minimum_wage import (
    MinimumWageFacts,
    evaluate_minimum_wage,
)
from wageguard.compliance.facts import (
    RawFacts,
    exemption_salary_facts,
    minimum_wage_facts,
    resolve,
)
from wageguard.compliance.rules import Ruleset
from wageguard.compliance.scope import evaluate_scope
from wageguard.config import PrivacyMode
from wageguard.domain.enums import CheckType, PayBasis, PayPeriod, WorkerCategory
from wageguard.domain.errors import (
    ConfigurationError,
    InputRejected,
    LedgerError,
    WageGuardError,
)
from wageguard.domain.fields import FieldName
from wageguard.domain.identifiers import DecisionId, RulesetVersion
from wageguard.domain.jurisdiction import Jurisdiction
from wageguard.domain.money import Money
from wageguard.domain.outcomes import (
    CannotDetermine,
    Flagged,
    NeedsLegalReview,
    Outcome,
    Passed,
)
from wageguard.intake.parser import parse_check_request
from wageguard.ledger.ledger import append as ledger_append
from wageguard.ledger.records import PartialHeader, RecordKind
from wageguard.ledger.repository import LedgerRepository
from wageguard.resilience.clock import Clock


class ResultCategory(StrEnum):
    DECISION = "decision"
    ABSTENTION = "abstention"
    REJECTION = "rejection"
    FAULT = "fault"


class IdGenerator(Protocol):
    def __call__(self) -> DecisionId: ...


@dataclass(frozen=True, slots=True)
class CheckResponse:
    category: ResultCategory
    decision_id: DecisionId | None
    outcome: Outcome | None
    detail: str
    fault_stage: str | None = None


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    rules: Ruleset
    supported_jurisdictions: frozenset[str]
    federal_code: Jurisdiction
    app_version: str
    git_commit: str
    privacy_mode: PrivacyMode = PrivacyMode.SYNTHETIC


# Fault stage vocabulary — spec-named; `_emit_fault` enforces membership.
_VALID_FAULT_STAGES: frozenset[str] = frozenset(
    {"evidence", "llm", "verification", "ledger", "engine"}
)


def _to_exemption_salary_facts(raw_facts: RawFacts) -> ExemptionSalaryFacts | str:
    v = raw_facts.values
    salary = v.get(FieldName.SALARY_AMOUNT)
    work_state = v.get(FieldName.WORK_STATE)
    work_date = v.get(FieldName.WORK_DATE)
    pay_basis = v.get(FieldName.PAY_BASIS)
    pay_period = v.get(FieldName.PAY_PERIOD)
    worker_category = v.get(FieldName.WORKER_CATEGORY)
    current_exempt = v.get(FieldName.CURRENT_EXEMPT_STATUS)
    if not isinstance(salary, Decimal):
        return f"salary_amount must be Decimal, got {type(salary).__name__}"
    if not isinstance(work_state, str):
        return f"work_state must be str, got {type(work_state).__name__}"
    if not isinstance(work_date, date):
        return f"work_date must be date, got {type(work_date).__name__}"
    if not isinstance(pay_basis, PayBasis):
        return f"pay_basis must be PayBasis, got {type(pay_basis).__name__}"
    if not isinstance(pay_period, PayPeriod):
        return f"pay_period must be PayPeriod, got {type(pay_period).__name__}"
    if not isinstance(worker_category, WorkerCategory):
        return f"worker_category must be WorkerCategory, got {type(worker_category).__name__}"
    if not isinstance(current_exempt, bool):
        return f"current_exempt_status must be bool, got {type(current_exempt).__name__}"
    return ExemptionSalaryFacts(
        work_state=Jurisdiction(work_state),
        work_date=work_date,
        salary_amount=Money(salary),
        pay_basis=pay_basis,
        pay_period=pay_period,
        worker_category=worker_category,
        current_exempt_status=current_exempt,
    )


def _to_minimum_wage_facts(raw_facts: RawFacts) -> MinimumWageFacts | str:
    """Convert RawFacts into a typed MinimumWageFacts.

    Returns the typed facts on success, or a string describing why
    conversion failed. Callers route failures through `_emit_fault`
    at the engine stage — this is not an abstention, it is an
    unexpected internal shape (the resolver already approved the
    values; a type mismatch means the Pydantic model and the engine
    types drifted).
    """
    values = raw_facts.values
    pay_rate = values.get(FieldName.PAY_RATE)
    work_state = values.get(FieldName.WORK_STATE)
    work_date = values.get(FieldName.WORK_DATE)
    pay_basis = values.get(FieldName.PAY_BASIS)
    worker_category = values.get(FieldName.WORKER_CATEGORY)
    if not isinstance(pay_rate, Decimal):
        return f"pay_rate must be Decimal, got {type(pay_rate).__name__}"
    if not isinstance(work_state, str):
        return f"work_state must be str, got {type(work_state).__name__}"
    if not isinstance(work_date, date):
        return f"work_date must be date, got {type(work_date).__name__}"
    if not isinstance(pay_basis, PayBasis):
        return f"pay_basis must be PayBasis, got {type(pay_basis).__name__}"
    if not isinstance(worker_category, WorkerCategory):
        return f"worker_category must be WorkerCategory, got {type(worker_category).__name__}"
    return MinimumWageFacts(
        work_state=Jurisdiction(work_state),
        work_date=work_date,
        pay_rate=Money(pay_rate),
        pay_basis=pay_basis,
        worker_category=worker_category,
    )


def _input_fingerprint(raw_json: str, privacy_mode: PrivacyMode) -> Mapping[str, object]:
    """Build the input portion of the ledger body per privacy mode."""
    input_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    # Use `==` (not `is`) because Pydantic Settings may deliver either
    # the enum member or its underlying string value.
    if privacy_mode == PrivacyMode.HASH_ONLY:
        return {"input_hash": input_hash}
    try:
        snapshot = json.loads(raw_json)
    except json.JSONDecodeError:
        snapshot = None
    return {"input_hash": input_hash, "input_snapshot": snapshot}


class CheckService:
    def __init__(
        self,
        *,
        config: ServiceConfig,
        ledger_repo: LedgerRepository,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._config = config
        self._ledger = ledger_repo
        self._clock = clock
        self._id_generator = id_generator

    def run_check(self, raw_json: str) -> CheckResponse:
        fingerprint = _input_fingerprint(raw_json, self._config.privacy_mode)

        # 1. Parse at the trust boundary.
        try:
            raw_facts = parse_check_request(raw_json)
        except InputRejected as exc:
            return CheckResponse(
                category=ResultCategory.REJECTION,
                decision_id=None,
                outcome=None,
                detail=str(exc),
            )

        # 2. Scope guard.
        scope = evaluate_scope(
            raw_facts,
            supported_jurisdictions=self._config.supported_jurisdictions,
        )
        if scope.verdict is not None:
            return self._emit_abstention(
                raw_facts.check,
                scope.verdict,
                fingerprint=fingerprint,
                detail="Out-of-scope input routed to legal review.",
            )

        # 3. Required-facts resolution + engine dispatch.
        required = {
            CheckType.MINIMUM_WAGE: minimum_wage_facts(),
            CheckType.EXEMPTION_SALARY: exemption_salary_facts(),
        }[raw_facts.check]
        resolution = resolve(required, raw_facts)
        abstention = resolution.as_abstention()
        if abstention is not None:
            return self._emit_abstention(
                raw_facts.check,
                abstention,
                fingerprint=fingerprint,
                detail="Required facts missing / invalid / ambiguous.",
            )
        if raw_facts.check is CheckType.MINIMUM_WAGE:
            return self._run_minimum_wage(raw_facts, fingerprint=fingerprint)
        return self._run_exemption_salary(raw_facts, fingerprint=fingerprint)

    def _run_minimum_wage(
        self, raw_facts: RawFacts, *, fingerprint: Mapping[str, object]
    ) -> CheckResponse:
        converted = _to_minimum_wage_facts(raw_facts)
        if isinstance(converted, str):
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="engine",
                detail=converted,
                fingerprint=fingerprint,
            )

        try:
            engine_result = evaluate_minimum_wage(
                converted,
                self._config.rules,
                federal_code=self._config.federal_code,
            )
        except ConfigurationError as exc:
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="engine",
                detail=str(exc),
                fingerprint=fingerprint,
            )

        verdict = engine_result.verdict
        try:
            record = ledger_append(
                self._ledger,
                PartialHeader(
                    decision_id=self._id_generator(),
                    created_at=self._clock.now_utc(),
                    app_version=self._config.app_version,
                    git_commit=self._config.git_commit,
                    record_kind=RecordKind.DECISION,
                    check_type_value=raw_facts.check.value,
                    ruleset_version=RulesetVersion(str(self._config.rules.version)),
                    ruleset_hash=self._config.rules.ruleset_hash,
                ),
                body={
                    **fingerprint,
                    "verdict": "PASS" if isinstance(verdict, Passed) else "FLAG",
                    "controlling_rule_id": str(engine_result.controlling_rule.rule_id),
                    "controlling_rate": engine_result.controlling_rate.to_canonical_string(),
                    "actual_rate": engine_result.actual_rate.to_canonical_string(),
                    "shortfall": (
                        engine_result.shortfall.to_canonical_string()
                        if engine_result.shortfall is not None
                        else None
                    ),
                    "reason_codes": tuple(r.value for r in engine_result.reason_codes),
                },
            )
        except LedgerError as exc:
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="ledger",
                detail=str(exc),
                fingerprint=fingerprint,
            )

        outcome: Outcome
        if isinstance(verdict, Passed):
            outcome = Passed()
            detail = (
                f"Pay {engine_result.actual_rate.to_canonical_string()} meets the "
                f"controlling rate {engine_result.controlling_rate.to_canonical_string()}."
            )
        else:
            outcome = Flagged()
            detail = (
                f"Pay {engine_result.actual_rate.to_canonical_string()} is below the "
                f"controlling rate {engine_result.controlling_rate.to_canonical_string()}."
            )
        return CheckResponse(
            category=ResultCategory.DECISION,
            decision_id=record.header.decision_id,
            outcome=outcome,
            detail=detail,
        )

    def _run_exemption_salary(
        self, raw_facts: RawFacts, *, fingerprint: Mapping[str, object]
    ) -> CheckResponse:
        converted = _to_exemption_salary_facts(raw_facts)
        if isinstance(converted, str):
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="engine",
                detail=converted,
                fingerprint=fingerprint,
            )

        try:
            result = evaluate_exemption_salary(
                converted,
                self._config.rules,
                federal_code=self._config.federal_code,
            )
        except ConfigurationError as exc:
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="engine",
                detail=str(exc),
                fingerprint=fingerprint,
            )

        # Exemption engine can return Flagged or NeedsLegalReview directly.
        if isinstance(result.verdict, NeedsLegalReview):
            return self._emit_abstention(
                raw_facts.check,
                result.verdict,
                fingerprint=fingerprint,
                detail="Exemption necessary conditions not sufficient; sent to legal review.",
            )
        try:
            record = ledger_append(
                self._ledger,
                PartialHeader(
                    decision_id=self._id_generator(),
                    created_at=self._clock.now_utc(),
                    app_version=self._config.app_version,
                    git_commit=self._config.git_commit,
                    record_kind=RecordKind.DECISION,
                    check_type_value=raw_facts.check.value,
                    ruleset_version=RulesetVersion(str(self._config.rules.version)),
                    ruleset_hash=self._config.rules.ruleset_hash,
                ),
                body={
                    **fingerprint,
                    "verdict": "FLAG",
                    "reason_codes": tuple(r.value for r in result.reason_codes),
                    "salary_amount": result.salary_amount.to_canonical_string(),
                    "threshold_rate": (
                        result.threshold_rate.to_canonical_string()
                        if result.threshold_rate is not None
                        else None
                    ),
                    "controlling_rule_id": (
                        str(result.controlling_rule.rule_id)
                        if result.controlling_rule is not None
                        else None
                    ),
                },
            )
        except LedgerError as exc:
            return self._emit_fault(
                check_type=raw_facts.check.value,
                stage="ledger",
                detail=str(exc),
                fingerprint=fingerprint,
            )
        return CheckResponse(
            category=ResultCategory.DECISION,
            decision_id=record.header.decision_id,
            outcome=Flagged(),
            detail=("Facts do not satisfy the necessary conditions for the exemption."),
        )

    def _emit_abstention(
        self,
        check_type: CheckType,
        outcome: CannotDetermine | NeedsLegalReview,
        *,
        fingerprint: Mapping[str, object],
        detail: str,
    ) -> CheckResponse:
        try:
            record = ledger_append(
                self._ledger,
                PartialHeader(
                    decision_id=self._id_generator(),
                    created_at=self._clock.now_utc(),
                    app_version=self._config.app_version,
                    git_commit=self._config.git_commit,
                    record_kind=RecordKind.ABSTENTION,
                    check_type_value=check_type.value,
                    ruleset_version=RulesetVersion(str(self._config.rules.version)),
                    ruleset_hash=self._config.rules.ruleset_hash,
                ),
                body={
                    **fingerprint,
                    "kind": outcome.__class__.__name__,
                    "reasons": tuple(r.value for r in outcome.reasons),
                    "fields": (
                        tuple(f.value for f in outcome.fields)
                        if isinstance(outcome, CannotDetermine)
                        else ()
                    ),
                },
            )
        except LedgerError as exc:
            return self._emit_fault(
                check_type=check_type.value,
                stage="ledger",
                detail=str(exc),
                fingerprint=fingerprint,
            )

        return CheckResponse(
            category=ResultCategory.ABSTENTION,
            decision_id=record.header.decision_id,
            outcome=outcome,
            detail=detail,
        )

    def _emit_fault(
        self,
        *,
        check_type: str,
        stage: str,
        detail: str,
        fingerprint: Mapping[str, object] | None = None,
    ) -> CheckResponse:
        if stage not in _VALID_FAULT_STAGES:
            # Programmer error; fail loudly rather than mislabel a record.
            raise WageGuardError(f"invalid fault stage: {stage!r}")
        body: dict[str, object] = {"stage": stage, "detail": detail}
        if fingerprint is not None:
            body = {**fingerprint, **body}
        try:
            record = ledger_append(
                self._ledger,
                PartialHeader(
                    decision_id=self._id_generator(),
                    created_at=self._clock.now_utc(),
                    app_version=self._config.app_version,
                    git_commit=self._config.git_commit,
                    record_kind=RecordKind.FAULT,
                    check_type_value=check_type,
                    ruleset_version=RulesetVersion(str(self._config.rules.version)),
                    ruleset_hash=self._config.rules.ruleset_hash,
                ),
                body=body,
            )
            return CheckResponse(
                category=ResultCategory.FAULT,
                decision_id=record.header.decision_id,
                outcome=None,
                detail=detail,
                fault_stage=stage,
            )
        except LedgerError:
            # The ledger itself is down. Return a fault response with
            # no decision_id — the caller sees stage="ledger" and the
            # process exit / HTTP 503 remains correct.
            return CheckResponse(
                category=ResultCategory.FAULT,
                decision_id=None,
                outcome=None,
                detail=detail,
                fault_stage=stage,
            )
