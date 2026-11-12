"""Enforce that committed JSON schemas match the Pydantic models.

Runs in CI (make docs-check): if a model drifts from the committed
schema, the diff is printed and the exit code is non-zero. Regenerate
by running `python scripts/generate_schemas.py` (or re-running this
with `--write`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wageguard.intake.model import CheckRequestModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "docs" / "schemas"

_MODELS = (("check_request.json", CheckRequestModel),)


def _dump(model_cls: type) -> str:
    return json.dumps(model_cls.model_json_schema(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or regenerate committed JSON schemas")
    parser.add_argument("--write", action="store_true", help="Write current schemas to disk")
    args = parser.parse_args()

    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    drift: list[str] = []
    for filename, model_cls in _MODELS:
        path = SCHEMA_DIR / filename
        expected = _dump(model_cls)
        if args.write:
            path.write_text(expected, encoding="utf-8")
            print(f"[schemas] wrote {path.relative_to(PROJECT_ROOT)}")
            continue
        if not path.exists():
            drift.append(f"missing {path.relative_to(PROJECT_ROOT)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            drift.append(f"{path.relative_to(PROJECT_ROOT)} differs from {model_cls.__name__}")

    if drift and not args.write:
        print("[schemas] committed schemas drift from Pydantic models:", file=sys.stderr)
        for d in drift:
            print(f"  - {d}", file=sys.stderr)
        print(
            "\nRun `python scripts/check_schemas.py --write` to regenerate.",
            file=sys.stderr,
        )
        return 1

    if not args.write:
        print(f"[schemas] OK: {len(_MODELS)} schema(s) current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
