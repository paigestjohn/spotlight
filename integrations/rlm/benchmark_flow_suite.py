#!/usr/bin/env python3
"""Run all RLM dummy Spotlight flow fixtures and aggregate scores."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def aggregate(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for fixture in fixtures:
        for result in fixture["results"]:
            by_mode.setdefault(result["mode"], []).append(result)
    mode_summary = {}
    for mode, results in sorted(by_mode.items()):
        ok_results = [result for result in results if result["status"] == "ok"]
        mode_summary[mode] = {
            "fixtures": len(results),
            "ok": len(ok_results),
            "errors": len(results) - len(ok_results),
            "avg_recall": average([result.get("finding_recall", 0.0) for result in ok_results]),
            "avg_precision": average([result.get("lead_precision", 0.0) for result in ok_results]),
            "avg_wall_time_seconds": average([result.get("wall_time_seconds", 0.0) for result in ok_results]),
            "avg_downstream_lines": average([result.get("source_lines_read_by_downstream", 0) for result in ok_results]),
            "total_absent_hits": sum(result.get("absent_hit_count", 0) for result in ok_results),
            "contradiction_required": sum(1 for result in ok_results if result.get("contradiction_required")),
            "contradiction_satisfied": sum(1 for result in ok_results if result.get("contradiction_required") and result.get("contradiction_requirement_satisfied")),
        }
    return mode_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all RLM flow fixtures.")
    parser.add_argument("--fixtures", required=True, help="Directory containing fixture subdirectories.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-rlm-chunk-budget", type=int, default=12)
    args = parser.parse_args()

    fixture_root = Path(args.fixtures)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_outputs: list[dict[str, Any]] = []
    for fixture in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
        fixture_out = out_path.parent / f"{out_path.stem}-{fixture.name}.json"
        proc = subprocess.run(
            [
                sys.executable,
                "integrations/rlm/benchmark_flow.py",
                "--fixture",
                str(fixture),
                "--out",
                str(fixture_out),
                "--no-rlm-chunk-budget",
                str(args.no_rlm_chunk_budget),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stdout, end="")
            print(proc.stderr, end="", file=sys.stderr)
            return proc.returncode
        fixture_outputs.append(json.loads(fixture_out.read_text(encoding="utf-8")))
    output = {
        "created_at": utc_now(),
        "fixture_root": str(fixture_root),
        "fixture_count": len(fixture_outputs),
        "mode_summary": aggregate(fixture_outputs),
        "fixtures": fixture_outputs,
    }
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out_path), "fixture_count": len(fixture_outputs), "mode_summary": output["mode_summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
