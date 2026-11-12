"""Field names used by intake and the required-facts graph (spec §3, §8).

Phase 1 ships the minimal set exercised by the outcome types. Phase 2
grows this enum together with the intake pipeline.
"""

from __future__ import annotations

from enum import StrEnum


class FieldName(StrEnum):
    WORK_STATE = "work_state"
    WORK_DATE = "work_date"
    PAY_RATE = "pay_rate"
    PAY_BASIS = "pay_basis"
    WORKER_CATEGORY = "worker_category"
    EMPLOYER_SIZE = "employer_size"
    HOURS_WORKED = "hours_worked"
    SALARY_AMOUNT = "salary_amount"
    PAY_PERIOD = "pay_period"
    CURRENT_EXEMPT_STATUS = "current_exempt_status"
    LOCALITY = "locality"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
