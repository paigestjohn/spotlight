#!/usr/bin/env python3
"""Check integrations/preflight.py smoke_test() logic paths.

Network-free: API probes use an unroutable localhost port so connection
failures are immediate; CLI probes use binaries guaranteed present (sh)
or absent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "integrations" / "preflight.py"

spec = importlib.util.spec_from_file_location("preflight", SCRIPT)
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

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
    # api: no URL configured → trivially ok
    ok, err = pf.smoke_test({"type": "api"})
    check("api: no homepage/docs URL passes", ok and err is None)

    # api: unreachable endpoint → failed with error detail
    ok, err = pf.smoke_test({"type": "api", "homepage": "http://127.0.0.1:1/"})
    check("api: connection failure reported", not ok and err is not None, f"ok={ok} err={err}")

    # library: unknown integration id → no module mapping, passes
    ok, err = pf.smoke_test({"type": "library", "id": "unknown-lib"})
    check("library: unmapped id passes", ok and err is None)

    # library: mapped id with module that is not installed under this name
    ok, err = pf.smoke_test({"type": "library", "id": "browser-use"})
    check("library: mapped id returns boolean with error on miss",
          isinstance(ok, bool) and (ok or "import" in (err or "")))

    # cli: binary present, no version args
    ok, err = pf.smoke_test({"type": "cli", "id": "sh"})
    check("cli: present binary passes", ok and err is None)

    # cli: binary missing
    ok, err = pf.smoke_test({"type": "cli", "id": "definitely-not-a-binary-xyz"})
    check("cli: missing binary fails with PATH error", not ok and "not on PATH" in (err or ""))

    # cli: version check exits non-zero
    ok, err = pf.smoke_test({"type": "cli", "id": "sh", "version_args": ["-c", "exit 7"]})
    check("cli: failing version check fails with exit code", not ok and "exited 7" in (err or ""))

    # cli: version check succeeds
    ok, err = pf.smoke_test({"type": "cli", "id": "sh", "version_args": ["-c", "exit 0"]})
    check("cli: passing version check passes", ok and err is None)

    # cli: local_binary override respected
    ok, err = pf.smoke_test({"type": "cli", "id": "anything", "local_binary": "sh"})
    check("cli: local_binary override resolves", ok and err is None)

    # unknown type → assumed ok
    ok, err = pf.smoke_test({"type": "mcp", "id": "x"})
    check("mcp/unknown type assumed ok", ok and err is None)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
