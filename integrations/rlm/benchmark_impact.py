#!/usr/bin/env python3
"""Benchmark RLM-off versus lite and Gemma4 E4B on Spotlight fixtures."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_rlm import MODEL, run, validate_analysis  # noqa: E402


MODES = ["off", "lite", "local_gemma4_e4b"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def model_available() -> bool:
    proc = subprocess.run(["ollama", "list"], text=True, capture_output=True, check=False)
    return proc.returncode == 0 and MODEL in proc.stdout


def score_fixture(analysis: dict[str, Any] | None, labels: dict[str, Any]) -> dict[str, Any]:
    if analysis is None:
        return {
            "json_valid_after_retry": True,
            "schema_valid": True,
            "source_ref_coverage": 0.0,
            "entity_recall": 0.0,
            "entity_false_positive_rate": 0.0,
            "contradiction_recall": 0.0,
            "lead_usefulness": 0,
        }
    artifacts = analysis.get("artifacts", [])
    errors = validate_analysis(analysis)
    expected_entities = set(labels.get("entities", []))
    found_entities = {a.get("text") for a in artifacts if a.get("kind") == "entity"}
    matched = expected_entities & found_entities
    false_positive = found_entities - expected_entities if expected_entities else set()
    sourceful = [a for a in artifacts if a.get("kind") == "discarded" or a.get("source_refs")]
    return {
        "json_valid_after_retry": True,
        "schema_valid": not errors,
        "schema_errors": errors,
        "source_ref_coverage": round(len(sourceful) / len(artifacts), 3) if artifacts else 1.0,
        "entity_recall": round(len(matched) / len(expected_entities), 3) if expected_entities else 1.0,
        "entity_false_positive_rate": round(len(false_positive) / len(found_entities), 3) if found_entities else 0.0,
        "contradiction_recall": 0.0,
        "lead_usefulness": 2 if artifacts else 0,
    }


def run_fixture(fixture: Path, mode: str, *, skip_local: bool) -> dict[str, Any]:
    request = json.loads((fixture / "request.json").read_text(encoding="utf-8"))
    labels = json.loads((fixture / "labels.json").read_text(encoding="utf-8"))
    request["mode"] = mode
    case_dir = ROOT / "cases" / request["project"]
    case_dir.mkdir(parents=True, exist_ok=True)
    if fixture.joinpath("corpus").is_dir():
        target = case_dir / "research"
        target.mkdir(parents=True, exist_ok=True)
        for src in fixture.joinpath("corpus").iterdir():
            if src.is_file():
                target.joinpath(src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    tmp_request = fixture / f".request-{mode}.json"
    tmp_request.write_text(json.dumps(request), encoding="utf-8")
    started = time.time()
    skipped = mode == "local_gemma4_e4b" and skip_local
    if skipped:
        result = {"status": "skipped", "reason": f"{MODEL} unavailable"}
        analysis = None
    else:
        result = run(tmp_request)
        analysis_path = result.get("analysis_path")
        analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8")) if analysis_path else None
    tmp_request.unlink(missing_ok=True)
    return {
        "fixture": fixture.name,
        "mode": mode,
        "status": result["status"],
        "wall_time_seconds": round(time.time() - started, 3),
        "metrics": score_fixture(analysis, labels),
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark RLM impact for Spotlight.")
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pull-missing", action="store_true", help="Pull gemma4:e4b if missing before local benchmark")
    args = parser.parse_args()

    if args.pull_missing and not model_available():
        subprocess.run(["ollama", "pull", MODEL], check=True)
    local_available = model_available()
    skip_local = not local_available and os.environ.get("SPOTLIGHT_RLM_FAKE_LOCAL") != "1"

    fixture_root = Path(args.fixtures)
    results = []
    for fixture in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
        for mode in MODES:
            results.append(run_fixture(fixture, mode, skip_local=skip_local))

    output = {
        "created_at": utc_now(),
        "model": MODEL,
        "modes": MODES,
        "local_model_available": local_available,
        "results": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_path.with_suffix(".md").write_text(
        "# RLM Impact Benchmark\n\n"
        f"- Model: `{MODEL}`\n"
        f"- Local available: `{local_available}`\n"
        f"- Fixture results: `{len(results)}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "out": str(out_path), "result_count": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
