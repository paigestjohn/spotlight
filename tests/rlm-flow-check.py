#!/usr/bin/env python3
"""Check the dummy RLM flow benchmark without requiring Ollama."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    out = Path(tempfile.gettempdir()) / "spotlight-rlm-flow-fake.json"
    proc = subprocess.run(
        [
            sys.executable,
            "integrations/rlm/benchmark_flow.py",
            "--fixture",
            "evals/rlm-flow-fixtures/fixture-context-rot-001",
            "--out",
            str(out),
            "--no-rlm-chunk-budget",
            "12",
        ],
        cwd=ROOT,
        env={**dict(), **__import__("os").environ, "SPOTLIGHT_RLM_FAKE_LOCAL": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    without, with_full, with_prefiltered = data["results"]
    assert without["mode"] == "without_rlm"
    assert with_full["mode"] == "with_rlm_full"
    assert with_prefiltered["mode"] == "with_rlm_hybrid_prefiltered"
    assert without["finding_recall"] < with_full["finding_recall"]
    assert without["finding_recall"] < with_prefiltered["finding_recall"]
    assert with_full["finding_recall"] == 1.0
    assert with_prefiltered["finding_recall"] == 1.0
    assert with_prefiltered["rlm_metrics"]["prefilter"] is True
    assert with_prefiltered["rlm_metrics"]["hybrid"] is True
    assert with_prefiltered["rlm_metrics"]["semantic_chunk_count"] > 0
    assert with_prefiltered["rlm_metrics"]["rlm_chunk_count"] < with_full["rlm_metrics"]["input_chunk_count"]
    assert with_prefiltered["source_lines_read_by_downstream"] < without["source_lines_read_by_downstream"]
    assert with_prefiltered["contradiction_required"] is True
    assert with_prefiltered["contradiction_requirement_satisfied"] is True
    suite_out = Path(tempfile.gettempdir()) / "spotlight-rlm-flow-suite-fake.json"
    proc = subprocess.run(
        [
            sys.executable,
            "integrations/rlm/benchmark_flow_suite.py",
            "--fixtures",
            "evals/rlm-flow-fixtures",
            "--out",
            str(suite_out),
            "--no-rlm-chunk-budget",
            "12",
        ],
        cwd=ROOT,
        env={**dict(), **__import__("os").environ, "SPOTLIGHT_RLM_FAKE_LOCAL": "1"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    suite = json.loads(suite_out.read_text(encoding="utf-8"))
    assert suite["fixture_count"] >= 4
    summary = suite["mode_summary"]
    assert summary["with_rlm_hybrid_prefiltered"]["avg_recall"] >= summary["without_rlm"]["avg_recall"]
    assert summary["with_rlm_hybrid_prefiltered"]["total_absent_hits"] <= summary["without_rlm"]["total_absent_hits"]
    assert summary["with_rlm_hybrid_prefiltered"]["contradiction_satisfied"] >= summary["without_rlm"]["contradiction_satisfied"]
    print("ok rlm flow proxy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
