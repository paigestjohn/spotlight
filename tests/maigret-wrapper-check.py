#!/usr/bin/env python3
"""Check bounded Maigret wrapper behavior without invoking Maigret."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "maigret"))
from run_maigret import build_command, run, validate_request  # noqa: E402


def write_request(tmp: Path, payload: dict) -> Path:
    path = tmp / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def assert_reject(payload: dict, label: str) -> None:
    try:
        validate_request(payload)
    except Exception:
        print(f"ok {label}")
        return
    raise AssertionError(f"expected reject: {label}")


def main() -> int:
    valid = validate_request(
        {
            "project": "case-one",
            "run_id": "20260604-username-scan",
            "usernames": ["example_user", "exampleuser"],
            "site_tags": ["social", "news"],
            "formats": ["json", "csv", "txt"],
        }
    )
    assert valid["scan_all_sites"] is False
    command = build_command(valid, Path("/tmp/out"))
    assert command[:3] == ["maigret", "example_user", "exampleuser"]
    assert "--ai" not in command and "-a" not in command
    assert "--json" in command and "--csv" in command and "--txt" in command
    print("ok command args")

    assert_reject({**valid, "scan_all_sites": True}, "full scan rejected")
    assert_reject({**valid, "use_ai": True}, "--ai rejected")
    assert_reject({**valid, "usernames": ["bad;name"]}, "invalid username rejected")
    assert_reject({**valid, "site_tags": ["bad tag"]}, "invalid tag rejected")

    with tempfile.TemporaryDirectory(dir=ROOT / "cases") as tmp_dir:
        tmp = Path(tmp_dir)
        request_path = write_request(tmp, {**valid, "project": Path(tmp_dir).name})
        result = run(request_path, dry_run=True)
        assert result["status"] == "dry_run"
        leads = json.loads(Path(result["normalized_leads"]).read_text(encoding="utf-8"))["leads"]
        assert leads == []
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        assert manifest["command"][0] == "maigret"
        print("ok dry-run artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
