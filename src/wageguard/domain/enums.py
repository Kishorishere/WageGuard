"""Shared domain enums used across intake, facts, and the rule engine (spec §3)."""

from __future__ import annotations

from enum import StrEnum


class CheckType(StrEnum):
    MINIMUM_WAGE = "minimum_wage"
    EXEMPTION_SALARY = "exemption_salary"


class PayBasis(StrEnum):
    HOURLY = "hourly"
    SALARY = "salary"


class PayPeriod(StrEnum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMI_MONTHLY = "semi_monthly"
    MONTHLY = "monthly"


class WorkerCategory(StrEnum):
    # The MVP supports GENERAL only (spec §9.6). Other categories exist
    # as closed vocabulary so the scope guard can route them to legal
    # review by name rather than "unknown".
    GENERAL = "general"
    TIPPED = "tipped"
    YOUTH = "youth"
    STUDENT = "student"
    LEARNER = "learner"
    APPRENTICE = "apprentice"
    DISABLED = "disabled"
