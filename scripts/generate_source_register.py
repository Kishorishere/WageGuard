"""Regenerate docs/source-register.md from the source manifest.

Phase 4 populates the register from the manifest only (no ingested
content yet); Phase 4+ runs rewire this to include retrieval
timestamps, content hashes, and passage counts from the store.
Run via `make docs-check` or directly with `--write` to update.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wageguard.evidence.manifest import SourceManifest, SourceSpec, load_source_manifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "sources" / "manifest.yaml"
REGISTER_PATH = PROJECT_ROOT / "docs" / "source-register.md"


_HEADER = """\
# Primary source register

**Generated.** Do not edit by hand. Regenerated from
`data/sources/manifest.yaml` by `scripts/generate_source_register.py`;
`make docs-check` fails if the committed file is stale.

| Source key | Publisher | Title | Jurisdiction | Topic(s) | Type | Fetch | Notes |
|------------|-----------|-------|--------------|----------|------|-------|-------|
"""


def _row(spec: SourceSpec) -> str:
    topics = ", ".join(t.value for t in spec.topics)
    return (
        f"| `{spec.source_key}` | {spec.publisher} | {spec.title} | "
        f"`{spec.jurisdiction}` | {topics} | {spec.source_type.value} | "
        f"{spec.fetch_method.value} | {spec.notes} |"
    )


def render(manifest: SourceManifest) -> str:
    lines = [_HEADER.rstrip()]
    for spec in manifest.sources:
        lines.append(_row(spec))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate docs/source-register.md")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        # Phase 0 ships no manifest; keep the register as scaffolding.
        if args.write:
            print(f"[source-register] {MANIFEST_PATH} not found; skipping write.")
        else:
            print("[source-register] OK: no manifest yet; register is scaffolding.")
        return 0

    manifest = load_source_manifest(MANIFEST_PATH)
    expected = render(manifest)

    if args.write:
        REGISTER_PATH.write_text(expected, encoding="utf-8")
        print(f"[source-register] wrote {REGISTER_PATH.relative_to(PROJECT_ROOT)}")
        return 0

    actual = REGISTER_PATH.read_text(encoding="utf-8") if REGISTER_PATH.exists() else ""
    if actual != expected:
        print(
            "[source-register] docs/source-register.md is stale; "
            "run `python scripts/generate_source_register.py --write`.",
            file=sys.stderr,
        )
        return 1

    print(f"[source-register] OK: {len(manifest.sources)} source(s) listed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
