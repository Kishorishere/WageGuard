"""Reason codes: closed enum with a category and a human template (spec §7.2, App. A).

Adding a code without wiring it into both tables fails the unit tests;
`category_of` and `template_of` raise `KeyError` on unmapped codes.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ReasonCategory(StrEnum):
    DECISION = "decision"
    ABSTENTION_DATA = "abstention-data"
    ABSTENTION_SCOPE = "abstention-scope"
    REJECTION = "rejection"
    FAULT = "fault"


class ReasonCode(StrEnum):
    # --- abstention: data ---------------------------------------------------
    MISSING_REQUIRED_FACT = "missing_required_fact"
    INVALID_FIELD_VALUE = "invalid_field_value"
    AMBIGUOUS_FIELD_VALUE = "ambiguous_field_value"
    # --- abstention: scope --------------------------------------------------
    OUT_OF_SCOPE_JURISDICTION = "out_of_scope_jurisdiction"
    OUT_OF_SCOPE_WORKER_CATEGORY = "out_of_scope_worker_category"
    DATE_OUTSIDE_RULE_COVERAGE = "date_outside_rule_coverage"
    LOCAL_RULES_NOT_ENCODED = "local_rules_not_encoded"
    PERIOD_STRADDLES_RULE_CHANGE = "period_straddles_rule_change"
    STATE_RULE_ABSENT_FEDERAL_APPLIES = "state_rule_absent_federal_applies"
    STATE_EXEMPTION_RULES_NOT_ENCODED = "state_exemption_rules_not_encoded"
    THRESHOLD_STATUS_UNCERTAIN = "threshold_status_uncertain"
    EXEMPT_SALARY_BASIS_NOT_MET = "exempt_salary_basis_not_met"
    EXEMPT_SALARY_LEVEL_NOT_MET = "exempt_salary_level_not_met"
    EXEMPT_DUTIES_NOT_EVALUATED = "exempt_duties_not_evaluated"
    EXEMPT_DUTIES_NOT_MET = "exempt_duties_not_met"
    EXEMPT_NEEDS_HUMAN_CONFIRMATION = "exempt_needs_human_confirmation"
    # --- rejection ----------------------------------------------------------
    MALFORMED_INPUT = "malformed_input"
    UNKNOWN_FIELD = "unknown_field"
    # --- fault --------------------------------------------------------------
    FAULT_EVIDENCE_RETRIEVAL_UNAVAILABLE = "fault_evidence_retrieval_unavailable"
    FAULT_SOURCE_VERSION_MISMATCH = "fault_source_version_mismatch"
    FAULT_LLM_TIMEOUT = "fault_llm_timeout"
    FAULT_LLM_MALFORMED_OUTPUT = "fault_llm_malformed_output"
    FAULT_LLM_REFUSED = "fault_llm_refused"
    FAULT_VERIFICATION_CITATION_NOT_RETRIEVED = "fault_citation_not_retrieved"
    FAULT_VERIFICATION_QUOTE_MISMATCH = "fault_quote_mismatch"
    FAULT_VERIFICATION_OUTCOME_CONTRADICTION = "fault_outcome_contradiction"
    FAULT_MISSING_REQUIRED_CITATION = "fault_missing_required_citation"
    FAULT_LEDGER_APPEND_FAILED = "fault_ledger_append_failed"
    FAULT_LEDGER_CHAIN_BROKEN = "fault_ledger_chain_broken"
    FAULT_CONFIGURATION_ERROR = "fault_configuration_error"


_CATEGORY: Mapping[ReasonCode, ReasonCategory] = MappingProxyType(
    {
        ReasonCode.MISSING_REQUIRED_FACT: ReasonCategory.ABSTENTION_DATA,
        ReasonCode.INVALID_FIELD_VALUE: ReasonCategory.ABSTENTION_DATA,
        ReasonCode.AMBIGUOUS_FIELD_VALUE: ReasonCategory.ABSTENTION_DATA,
        ReasonCode.OUT_OF_SCOPE_JURISDICTION: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.DATE_OUTSIDE_RULE_COVERAGE: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.LOCAL_RULES_NOT_ENCODED: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.PERIOD_STRADDLES_RULE_CHANGE: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.STATE_RULE_ABSENT_FEDERAL_APPLIES: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.STATE_EXEMPTION_RULES_NOT_ENCODED: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.THRESHOLD_STATUS_UNCERTAIN: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.EXEMPT_SALARY_BASIS_NOT_MET: ReasonCategory.DECISION,
        ReasonCode.EXEMPT_SALARY_LEVEL_NOT_MET: ReasonCategory.DECISION,
        ReasonCode.EXEMPT_DUTIES_NOT_EVALUATED: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.EXEMPT_DUTIES_NOT_MET: ReasonCategory.DECISION,
        ReasonCode.EXEMPT_NEEDS_HUMAN_CONFIRMATION: ReasonCategory.ABSTENTION_SCOPE,
        ReasonCode.MALFORMED_INPUT: ReasonCategory.REJECTION,
        ReasonCode.UNKNOWN_FIELD: ReasonCategory.REJECTION,
        ReasonCode.FAULT_EVIDENCE_RETRIEVAL_UNAVAILABLE: ReasonCategory.FAULT,
        ReasonCode.FAULT_SOURCE_VERSION_MISMATCH: ReasonCategory.FAULT,
        ReasonCode.FAULT_LLM_TIMEOUT: ReasonCategory.FAULT,
        ReasonCode.FAULT_LLM_MALFORMED_OUTPUT: ReasonCategory.FAULT,
        ReasonCode.FAULT_LLM_REFUSED: ReasonCategory.FAULT,
        ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED: ReasonCategory.FAULT,
        ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH: ReasonCategory.FAULT,
        ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION: ReasonCategory.FAULT,
        ReasonCode.FAULT_MISSING_REQUIRED_CITATION: ReasonCategory.FAULT,
        ReasonCode.FAULT_LEDGER_APPEND_FAILED: ReasonCategory.FAULT,
        ReasonCode.FAULT_LEDGER_CHAIN_BROKEN: ReasonCategory.FAULT,
        ReasonCode.FAULT_CONFIGURATION_ERROR: ReasonCategory.FAULT,
    }
)


_TEMPLATE: Mapping[ReasonCode, str] = MappingProxyType(
    {
        ReasonCode.MISSING_REQUIRED_FACT: "Required fact is missing.",
        ReasonCode.INVALID_FIELD_VALUE: "Field value is present but unusable for this check.",
        ReasonCode.AMBIGUOUS_FIELD_VALUE: "Field value could mean more than one thing.",
        ReasonCode.OUT_OF_SCOPE_JURISDICTION: "Jurisdiction is not in the supported set.",
        ReasonCode.OUT_OF_SCOPE_WORKER_CATEGORY: "Worker category is not in the supported set.",
        ReasonCode.DATE_OUTSIDE_RULE_COVERAGE: "Work date is outside any encoded rule range.",
        ReasonCode.LOCAL_RULES_NOT_ENCODED: "Local (city/county) rules are not encoded.",
        ReasonCode.PERIOD_STRADDLES_RULE_CHANGE: "Pay period straddles a rule-change date.",
        ReasonCode.STATE_RULE_ABSENT_FEDERAL_APPLIES: (
            "No state rule for this date; federal rate applies."
        ),
        ReasonCode.STATE_EXEMPTION_RULES_NOT_ENCODED: (
            "State may impose a higher exemption threshold that is not encoded."
        ),
        ReasonCode.THRESHOLD_STATUS_UNCERTAIN: (
            "The threshold's legal status on the work date is uncertain."
        ),
        ReasonCode.EXEMPT_SALARY_BASIS_NOT_MET: (
            "Facts do not satisfy the salary-basis requirement."
        ),
        ReasonCode.EXEMPT_SALARY_LEVEL_NOT_MET: (
            "Facts do not satisfy the salary-level requirement."
        ),
        ReasonCode.EXEMPT_DUTIES_NOT_EVALUATED: "Duties test is not evaluated by this screen.",
        ReasonCode.EXEMPT_DUTIES_NOT_MET: "Encoded duties facts do not satisfy the test.",
        ReasonCode.EXEMPT_NEEDS_HUMAN_CONFIRMATION: (
            "Necessary conditions met; exemption still requires human confirmation."
        ),
        ReasonCode.MALFORMED_INPUT: "Input failed schema validation.",
        ReasonCode.UNKNOWN_FIELD: "Input contained an unknown field.",
        ReasonCode.FAULT_EVIDENCE_RETRIEVAL_UNAVAILABLE: "Evidence backend unavailable.",
        ReasonCode.FAULT_SOURCE_VERSION_MISMATCH: (
            "A required passage's source version does not match what the rule references."
        ),
        ReasonCode.FAULT_LLM_TIMEOUT: "LLM provider did not respond within the timeout.",
        ReasonCode.FAULT_LLM_MALFORMED_OUTPUT: "LLM output did not match the required schema.",
        ReasonCode.FAULT_LLM_REFUSED: "LLM declined to produce an explanation.",
        ReasonCode.FAULT_VERIFICATION_CITATION_NOT_RETRIEVED: (
            "A cited passage was not in this run's evidence bundle."
        ),
        ReasonCode.FAULT_VERIFICATION_QUOTE_MISMATCH: (
            "A quoted phrase was not found in the cited passage."
        ),
        ReasonCode.FAULT_VERIFICATION_OUTCOME_CONTRADICTION: (
            "LLM-asserted outcome disagreed with the engine outcome."
        ),
        ReasonCode.FAULT_MISSING_REQUIRED_CITATION: (
            "A passage required by the engine was not cited in the explanation."
        ),
        ReasonCode.FAULT_LEDGER_APPEND_FAILED: "Ledger append did not durably commit.",
        ReasonCode.FAULT_LEDGER_CHAIN_BROKEN: "Ledger chain linkage is broken.",
        ReasonCode.FAULT_CONFIGURATION_ERROR: "Startup configuration is invalid.",
    }
)


def category_of(code: ReasonCode) -> ReasonCategory:
    return _CATEGORY[code]


def template_of(code: ReasonCode) -> str:
    return _TEMPLATE[code]
