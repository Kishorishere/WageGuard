"""CLI entry point (spec §17.2).

Exit codes are a documented contract:
  0   decision or abstention produced and logged
  1   unexpected error
  2   input rejected (malformed)
  3   fault (infrastructure)
  4   verification failure
  5   ledger integrity failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wageguard.config import Settings
from wageguard.interfaces.composition import build_check_service
from wageguard.interfaces.service import CheckResponse, ResultCategory
from wageguard.ledger.chain import verify_chain

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_REJECTION = 2
EXIT_FAULT = 3
EXIT_VERIFICATION = 4
EXIT_LEDGER_INTEGRITY = 5


def _check(args: argparse.Namespace) -> int:
    raw = Path(args.input).read_text(encoding="utf-8")
    settings = Settings()
    artifacts = build_check_service(settings)
    response = artifacts.service.run_check(raw)
    _print_response(response, as_json=bool(args.json))
    return _exit_code(response)


def _ledger_verify(args: argparse.Namespace) -> int:
    settings = Settings()
    artifacts = build_check_service(settings)
    report = verify_chain(artifacts.ledger_repo.all())
    if report.ok:
        print("ledger verify: OK")
        return EXIT_OK
    print(f"ledger verify: broken at index {report.break_at}: {report.reason}", file=sys.stderr)
    return EXIT_LEDGER_INTEGRITY


def _ledger_show(args: argparse.Namespace) -> int:
    settings = Settings()
    artifacts = build_check_service(settings)
    matches = artifacts.ledger_repo.find_by_decision_id(args.decision_id)
    if not matches:
        print(f"no records for decision_id={args.decision_id!r}", file=sys.stderr)
        return EXIT_UNEXPECTED
    for r in matches:
        print(
            json.dumps(
                {
                    "decision_id": r.header.decision_id,
                    "sequence_no": r.header.sequence_no,
                    "record_kind": r.header.record_kind.value,
                    "record_hash": r.record_hash,
                },
                indent=None,
                separators=(",", ":"),
            )
        )
    return EXIT_OK


def _rules_validate(args: argparse.Namespace) -> int:
    settings = Settings()
    try:
        artifacts = build_check_service(settings)
        _ = artifacts.rules
    except Exception as exc:
        print(f"rules validate: FAIL: {exc}", file=sys.stderr)
        return EXIT_FAULT
    print("rules validate: OK")
    return EXIT_OK


def _exit_code(response: CheckResponse) -> int:
    if response.category in {ResultCategory.DECISION, ResultCategory.ABSTENTION}:
        return EXIT_OK
    if response.category is ResultCategory.REJECTION:
        return EXIT_REJECTION
    return EXIT_FAULT


def _print_response(response: CheckResponse, *, as_json: bool) -> None:
    if as_json:
        payload = {
            "category": response.category.value,
            "decision_id": response.decision_id,
            "detail": response.detail,
            "fault_stage": response.fault_stage,
        }
        print(json.dumps(payload, indent=2))
        return
    print(f"{response.category.value.upper()}: {response.detail}")
    if response.decision_id is not None:
        print(f"decision_id: {response.decision_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wageguard", description="WageGuard CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="Run a compliance check on a JSON input file.")
    p_check.add_argument("input", help="Path to JSON input file.")
    p_check.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    p_check.set_defaults(func=_check)

    p_ledger = sub.add_parser("ledger", help="Ledger operations.")
    ledger_sub = p_ledger.add_subparsers(dest="ledger_cmd", required=True)
    p_verify = ledger_sub.add_parser("verify", help="Verify the ledger hash chain.")
    p_verify.set_defaults(func=_ledger_verify)
    p_show = ledger_sub.add_parser("show", help="Show records for a decision_id.")
    p_show.add_argument("decision_id")
    p_show.set_defaults(func=_ledger_show)

    p_rules = sub.add_parser("rules", help="Rules operations.")
    rules_sub = p_rules.add_subparsers(dest="rules_cmd", required=True)
    p_validate = rules_sub.add_parser("validate", help="Validate the loaded ruleset.")
    p_validate.set_defaults(func=_rules_validate)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"unexpected: {exc}", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
