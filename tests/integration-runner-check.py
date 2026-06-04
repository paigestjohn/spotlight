#!/usr/bin/env python3
"""Check shared integration runner safety properties."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations"))
from _runner import IntegrationError, integration_run_dir, resolve_within, run_subprocess, write_json_atomic  # noqa: E402


def expect_error(fn, label: str) -> None:
    try:
        fn()
    except IntegrationError:
        print(f"ok {label}")
        return
    raise AssertionError(f"expected IntegrationError: {label}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        expect_error(lambda: resolve_within(base, "/etc/passwd"), "absolute path rejected")
        expect_error(lambda: resolve_within(base, "../escape"), "traversal rejected")
        outside = base.parent / "outside-target"
        outside.write_text("x", encoding="utf-8")
        link = base / "link"
        os.symlink(outside, link)
        expect_error(lambda: resolve_within(base, "link"), "symlink escape rejected")

        run_dir = integration_run_dir("case-one", "maigret", "run-001", root=base)
        write_json_atomic(run_dir / "run-manifest.json", {"ok": True})
        data = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
        assert data["ok"] is True
        print("ok atomic manifest write")

        proc = run_subprocess(["python3", "-c", "print('ok')"])
        assert proc.returncode == 0 and proc.stdout.strip() == "ok"
        print("ok subprocess argument list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
