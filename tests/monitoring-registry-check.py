#!/usr/bin/env python3
"""Check monitoring/registry.py normalization, legacy migration, and CLI
round-trips. Stdlib only, no network; CLI cases run against a temp
SPOTLIGHT_CASES_ROOT.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "monitoring" / "registry.py"

spec = importlib.util.spec_from_file_location("monitoring_registry", SCRIPT)
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"ok   {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}{' — ' + detail if detail else ''}")


def main() -> int:
    # --- normalize_registry ---
    reg = mr.normalize_registry("p", None)
    check("normalize: None payload yields default shape",
          reg["schema_version"] == mr.SCHEMA_VERSION and reg["case_ref"] == "spotlight:p"
          and reg["mycroft"]["topic_slugs"] == [] and reg["checks"] == [])

    payload = {
        "schema_version": mr.SCHEMA_VERSION,
        "mycroft": {"topic_slugs": ["a", " a ", "b", "", 3], "last_checked_at": "t1"},
        "scoutpost": {"project_id": "sp1", "scouts": [
            {"scout_id": "s1", "scout_type": "pulse", "target": "x", "criteria": "y"},
            {"target": "no-id"},
            "not-a-dict",
        ]},
        "fallback_routines": [
            {"runtime": "claude", "handle": "h1", "scout_type": "web"},
            {"runtime": "claude"},
        ],
        "checks": [{"source": "mycroft", "summary": "s"}, "junk"],
    }
    reg = mr.normalize_registry("p", payload)
    check("normalize: topic slugs deduped and cleaned", reg["mycroft"]["topic_slugs"] == ["a", "b"])
    check("normalize: scout without id dropped, scout_type mapped",
          len(reg["scoutpost"]["scouts"]) == 1 and reg["scoutpost"]["scouts"][0]["monitor_kind"] == "pulse")
    check("normalize: fallback without handle dropped, scout_type mapped",
          len(reg["fallback_routines"]) == 1 and reg["fallback_routines"][0]["monitor_kind"] == "web")
    check("normalize: non-dict checks dropped, defaults filled",
          len(reg["checks"]) == 1 and reg["checks"][0]["source"] == "mycroft" and reg["checks"][0]["checked_at"])

    legacy_via_cojournalist = mr.normalize_registry("p", {
        "schema_version": mr.SCHEMA_VERSION,
        "cojournalist": {"project_id": "legacy-id", "scouts": [{"id": "s9", "target": "t"}]},
    })
    check("normalize: legacy cojournalist key honored when scoutpost absent",
          legacy_via_cojournalist["scoutpost"]["project_id"] == "legacy-id"
          and legacy_via_cojournalist["scoutpost"]["scouts"][0]["scout_id"] == "s9")

    # --- migrate_legacy_registry ---
    legacy = {
        "schema_version": "1",
        "topics": [{"slug": "topic-a"}, "topic-b", {"name": "no-slug"}],
        "project_id": "old-1",
        "scouts": [{"id": "s2", "scout_type": "social", "target": "t"}],
        "routines": [{"runtime": "hermes", "handle": "r1"}],
        "checks": [{"source": "scoutpost", "summary": "old check"}],
    }
    migrated = mr.normalize_registry("p", legacy)
    check("migrate: triggered for non-v2 schema", "migration" in migrated
          and migrated["migration"]["source_schema_version"] == "1")
    check("migrate: topic slugs extracted from dict and string forms",
          migrated["mycroft"]["topic_slugs"] == ["topic-a", "topic-b"])
    check("migrate: scouts carried with id alias and kind mapping",
          migrated["scoutpost"]["scouts"][0]["scout_id"] == "s2"
          and migrated["scoutpost"]["scouts"][0]["monitor_kind"] == "social")
    check("migrate: routines become fallback_routines",
          migrated["fallback_routines"][0]["handle"] == "r1")
    check("migrate: legacy snapshot preserved verbatim", migrated["legacy_snapshot"] == legacy)
    check("migrate: checks normalized", migrated["checks"][0]["summary"] == "old check")

    # --- CLI round-trips against a temp cases root ---
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, SPOTLIGHT_CASES_ROOT=tmp)

        def cli(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, str(SCRIPT), *args],
                                  capture_output=True, text=True, env=env)

        proj = "demo-case"
        check("cli: init exits 0", cli("init", "--project", proj).returncode == 0)
        cli("link-mycroft-topic", "--project", proj, "--slug", "topic-x")
        cli("link-mycroft-topic", "--project", proj, "--slug", "topic-x")
        reg_path = Path(tmp) / proj / "data" / "monitoring.json"
        data = json.loads(reg_path.read_text())
        check("cli: duplicate topic slug deduped", data["mycroft"]["topic_slugs"] == ["topic-x"])

        cli("link-scoutpost-scout", "--project", proj, "--scout-id", "s1",
            "--monitor-kind", "web", "--target", "t1", "--criteria", "c1")
        cli("link-scoutpost-scout", "--project", proj, "--scout-id", "s1",
            "--monitor-kind", "web", "--target", "t2", "--criteria", "c2")
        data = json.loads(reg_path.read_text())
        check("cli: re-linking same scout replaces, not duplicates",
              len(data["scoutpost"]["scouts"]) == 1 and data["scoutpost"]["scouts"][0]["target"] == "t2")

        bad = cli("record-check", "--project", proj, "--source", "mycroft",
                  "--summary", "s", "--items-json", "{\"not\": \"a list\"}")
        check("cli: record-check rejects non-list items-json", bad.returncode != 0)

        good = cli("record-check", "--project", proj, "--source", "mycroft", "--summary", "weekly")
        data = json.loads(reg_path.read_text())
        check("cli: record-check appends and stamps last_checked_at",
              good.returncode == 0 and len(data["checks"]) == 1
              and data["mycroft"]["last_checked_at"] is not None)

        check("cli: lock file created alongside registry",
              (Path(tmp) / proj / "data" / "monitoring.lock").exists())

        before = reg_path.read_text()
        cli("migrate", "--project", proj)
        check("cli: migrate on current schema is idempotent", reg_path.read_text() == before)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
