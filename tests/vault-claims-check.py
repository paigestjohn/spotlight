#!/usr/bin/env python3
"""Validate the vault claims layer: claim notes, claims registry, alias index,
merge proposals, and master stats.

Default mode: validate tests/fixtures/claims-vault (expected to pass), then run
negative self-tests (fixture mutations expected to fail).

Real-vault mode: vault-claims-check.py --vault /path/to/vault
A vault that predates the claims layer (no claims/_registry.json) passes with a
notice — the layer is additive, absence is not an error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "claims-vault"

ALLOWED_VERDICTS = {"verified", "partially_verified"}
LAYER_FOR_VERDICT = {"verified": "durable", "partially_verified": "lead"}
NEEDS_VERIFICATION_FOR_LAYER = {"durable": False, "lead": True}
PROPOSAL_STATUSES = {"open", "accepted", "rejected"}
CLAIM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*-f\d+$")
REQUIRED_NOTE_FIELDS = {
    "id", "project", "finding_id", "entities", "verdict", "confidence",
    "confidence_cap", "layer", "recorded", "verified", "verified_by",
    "needs_verification",
}
REQUIRED_REGISTRY_FIELDS = {
    "id", "project", "entities", "verdict", "layer", "recorded", "verified",
    "needs_verification", "file",
}


def normalize(name: str) -> str:
    return " ".join(name.lower().split())


def load_json(path: Path, errors: list[str]) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: unreadable or invalid JSON ({exc})")
        return None


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, object] | None:
    """Minimal frontmatter parser for the generated note format:
    scalar `key: value` and inline lists `key: [a, b]`."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        errors.append(f"{path.name}: missing frontmatter")
        return None
    end = text.find("\n---", 4)
    if end == -1:
        errors.append(f"{path.name}: unterminated frontmatter")
        return None
    fields: dict[str, object] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            fields[key.strip()] = (
                [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
                if inner else []
            )
        else:
            fields[key.strip()] = raw.strip('"').strip("'")
    return fields


def note_body_sections(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 4)
    body = text[end + 4:] if end != -1 else text
    sections: dict[str, str] = {}
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"
    return sections


def validate_vault(vault: Path) -> tuple[list[str], list[str]]:
    """Returns (errors, notices)."""
    errors: list[str] = []
    notices: list[str] = []

    claims_registry_path = vault / "claims" / "_registry.json"
    if not claims_registry_path.exists():
        notices.append("no claims/_registry.json — vault predates the claims layer (ok, additive)")
        return errors, notices

    registry = load_json(claims_registry_path, errors)
    if registry is None:
        return errors, notices
    if registry.get("schema_version") != "1.0":
        errors.append("claims/_registry.json: schema_version must be 1.0")

    entries = {e.get("id"): e for e in registry.get("claims", [])}

    # --- Registry entry shape and verdict/layer consistency ---
    for cid, entry in entries.items():
        missing = REQUIRED_REGISTRY_FIELDS - set(entry)
        if missing:
            errors.append(f"claims registry {cid}: missing fields {sorted(missing)}")
            continue
        if not CLAIM_ID_RE.match(str(cid)):
            errors.append(f"claims registry {cid}: id not in {{project-id}}-f{{n}} format")
        if not str(cid).startswith(str(entry["project"]) + "-"):
            errors.append(f"claims registry {cid}: id does not start with project '{entry['project']}'")
        verdict = entry["verdict"]
        if verdict not in ALLOWED_VERDICTS:
            errors.append(f"claims registry {cid}: verdict '{verdict}' not allowed in claims layer")
        elif entry["layer"] != LAYER_FOR_VERDICT[verdict]:
            errors.append(f"claims registry {cid}: layer '{entry['layer']}' inconsistent with verdict '{verdict}'")
        if entry["layer"] in NEEDS_VERIFICATION_FOR_LAYER and \
                entry["needs_verification"] != NEEDS_VERIFICATION_FOR_LAYER[entry["layer"]]:
            errors.append(f"claims registry {cid}: needs_verification inconsistent with layer '{entry['layer']}'")
        if not (vault / str(entry["file"])).exists():
            errors.append(f"claims registry {cid}: note file {entry['file']} does not exist")

    # --- Note <-> registry parity (both directions) ---
    note_paths = sorted((vault / "claims").glob("*.md"))
    note_ids = {p.stem for p in note_paths}
    for cid in note_ids - set(entries):
        errors.append(f"claims/{cid}.md has no registry entry")
    for cid in set(entries) - note_ids:
        errors.append(f"claims registry {cid}: no note file in claims/")

    # --- Note frontmatter, sources, history ---
    # Entities registry comes in two shapes: spec {entities: [...]} and the
    # legacy live-vault shape {section, last_updated, items}.
    entity_registry = load_json(vault / "entities" / "_registry.json", errors) or {"entities": []}
    known_entities = {e["id"] for e in entity_registry.get("entities", entity_registry.get("items", []))}
    for path in note_paths:
        fm = parse_frontmatter(path, errors)
        if fm is None:
            continue
        missing = REQUIRED_NOTE_FIELDS - set(fm)
        if missing:
            errors.append(f"{path.name}: frontmatter missing {sorted(missing)}")
            continue
        entry = entries.get(path.stem)
        if entry:
            for field in ("project", "verdict", "layer"):
                if str(fm[field]) != str(entry[field]):
                    errors.append(f"{path.name}: frontmatter {field} '{fm[field]}' != registry '{entry[field]}'")
        if fm["verdict"] not in ALLOWED_VERDICTS:
            errors.append(f"{path.name}: verdict '{fm['verdict']}' not allowed in claims layer")
        if str(fm.get("confidence_cap")) == "low":
            errors.append(f"{path.name}: confidence_cap 'low' fails the eligibility gate")
        for eid in fm.get("entities", []):
            if eid not in known_entities:
                errors.append(f"{path.name}: entity '{eid}' not in entities registry")
        sections = note_body_sections(path)
        sources = sections.get("Sources", "")
        if not any(line.strip().lstrip("-").strip() for line in sources.splitlines()):
            errors.append(f"{path.name}: Sources section empty — claims require source refs")
        if "Supersession History" not in sections:
            errors.append(f"{path.name}: missing Supersession History section")

    # --- Merge proposals schema (loaded first: the alias check below excuses
    #     collisions that carry a recorded proposal) ---
    proposal_pairs: set[frozenset[str]] = set()
    proposals = load_json(vault / "entities" / "_merge-proposals.json", errors)
    if proposals is not None:
        for prop in proposals.get("proposals", []):
            if prop.get("status") not in PROPOSAL_STATUSES:
                errors.append(f"_merge-proposals.json {prop.get('id')}: invalid status '{prop.get('status')}'")
            for eid in prop.get("entities", []):
                if eid not in known_entities:
                    errors.append(f"_merge-proposals.json {prop.get('id')}: unknown entity '{eid}'")
            proposal_pairs.add(frozenset(prop.get("entities", [])))

    # --- Alias index derivable from entity frontmatter ---
    alias_index = load_json(vault / "entities" / "_aliases.json", errors)
    if alias_index is not None:
        alias_map = alias_index.get("aliases", {})
        for value in set(alias_map.values()):
            if value not in known_entities:
                errors.append(f"_aliases.json: '{value}' is not a known entity id")
        for entity_path in sorted((vault / "entities").glob("*.md")):
            fm = parse_frontmatter(entity_path, errors)
            if fm is None:
                continue
            for alias in fm.get("aliases", []):
                key = normalize(str(alias))
                mapped = alias_map.get(key)
                if mapped == fm.get("id"):
                    continue
                # A collision with a recorded merge proposal is a flagged,
                # human-gated state — not index drift.
                if mapped and frozenset({mapped, str(fm.get("id"))}) in proposal_pairs:
                    continue
                errors.append(
                    f"_aliases.json: alias '{key}' of {fm.get('id')} missing or mapped elsewhere"
                )

    # --- Master stats ---
    master = load_json(vault / "_registry.json", errors)
    if master is not None:
        stat = master.get("stats", {}).get("claims")
        if stat != len(entries) or stat != len(note_ids):
            errors.append(
                f"_registry.json: stats.claims={stat} but registry has {len(entries)} entries "
                f"and claims/ has {len(note_ids)} notes"
            )

    return errors, notices


# --- Negative self-tests: each mutation must produce at least one error ---

def _mutate_json(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def negative_cases() -> list[tuple[str, callable]]:
    def drop_registry_entry(v: Path):
        _mutate_json(v / "claims/_registry.json", lambda d: d["claims"].pop(0))
        _mutate_json(v / "_registry.json", lambda d: d["stats"].__setitem__("claims", 1))

    def orphan_registry_entry(v: Path):
        def add(d):
            ghost = dict(d["claims"][0], id="test-case-f9", file="claims/test-case-f9.md")
            d["claims"].append(ghost)
        _mutate_json(v / "claims/_registry.json", add)

    def empty_sources(v: Path):
        p = v / "claims/test-case-f1.md"
        text = p.read_text(encoding="utf-8")
        p.write_text(text.replace("- https://example.org/registry/filing-123 (accessed 2026-06-01)\n", ""), encoding="utf-8")

    def missing_alias(v: Path):
        _mutate_json(v / "entities/_aliases.json", lambda d: d["aliases"].pop("acme ltd"))

    def bad_verdict(v: Path):
        _mutate_json(v / "claims/_registry.json", lambda d: d["claims"][0].__setitem__("verdict", "disputed"))

    def stats_mismatch(v: Path):
        _mutate_json(v / "_registry.json", lambda d: d["stats"].__setitem__("claims", 5))

    def layer_inconsistent(v: Path):
        _mutate_json(v / "claims/_registry.json", lambda d: d["claims"][0].__setitem__("layer", "lead"))

    def low_confidence_cap(v: Path):
        p = v / "claims/test-case-f1.md"
        p.write_text(p.read_text(encoding="utf-8").replace("confidence_cap: high", "confidence_cap: low"), encoding="utf-8")

    def missing_supersession(v: Path):
        p = v / "claims/test-case-f1.md"
        p.write_text(p.read_text(encoding="utf-8").replace("## Supersession History", "## History"), encoding="utf-8")

    def bad_proposal_status(v: Path):
        def add(d):
            d["proposals"].append({"id": "merge-0001", "entities": ["acme-corp", "john-doe"],
                                   "colliding_alias": "x", "source_project": "test-case",
                                   "proposed": "2026-06-01", "status": "maybe"})
        _mutate_json(v / "entities/_merge-proposals.json", add)

    return [
        ("note without registry entry", drop_registry_entry),
        ("registry entry without note", orphan_registry_entry),
        ("claim without sources", empty_sources),
        ("alias missing from index", missing_alias),
        ("verdict outside claims-layer enum", bad_verdict),
        ("master stats mismatch", stats_mismatch),
        ("layer inconsistent with verdict", layer_inconsistent),
        ("confidence_cap low fails eligibility", low_confidence_cap),
        ("missing Supersession History section", missing_supersession),
        ("invalid merge-proposal status", bad_proposal_status),
    ]


def run_self_tests() -> int:
    failures = 0
    errors, _ = validate_vault(FIXTURE)
    if errors:
        print("FAIL fixture vault should validate cleanly:")
        for err in errors:
            print(f"  - {err}")
        failures += 1
    else:
        print("ok   fixture vault validates")

    for name, mutate in negative_cases():
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "vault"
            shutil.copytree(FIXTURE, copy)
            mutate(copy)
            errors, _ = validate_vault(copy)
            if errors:
                print(f"ok   rejects: {name}")
            else:
                print(f"FAIL not rejected: {name}")
                failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, help="validate a real vault instead of running self-tests")
    args = parser.parse_args()

    if args.vault:
        if not args.vault.is_dir():
            print(f"FAIL not a directory: {args.vault}")
            return 1
        errors, notices = validate_vault(args.vault)
        for note in notices:
            print(f"note {note}")
        if errors:
            print(f"FAIL {args.vault}: {len(errors)} error(s)")
            for err in errors:
                print(f"  - {err}")
            return 1
        print(f"ok   {args.vault}: claims layer valid")
        return 0

    return 1 if run_self_tests() else 0


if __name__ == "__main__":
    sys.exit(main())
