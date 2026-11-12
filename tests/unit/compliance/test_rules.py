"""Rule / Ruleset: structural invariants and canonical hashing (spec §9.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from wageguard.compliance.rules import Rule, Ruleset
from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import jurisdiction
from wageguard.domain.ranges import EffectiveRange

_PASSAGE = PassageId("fake_src", 1, 0)


def _rule(
    *,
    rid: str = "rule-a",
    jur: str = "US",
    value: str = "7.00",
    start: date = date(2020, 1, 1),
    end: date | None = None,
    category: WorkerCategory = WorkerCategory.GENERAL,
) -> Rule:
    return Rule(
        rule_id=RuleId(rid),
        jurisdiction=jurisdiction(jur),
        topic=Topic.MINIMUM_WAGE,
        worker_category=category,
        value=Decimal(value),
        unit="USD/hour",
        effective=EffectiveRange(start, end),
        supporting_passages=(_PASSAGE,),
        review_status=ReviewStatus.NOT_REVIEWED_BY_COUNSEL,
    )


class TestRulesetConstruction:
    def test_builds_from_a_list_of_rules(self) -> None:
        rs = Ruleset.from_rules(RulesetVersion("v1"), (_rule(),))
        assert rs.version == "v1"
        assert len(rs.rules) == 1

    def test_rejects_overlapping_ranges_for_same_key(self) -> None:
        # (jurisdiction, topic, worker_category) key: overlapping ranges
        # would make applicable_rule return Ambiguous -> this is a
        # ruleset defect, caught at load (spec §9.3).
        overlapping = (
            _rule(rid="a", start=date(2020, 1, 1), end=date(2024, 12, 31)),
            _rule(rid="b", start=date(2024, 1, 1), end=None),
        )
        with pytest.raises(ConfigurationError, match="overlapping"):
            Ruleset.from_rules(RulesetVersion("v"), overlapping)

    def test_rejects_unexplained_gap_between_consecutive_rules(self) -> None:
        # Spec §9.3: gaps are either explicitly allowed with a note or
        # fail the load. Default behaviour rejects gaps.
        gappy = (
            _rule(rid="a", start=date(2020, 1, 1), end=date(2022, 1, 1)),
            _rule(rid="b", start=date(2023, 1, 1), end=None),
        )
        with pytest.raises(ConfigurationError, match="gap"):
            Ruleset.from_rules(RulesetVersion("v"), gappy)

    def test_accepts_separate_keys_regardless_of_ranges(self) -> None:
        # Different jurisdictions can have arbitrary ranges relative to
        # each other; the invariant is per-key.
        rules = (
            _rule(rid="us.a", jur="US", start=date(2020, 1, 1)),
            _rule(rid="tla.a", jur="TESTLAND-A", start=date(2020, 1, 1)),
        )
        rs = Ruleset.from_rules(RulesetVersion("v"), rules)
        assert len(rs.rules) == 2


class TestRulesetHash:
    def test_hash_is_deterministic(self) -> None:
        a = Ruleset.from_rules(RulesetVersion("v"), (_rule(),))
        b = Ruleset.from_rules(RulesetVersion("v"), (_rule(),))
        assert a.ruleset_hash == b.ruleset_hash

    def test_hash_is_independent_of_input_order(self) -> None:
        r1 = _rule(rid="r1", jur="US", value="7.00")
        r2 = _rule(rid="r2", jur="TESTLAND-A", value="15.00")
        a = Ruleset.from_rules(RulesetVersion("v"), (r1, r2))
        b = Ruleset.from_rules(RulesetVersion("v"), (r2, r1))
        assert a.ruleset_hash == b.ruleset_hash

    def test_hash_changes_when_any_value_changes(self) -> None:
        a = Ruleset.from_rules(RulesetVersion("v"), (_rule(value="7.25"),))
        b = Ruleset.from_rules(RulesetVersion("v"), (_rule(value="7.26"),))
        assert a.ruleset_hash != b.ruleset_hash

    def test_hash_treats_equivalent_decimals_as_equal(self) -> None:
        # ADR-0005 canonical form: "7.5" and "7.50" quantize to the
        # same canonical string, so the hashes must match.
        a = Ruleset.from_rules(RulesetVersion("v"), (_rule(value="7.5"),))
        b = Ruleset.from_rules(RulesetVersion("v"), (_rule(value="7.50"),))
        assert a.ruleset_hash == b.ruleset_hash

    def test_hash_changes_when_effective_range_changes(self) -> None:
        a = Ruleset.from_rules(
            RulesetVersion("v"),
            (_rule(start=date(2020, 1, 1)),),
        )
        b = Ruleset.from_rules(
            RulesetVersion("v"),
            (_rule(start=date(2021, 1, 1)),),
        )
        assert a.ruleset_hash != b.ruleset_hash
