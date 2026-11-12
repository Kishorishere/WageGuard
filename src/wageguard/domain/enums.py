"""Shared domain enums used across intake, facts, and the rule engine (spec §3)."""

from __future__ import annotations

from enum import StrEnum


class CheckType(StrEnum):
    MINIMUM_WAGE = "minimum_wage"
    EXEMPTION_SALARY = "exemption_salary"


class Topic(StrEnum):
    """Topic of a rule row (spec §9.3)."""

    MINIMUM_WAGE = "minimum_wage"
    EXEMPTION_SALARY_LEVEL = "exemption_salary_level"


class ReviewStatus(StrEnum):
    """Closed set tracking whether a rule's wording has been reviewed.

    Default is `not_reviewed_by_counsel`; the field exists so
    `make docs-check` and the README can honestly state which rows have
    had a legal review (spec §1.4).
    """

    NOT_REVIEWED_BY_COUNSEL = "not_reviewed_by_counsel"
    REVIEWED_BY_COUNSEL = "reviewed_by_counsel"


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
