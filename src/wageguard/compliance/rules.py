"""Rule, Ruleset, and applicable_rule (spec §9.3, §9.4).

Pure, stdlib only. Rules are immutable; Rulesets are built via
`Ruleset.from_rules(...)` which validates structural invariants
(no overlapping ranges, no unexplained gaps) and computes a canonical
hash. `applicable_rule` returns a sum type so the engine can
distinguish NoRule (legitimate "fall through to federal" path) from
Ambiguous (a ruleset defect that must be a Fault).
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from wageguard.domain.enums import ReviewStatus, Topic, WorkerCategory
from wageguard.domain.errors import ConfigurationError
from wageguard.domain.identifiers import PassageId, RuleId, RulesetVersion
from wageguard.domain.jurisdiction import Jurisdiction
from wageguard.domain.ranges import EffectiveRange


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: RuleId
    jurisdiction: Jurisdiction
    topic: Topic
    worker_category: WorkerCategory
    value: Decimal
    unit: str
    effective: EffectiveRange
    supporting_passages: tuple[PassageId, ...]
    review_status: ReviewStatus
    notes: str = ""


# --- RuleLookup sum type ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Found:
    rule: Rule


@dataclass(frozen=True, slots=True)
class NoRule:
    pass


@dataclass(frozen=True, slots=True)
class Ambiguous:
    rules: tuple[Rule, ...]


RuleLookup = Found | NoRule | Ambiguous


# --- Ruleset ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ruleset:
    version: RulesetVersion
    rules: tuple[Rule, ...]
    ruleset_hash: str

    @classmethod
    def from_rules(cls, version: RulesetVersion, rules: Sequence[Rule]) -> Ruleset:
        _check_overlap_and_gap(rules)
        ruleset_hash = _compute_ruleset_hash(rules)
        return cls(version=version, rules=tuple(rules), ruleset_hash=ruleset_hash)


def applicable_rule(
    rules: Ruleset,
    *,
    jurisdiction: Jurisdiction,
    topic: Topic,
    category: WorkerCategory,
    on: date,
) -> RuleLookup:
    matches = [
        r
        for r in rules.rules
        if r.jurisdiction == jurisdiction
        and r.topic == topic
        and r.worker_category == category
        and r.effective.contains(on)
    ]
    if not matches:
        return NoRule()
    if len(matches) > 1:
        return Ambiguous(rules=tuple(matches))
    return Found(rule=matches[0])


# --- structural validation -------------------------------------------------


def _check_overlap_and_gap(rules: Sequence[Rule]) -> None:
    grouped: dict[tuple[Jurisdiction, Topic, WorkerCategory], list[Rule]] = defaultdict(list)
    for r in rules:
        grouped[(r.jurisdiction, r.topic, r.worker_category)].append(r)

    def _start_key(r: Rule) -> date:
        return r.effective.start

    for key, group in grouped.items():
        ordered = sorted(group, key=_start_key)
        for a, b in itertools.pairwise(ordered):
            if a.effective.overlaps(b.effective):
                raise ConfigurationError(
                    f"overlapping rules for {key}: {a.rule_id} and {b.rule_id}"
                )
            # Adjacent-no-overlap is enforced by EffectiveRange; gap means
            # a.effective.end != b.effective.start (the earlier rule ended
            # strictly before the later one begins).
            if a.effective.end is None:
                continue
            if a.effective.end != b.effective.start:
                raise ConfigurationError(
                    f"gap between consecutive rules for {key}: "
                    f"{a.rule_id} ends {a.effective.end} but "
                    f"{b.rule_id} starts {b.effective.start}"
                )


# --- canonical hashing (ADR-0005 for Decimals) -----------------------------


_CANONICAL_PLACES = 4


def _canonical_decimal(v: Decimal) -> str:
    quantum = Decimal(10) ** -_CANONICAL_PLACES
    return format(v.quantize(quantum), "f")


def _canonical_rule(r: Rule) -> dict[str, object]:
    return {
        "rule_id": str(r.rule_id),
        "jurisdiction": str(r.jurisdiction),
        "topic": r.topic.value,
        "worker_category": r.worker_category.value,
        "value": _canonical_decimal(r.value),
        "unit": r.unit,
        "effective_from": r.effective.start.isoformat(),
        "effective_to": r.effective.end.isoformat() if r.effective.end else None,
        "supporting_passages": sorted(str(p) for p in r.supporting_passages),
        "review_status": r.review_status.value,
        # `notes` is intentionally excluded: changing a note does not
        # change the legal content, so it must not perturb decisions.
    }


def _rule_id_key(row: dict[str, object]) -> str:
    value = row["rule_id"]
    return str(value) if not isinstance(value, str) else value


def _compute_ruleset_hash(rules: Sequence[Rule]) -> str:
    rows = sorted((_canonical_rule(r) for r in rules), key=_rule_id_key)
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
