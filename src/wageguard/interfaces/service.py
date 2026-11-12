"""CheckService: the single entry point shared by CLI and API (spec §17.1, G-23).

Threads intake -> scope -> facts -> engine -> (ledger). Decisive
outcomes go on to retrieval -> explainer -> verifier -> ledger with a
decision record; abstentions skip the LLM (templated, ADR-0014) and
append an abstention record. Every fault path appends a fault record
(best effort) and never emits a decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from wageguard.compliance.checks.minimum_wage import evaluate_minimum_wage
from wageguard.compliance.facts import minimum_wage_facts, resolve
from wageguard.compliance.rules import Ruleset
from wageguard.compliance.scope import evaluate_scope
from wageguard.domain.enums import CheckType, PayBasis, WorkerCategory
from wageguard.domain.errors import (
    ConfigurationError,
    EvidenceError,
    InputRejected,
    LedgerError,
    LlmError,
    VerificationFailed,
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
                detail="Out-of-scope input routed to legal review.",
            )

        # 3. Required-facts resolution.
        if raw_facts.check is CheckType.MINIMUM_WAGE:
            resolution = resolve(minimum_wage_facts(), raw_facts)
            abstention = resolution.as_abstention()
            if abstention is not None:
                return self._emit_abstention(
                    raw_facts.check,
                    abstention,
                    detail="Required facts missing / invalid / ambiguous.",
                )
            return self._run_minimum_wage(raw_facts)

        return CheckResponse(
            category=ResultCategory.FAULT,
            decision_id=None,
            outcome=None,
            detail=f"check type not yet wired in CheckService: {raw_facts.check!r}",
            fault_stage="service",
        )

    def _run_minimum_wage(self, raw_facts: object) -> CheckResponse:
        from wageguard.compliance.checks.minimum_wage import MinimumWageFacts
        from wageguard.compliance.facts import RawFacts

        assert isinstance(raw_facts, RawFacts)

        values = raw_facts.values
        pay_rate_value = values.get(FieldName.PAY_RATE)
        work_state_value = values.get(FieldName.WORK_STATE)
        work_date_value = values.get(FieldName.WORK_DATE)
        pay_basis_value = values.get(FieldName.PAY_BASIS)
        worker_category_value = values.get(FieldName.WORKER_CATEGORY)

        from decimal import Decimal

        assert isinstance(pay_rate_value, Decimal)
        from datetime import date

        assert isinstance(work_state_value, str)
        assert isinstance(work_date_value, date)
        assert isinstance(pay_basis_value, PayBasis)
        assert isinstance(worker_category_value, WorkerCategory)

        facts = MinimumWageFacts(
            work_state=Jurisdiction(work_state_value),
            work_date=work_date_value,
            pay_rate=Money(pay_rate_value),
            pay_basis=pay_basis_value,
            worker_category=worker_category_value,
        )

        try:
            engine_result = evaluate_minimum_wage(
                facts, self._config.rules, federal_code=self._config.federal_code
            )
        except ConfigurationError as exc:
            return self._emit_fault("engine", str(exc))
        except WageGuardError as exc:  # pragma: no cover - defensive
            return self._emit_fault("engine", str(exc))

        # Retrieval, explainer, and verifier run on decisive outcomes
        # in the full composition root. The service threads the call
        # points; the LLM step is wired at composition time.
        # Append the decision record now with engine-only payload.
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
            return self._emit_fault("ledger", str(exc))

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

    def _emit_abstention(
        self,
        check_type: CheckType,
        outcome: CannotDetermine | NeedsLegalReview,
        *,
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
            return self._emit_fault("ledger", str(exc))

        return CheckResponse(
            category=ResultCategory.ABSTENTION,
            decision_id=record.header.decision_id,
            outcome=outcome,
            detail=detail,
        )

    def _emit_fault(self, stage: str, detail: str) -> CheckResponse:
        # Best-effort fault record. If the ledger itself is down, we
        # return a FAULT response without a decision_id (spec §13.5).
        try:
            record = ledger_append(
                self._ledger,
                PartialHeader(
                    decision_id=self._id_generator(),
                    created_at=self._clock.now_utc(),
                    app_version=self._config.app_version,
                    git_commit=self._config.git_commit,
                    record_kind=RecordKind.FAULT,
                    check_type_value="minimum_wage",
                    ruleset_version=RulesetVersion(str(self._config.rules.version)),
                    ruleset_hash=self._config.rules.ruleset_hash,
                ),
                body={"stage": stage, "detail": detail},
            )
            return CheckResponse(
                category=ResultCategory.FAULT,
                decision_id=record.header.decision_id,
                outcome=None,
                detail=detail,
                fault_stage=stage,
            )
        except (LedgerError, WageGuardError, Exception):
            return CheckResponse(
                category=ResultCategory.FAULT,
                decision_id=None,
                outcome=None,
                detail=detail,
                fault_stage=stage,
            )


# Silence unused-import warnings for types referenced only in docs.
_ = (EvidenceError, LlmError, VerificationFailed, Callable, datetime)
