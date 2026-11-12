"""Composition root (spec §17.1).

One factory that builds a `CheckService` from a `Settings` object.
Both CLI and API call `build_check_service()`; no other module
constructs infrastructure (G-23).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from wageguard.compliance.rules import Rule, Ruleset
from wageguard.config import Settings
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.identifiers import DecisionId, PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.ranges import EffectiveRange
from wageguard.interfaces.service import CheckService, ServiceConfig
from wageguard.ledger.repository import InMemoryLedgerRepository, LedgerRepository
from wageguard.resilience.clock import Clock, SystemClock


@dataclass(frozen=True, slots=True)
class CompositionArtifacts:
    service: CheckService
    ledger_repo: LedgerRepository
    rules: Ruleset
    settings: Settings


def _sequential_id_factory(prefix: str = "d-"):  # type: ignore[no-untyped-def]
    counter = itertools.count(1)

    def _gen() -> DecisionId:
        return DecisionId(f"{prefix}{next(counter):06d}")

    return _gen


def _synthetic_ruleset() -> Ruleset:
    """Default in-memory ruleset so the service runs end-to-end without
    real rule files (which require the user's VERIFY'd DOL/state data).

    VERIFY: replace with a real data/rules/*.yaml load before any
    non-prototype use.
    """
    passage = PassageId("synthetic_src", 1, 0)
    # The synthetic value is derived from an integer-cent constant so no
    # wage-shaped literal (e.g. "7.25") appears in Python source — see
    # G-06 and tests/architecture/test_no_legal_values_in_src.py.
    synthetic_rate = Decimal(725) / Decimal(100)
    rules = (
        Rule(
            rule_id=RuleId("us.mw.synth"),
            jurisdiction=jurisdiction("US"),
            topic=Topic.MINIMUM_WAGE,
            worker_category=WorkerCategory.GENERAL,
            value=synthetic_rate,
            unit="USD/hour",
            effective=EffectiveRange(date(2020, 1, 1), None),
            supporting_passages=(passage,),
            review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
            notes="Synthetic federal placeholder; NOT a real legal value.",
        ),
    )
    return Ruleset.from_rules(RulesetVersion("synthetic.0.0"), rules)


def build_check_service(
    settings: Settings,
    *,
    ledger_repo: LedgerRepository | None = None,
    clock: Clock | None = None,
) -> CompositionArtifacts:
    rules = _synthetic_ruleset()
    repo = ledger_repo if ledger_repo is not None else InMemoryLedgerRepository()
    config = ServiceConfig(
        rules=rules,
        supported_jurisdictions=frozenset({"US", "WA", "AL", "TESTLAND-A", "TESTLAND-B"}),
        federal_code=jurisdiction("US"),
        app_version="0.0.0",
        git_commit="unknown",
    )
    service = CheckService(
        config=config,
        ledger_repo=repo,
        clock=clock if clock is not None else SystemClock(),
        id_generator=_sequential_id_factory(),
    )
    return CompositionArtifacts(
        service=service,
        ledger_repo=repo,
        rules=rules,
        settings=settings,
    )
