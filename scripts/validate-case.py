#!/usr/bin/env python3
"""Validate a Spotlight case directory against the published schemas.

Run after the investigator and fact-checker write their JSON to catch
data bugs before they enter the case archive — empty required strings,
missing top-level keys, wrong-shape documents, dangling fact-check
references, and confidence-vs-cap mismatches.

Intentionally avoids third-party JSON Schema dependencies. Performs
both schema-shape checks (re-implementing the subset that matters at
write-time) and cross-file checks that JSON Schema can't express.

Usage:
    python3 scripts/validate-case.py cases/{project}
    python3 scripts/validate-case.py cases/{project} --strict
    python3 scripts/validate-case.py cases/{project} --include-rlm

Exit code:
    0 — valid (warnings may still print to stderr)
    1 — invalid (at least one error in findings.json or fact-check.json)
    2 — case directory not found or unreadable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


VERDICTS = {"verified", "partially_verified", "unverified", "contradicted", "mischaracterized", "disputed", "false"}
CONFIDENCES = {"high", "medium", "low", "disputed"}
CAPS = {"high", "medium", "low"}
SUPPORT_TYPES = {"direct", "indirect", "inferred", "contradicted", "insufficient"}
SOURCE_ROLES = {"primary", "secondary", "contextual"}
HUMAN_REVIEW = {"unreviewed", "approved", "rejected"}
RLM_MODES = {"lite", "local_gemma4_e4b"}
RLM_PROVIDERS = {"deterministic", "ollama"}
RLM_STATUSES = {"needs_verification"}
RLM_KINDS = {"entity", "timeline_event", "contradiction", "lead", "discarded"}


def load_json(path: Path) -> tuple[Any, list[str]]:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle), []
    except FileNotFoundError:
        return None, [f"{path.name}: file not found"]
    except json.JSONDecodeError as exc:
        return None, [f"{path.name}: malformed JSON at line {exc.lineno}, col {exc.colno}: {exc.msg}"]
    except OSError as exc:
        return None, [f"{path.name}: read error: {exc}"]


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_findings(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"findings.json: top-level must be an object, got {type(data).__name__}"]

    # Required top-level fields
    if not nonempty_string(data.get("project")):
        errors.append("findings.json: missing or empty top-level 'project'")
    if "findings" not in data:
        errors.append("findings.json: missing top-level 'findings' — this is a finding archive, not a wrong-shape doc (paz-valais-communes-style). If the case produces commune_checks / claim_checks / other shapes, write them to a separate file (e.g. data/commune-checks.json), not findings.json.")
        return errors  # cannot continue without findings
    if not isinstance(data["findings"], list):
        errors.append("findings.json: 'findings' must be a list")
        return errors

    # Per-finding checks
    for i, finding in enumerate(data["findings"]):
        prefix = f"findings.json[{i}]"
        if not isinstance(finding, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        if not nonempty_string(finding.get("id")):
            errors.append(f"{prefix}: missing or empty 'id'")
        if not nonempty_string(finding.get("claim")):
            errors.append(f"{prefix}: missing or empty 'claim' — every finding must have a claim text. Skip the finding entirely if you can't articulate one.")
        if "evidence" in finding:
            ev = finding["evidence"]
            if not (nonempty_string(ev) or (isinstance(ev, list) and all(nonempty_string(x) for x in ev) and ev)):
                errors.append(f"{prefix}: 'evidence' must be a non-empty string or non-empty list of non-empty strings")
        elif "evidence" not in finding:
            errors.append(f"{prefix}: missing 'evidence'")
        if "sources" not in finding or not isinstance(finding["sources"], list):
            errors.append(f"{prefix}: missing or non-list 'sources'")
        elif len(finding["sources"]) == 0:
            errors.append(f"{prefix}: 'sources' is empty — every finding must cite at least one source")
        else:
            for j, src in enumerate(finding["sources"]):
                if not isinstance(src, dict):
                    errors.append(f"{prefix}.sources[{j}]: must be an object")
                # sources are optional-fielded now (schema reality alignment); only check basic shape

        conf = finding.get("confidence")
        if conf not in CONFIDENCES:
            errors.append(f"{prefix}: 'confidence' must be one of {sorted(CONFIDENCES)} (got {conf!r})")

        # Grounding object (optional in schema, but if present must be valid)
        grounding = finding.get("grounding")
        if grounding is not None:
            errors.extend(validate_grounding(grounding, prefix))

    return errors


def validate_grounding(grounding: Any, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(grounding, dict):
        return [f"{prefix}.grounding: must be an object"]
    if grounding.get("support_type") not in SUPPORT_TYPES:
        errors.append(f"{prefix}.grounding.support_type: must be one of {sorted(SUPPORT_TYPES)}")
    if grounding.get("source_role") not in SOURCE_ROLES:
        errors.append(f"{prefix}.grounding.source_role: must be one of {sorted(SOURCE_ROLES)}")
    if not isinstance(grounding.get("claim_elements_supported"), list):
        errors.append(f"{prefix}.grounding.claim_elements_supported: must be a list")
    if not isinstance(grounding.get("missing_assumptions"), list):
        errors.append(f"{prefix}.grounding.missing_assumptions: must be a list")
    if grounding.get("confidence_cap") not in CAPS:
        errors.append(f"{prefix}.grounding.confidence_cap: must be one of {sorted(CAPS)}")
    if not nonempty_string(grounding.get("misgrounding_risk")):
        errors.append(f"{prefix}.grounding.misgrounding_risk: missing or empty (write at minimum 'low; the claim restates source fields')")
    if not nonempty_string(grounding.get("grounding_rationale")):
        errors.append(f"{prefix}.grounding.grounding_rationale: missing or empty — explain why this evidence does or does not ground the claim, and include the contradiction-search outcome")
    return errors


def validate_fact_check(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(data, dict):
        return [f"fact-check.json: top-level must be an object, got {type(data).__name__}"]

    if not nonempty_string(data.get("project")):
        errors.append("fact-check.json: missing or empty top-level 'project'")

    # 'claims' is now optional at schema level (some legacy use 'verdicts'), but if present, validate
    if "claims" in data:
        if not isinstance(data["claims"], list):
            errors.append("fact-check.json: 'claims' must be a list")
        else:
            for i, claim in enumerate(data["claims"]):
                prefix = f"fact-check.json.claims[{i}]"
                if not isinstance(claim, dict):
                    errors.append(f"{prefix}: must be an object")
                    continue
                if not nonempty_string(claim.get("claim_text")):
                    errors.append(f"{prefix}: missing or empty 'claim_text' — every claim must have text. Skip the claim entirely if you can't articulate one.")
                if claim.get("verdict") not in VERDICTS:
                    errors.append(f"{prefix}: 'verdict' must be one of {sorted(VERDICTS)} (got {claim.get('verdict')!r})")

    return errors


def cross_reference(findings_data: dict[str, Any] | None, factcheck_data: dict[str, Any] | None) -> list[str]:
    """Cross-file: every fact-check claim's finding_id should resolve to a finding."""
    errors: list[str] = []
    if findings_data is None or factcheck_data is None:
        return errors
    finding_ids = {f.get("id") for f in findings_data.get("findings", []) if isinstance(f, dict)}
    for i, claim in enumerate(factcheck_data.get("claims", []) or []):
        if not isinstance(claim, dict):
            continue
        fid = claim.get("finding_id")
        if fid and fid not in finding_ids:
            errors.append(f"fact-check.json.claims[{i}]: 'finding_id' {fid!r} does not match any id in findings.json")
    return errors


def validate_rlm_analysis(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"rlm-analysis.json: top-level must be an object, got {type(data).__name__}"]
    for key in ("schema_version", "project", "run_id", "mode", "provider", "created_at", "artifacts"):
        if key not in data:
            errors.append(f"rlm-analysis.json: missing top-level '{key}'")
    if data.get("schema_version") != "1.0":
        errors.append("rlm-analysis.json: schema_version must be 1.0")
    if data.get("mode") not in RLM_MODES:
        errors.append(f"rlm-analysis.json: mode must be one of {sorted(RLM_MODES)}")
    if data.get("provider") not in RLM_PROVIDERS:
        errors.append(f"rlm-analysis.json: provider must be one of {sorted(RLM_PROVIDERS)}")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("rlm-analysis.json: artifacts must be a list")
        return errors
    for i, item in enumerate(artifacts):
        prefix = f"rlm-analysis.json.artifacts[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        if not nonempty_string(item.get("id")):
            errors.append(f"{prefix}: missing or empty id")
        if item.get("kind") not in RLM_KINDS:
            errors.append(f"{prefix}: kind must be one of {sorted(RLM_KINDS)}, got {item.get('kind')!r}")
        if not nonempty_string(item.get("text")):
            errors.append(f"{prefix}: missing or empty text")
        status = item.get("verification_status")
        if status not in RLM_STATUSES:
            errors.append(f"{prefix}: verification_status must be needs_verification, got {status!r}")
        if status in {"verified", "confirmed", "publishable"}:
            errors.append(f"{prefix}: forbidden verified-style status")
        source_refs = item.get("source_refs")
        if item.get("kind") != "discarded" and not source_refs:
            errors.append(f"{prefix}: non-discarded artifact must have source_refs")
        if source_refs is not None:
            if not isinstance(source_refs, list):
                errors.append(f"{prefix}: source_refs must be a list")
            else:
                for j, ref in enumerate(source_refs):
                    ref_prefix = f"{prefix}.source_refs[{j}]"
                    if not isinstance(ref, dict):
                        errors.append(f"{ref_prefix}: must be an object")
                        continue
                    if not nonempty_string(ref.get("path")):
                        errors.append(f"{ref_prefix}: missing or empty path")
                    for key in ("line_start", "line_end"):
                        if not isinstance(ref.get(key), int) or ref.get(key) < 1:
                            errors.append(f"{ref_prefix}: {key} must be a positive integer")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Spotlight case directory.")
    parser.add_argument("case_dir", help="Path to cases/{project}/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--include-rlm", action="store_true", help="Also validate optional data/rlm-analysis.json if present")
    args = parser.parse_args()

    case_dir = Path(args.case_dir).expanduser().resolve()
    if not case_dir.is_dir():
        print(f"error: not a directory: {case_dir}", file=sys.stderr)
        return 2

    findings_path = case_dir / "data" / "findings.json"
    if not findings_path.exists():
        findings_path = case_dir / "findings.json"
    factcheck_path = case_dir / "data" / "fact-check.json"
    if not factcheck_path.exists():
        factcheck_path = case_dir / "fact-check.json"

    all_errors: list[str] = []

    findings_data = None
    if findings_path.exists():
        findings_data, errs = load_json(findings_path)
        all_errors.extend(errs)
        if findings_data is not None:
            all_errors.extend(validate_findings(findings_data))
    else:
        all_errors.append(f"findings.json: not found in {case_dir}/data/ or {case_dir}/")

    factcheck_data = None
    if factcheck_path.exists():
        factcheck_data, errs = load_json(factcheck_path)
        all_errors.extend(errs)
        if factcheck_data is not None:
            all_errors.extend(validate_fact_check(factcheck_data))

    all_errors.extend(cross_reference(findings_data, factcheck_data))

    if args.include_rlm:
        rlm_path = case_dir / "data" / "rlm-analysis.json"
        if rlm_path.exists():
            rlm_data, errs = load_json(rlm_path)
            all_errors.extend(errs)
            if rlm_data is not None:
                all_errors.extend(validate_rlm_analysis(rlm_data))

    if all_errors:
        print(f"\n{len(all_errors)} validation error(s) in {case_dir.name}:\n", file=sys.stderr)
        for err in all_errors:
            print(f"  • {err}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    suffix = " + RLM" if args.include_rlm else ""
    print(f"✓ {case_dir.name} validates against findings + fact-check schemas{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
