#!/usr/bin/env python3
"""Validate that integration routing rows point at real manifests."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    text = (ROOT / "skills" / "integrations" / "SKILL.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "integrations-roadmap.md").read_text(encoding="utf-8")
    errors: list[str] = []
    match = re.search(r"## Current integrations\n(?P<table>[\s\S]*?)\n## Routing decision tree", text)
    if not match:
        print("FAIL could not locate current integrations table", file=sys.stderr)
        return 1
    ids = sorted(set(re.findall(r"^\| `([^`]+)` \|", match.group("table"), flags=re.MULTILINE)))
    for integration_id in ids:
        manifest = ROOT / "integrations" / integration_id / "manifest.json"
        if manifest.exists():
            continue
        if f"`{integration_id}`" in roadmap:
            continue
        errors.append(f"{integration_id}: routing row has no manifest and is not in roadmap")

    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    print(f"integration routing contract: OK ({len(ids)} routed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
