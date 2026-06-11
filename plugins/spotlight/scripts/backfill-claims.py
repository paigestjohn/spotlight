#!/usr/bin/env python3
"""Backfill the vault claims layer from existing investigation notes.

Reads investigations/*.md (read-only) and emits:
  claims/{project}-f{n}.md      one note per eligible finding
  claims/_registry.json         claims registry
  entities/_aliases.json        rebuilt from entity note frontmatter
  entities/_merge-proposals.json  created empty if missing (existing preserved)
  _registry.json                stats.claims updated

Eligibility gate (same as ingest): verdict `verified` or `partially_verified`,
confidence above `low`, sources present. Legacy notes carry no grounding
objects, so `confidence_cap` is set to the finding's confidence — recorded
here as the backfill assumption. Findings without an explicit verdict marker
inherit `verified` only when the investigation frontmatter declares
verified_count == total_findings; otherwise they are excluded and reported.
Only investigations with status `confirmed` are processed.

Idempotent: a second --apply run produces no changes. Investigation and
entity notes are never modified.

Usage:
  backfill-claims.py --vault /path/to/vault            # dry-run report
  backfill-claims.py --vault /path/to/vault --apply    # write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path


ALLOWED_VERDICTS = {"verified", "partially_verified"}
VERDICT_MAP = {
    "verified": "verified",
    "confirmed": "verified",
    "partially_verified": "partially_verified",
    "partially verified": "partially_verified",
}
HEADING_RE = re.compile(r"^### F[-]?0*(\d+)\s*[—:\-]*\s*(.*)$")
HEADING_CONFIDENCE_RE = re.compile(r"\((High|Medium|Low) Confidence\)\s*$", re.IGNORECASE)
FIELD_RE = re.compile(r"^[-*\s]*\*\*(Claim|Confidence|Verdict|Evidence|Sources|Perspective):\*\*\s*(.*)$")
PLAIN_SOURCES_RE = re.compile(r"^Sources:\s*(.*)$")
WIKILINK_RE = re.compile(r"\[\[([a-z0-9-]+)\]\]")


def normalize(name: str) -> str:
    return " ".join(name.lower().split())


def registry_items(doc: dict, key: str) -> list[dict]:
    """Registries come in two shapes: the spec shape {key: [...]} and the
    legacy live-vault shape {section, last_updated, items}."""
    return doc.get(key, doc.get("items", []))


def parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
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


def split_findings(body: str) -> list[tuple[int, str, list[str]]]:
    """Returns (finding_number, heading_title, section_lines) per `### F<n>` section."""
    findings: list[tuple[int, str, list[str]]] = []
    current: list[str] | None = None
    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            current = []
            findings.append((int(match.group(1)), match.group(2).strip(), current))
        elif line.startswith("## "):
            current = None
        elif current is not None:
            current.append(line)
    return findings


def parse_finding(number: int, title: str, lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {"title": title}
    conf = HEADING_CONFIDENCE_RE.search(title)
    if conf:
        fields["confidence"] = conf.group(1).lower()
        fields["title"] = HEADING_CONFIDENCE_RE.sub("", title).strip()

    paragraphs: list[str] = []
    sources_open = False
    for line in lines:
        field = FIELD_RE.match(line)
        if field:
            key = field.group(1).lower()
            fields[key] = field.group(2).strip()
            sources_open = key == "sources"
            continue
        plain = PLAIN_SOURCES_RE.match(line.strip())
        if plain:
            fields["sources"] = plain.group(1).strip()
            sources_open = True
            continue
        if sources_open:
            if line.strip():
                fields["sources"] = fields.get("sources", "") + "\n" + line.strip()
                continue
            sources_open = False
        if line.strip() and not line.strip().startswith(("|", ">")):
            paragraphs.append(line.strip())

    if "claim" not in fields:
        fields["claim"] = paragraphs[0] if paragraphs else fields["title"]
    fields["entities_in_section"] = sorted(set(WIKILINK_RE.findall("\n".join(lines))))
    fields["number"] = str(number)
    return fields


def build_claim_note(project: str, fields: dict, verdict: str, layer: str, inv_date: str) -> tuple[str, str]:
    claim_id = f"{project}-f{fields['number']}"
    needs = "true" if layer == "lead" else "false"
    entities = ", ".join(fields["entities_in_section"])
    sources_block = "\n".join(
        line if line.startswith("-") else f"- {line}"
        for line in fields.get("sources", "").splitlines() if line.strip()
    )
    connections = ", ".join(f"[[{e}]]" for e in fields["entities_in_section"]) or "—"
    note = f"""---
id: {claim_id}
project: {project}
finding_id: F{fields['number']}
entities: [{entities}]
verdict: {verdict}
confidence: {fields['confidence']}
confidence_cap: {fields['confidence']}
layer: {layer}
recorded: {inv_date}
verified: {inv_date}
verified_by: {project}
needs_verification: {needs}
---

## Claim

{fields['claim']}

## Evidence Summary

{fields.get('evidence', fields['title'])}

## Sources

{sources_block}

## Supersession History

| Date | Investigation | Event | Verdict |
|------|---------------|-------|---------|

## Connections

{connections}, [[{project}]]
"""
    return claim_id, note


def build_alias_index(vault: Path, report: list[str]) -> tuple[dict[str, str], list[dict]]:
    aliases: dict[str, str] = {}
    collisions: list[dict] = []
    for path in sorted((vault / "entities").glob("*.md")):
        fm = parse_frontmatter(path.read_text(encoding="utf-8"))
        eid = str(fm.get("id", path.stem))
        names = [str(a) for a in fm.get("aliases", [])] + [eid.replace("-", " ")]
        for name in names:
            key = normalize(name)
            if key in aliases and aliases[key] != eid:
                report.append(f"WARN alias '{key}' shared by {aliases[key]} and {eid} — merge proposal recorded, kept {aliases[key]}")
                collisions.append({"entities": sorted([aliases[key], eid]), "colliding_alias": key})
                continue
            aliases[key] = eid
    return aliases, collisions


def write_if_changed(path: Path, content: str, applied: list[str], dry: bool) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    if not dry:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    applied.append(str(path))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    args = parser.parse_args()
    vault = args.vault.resolve()
    dry = not args.apply

    if not (vault / "investigations" / "_registry.json").exists():
        print(f"FAIL no investigations registry under {vault}")
        return 1
    lock = vault / ".ingest-lock"
    if lock.exists():
        print("FAIL .ingest-lock present — another ingestion is in progress")
        return 1
    if not dry:
        lock.write_text(f"backfill-claims {date.today().isoformat()}", encoding="utf-8")

    report: list[str] = []
    applied: list[str] = []
    try:
        inv_registry = json.loads((vault / "investigations" / "_registry.json").read_text(encoding="utf-8"))
        entity_registry = json.loads((vault / "entities" / "_registry.json").read_text(encoding="utf-8"))
        known_entities = {e["id"] for e in registry_items(entity_registry, "entities")}
        alias_map, collisions = build_alias_index(vault, report)
        # Alias keys usable for name-in-text matching: multi-word or long
        # enough to avoid false positives on short tokens.
        text_match_aliases = {k: v for k, v in alias_map.items() if " " in k or len(k) > 6}
        claims: list[dict] = []
        notes: dict[str, str] = {}

        for inv in sorted(registry_items(inv_registry, "investigations"), key=lambda i: i["id"]):
            project = inv["id"]
            note_path = vault / "investigations" / f"{project}.md"
            if inv.get("status") != "confirmed":
                report.append(f"SKIP {project}: status '{inv.get('status')}' (only confirmed investigations are backfilled)")
                continue
            if not note_path.exists():
                report.append(f"SKIP {project}: investigation note missing")
                continue
            text = note_path.read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            inv_date = str(fm.get("date", inv.get("date", "")))
            total = str(fm.get("total_findings", ""))
            counts_all_verified = (
                "verified_count" in fm
                and str(fm.get("verified_count")) == total
                and total.isdigit()
                and int(total) > 0
            )
            findings = split_findings(text)
            if not findings:
                report.append(f"NOTE {project}: no finding sections found — nothing to backfill")
                continue

            for number, title, lines in findings:
                fields = parse_finding(number, title, lines)
                fid = f"F{number}"
                raw_verdict = fields.get("verdict", "").lower()
                if raw_verdict:
                    verdict = VERDICT_MAP.get(raw_verdict)
                    if verdict is None:
                        report.append(f"EXCLUDE {project} {fid}: verdict '{raw_verdict}' fails the eligibility gate")
                        continue
                elif counts_all_verified:
                    verdict = "verified"
                else:
                    report.append(f"EXCLUDE {project} {fid}: no verdict marker and investigation does not declare all findings verified")
                    continue
                confidence = fields.get("confidence", "").lower()
                if not confidence:
                    report.append(f"EXCLUDE {project} {fid}: no confidence marker")
                    continue
                if confidence == "low":
                    report.append(f"EXCLUDE {project} {fid}: confidence low fails the eligibility gate")
                    continue
                if not fields.get("sources", "").strip():
                    report.append(f"EXCLUDE {project} {fid}: no sources")
                    continue

                layer = "durable" if verdict == "verified" else "lead"
                # Wikilinks in finding sections also reference tools and
                # methodology — keep only registered entities. Prose-style
                # notes often name entities without wikilinks, so fall back
                # to alias-map matching against the section text.
                section_text = " " + normalize(title + " " + "\n".join(lines)) + " "
                matched = {
                    eid for key, eid in text_match_aliases.items()
                    if f" {key} " in section_text or f" {key}." in section_text
                }
                fields["entities_in_section"] = sorted(
                    (set(fields["entities_in_section"]) & known_entities) | matched
                )
                claim_id, note = build_claim_note(project, fields, verdict, layer, inv_date)
                notes[claim_id] = note
                claims.append({
                    "id": claim_id,
                    "project": project,
                    "entities": fields["entities_in_section"],
                    "verdict": verdict,
                    "layer": layer,
                    "recorded": inv_date,
                    "verified": inv_date,
                    "needs_verification": layer == "lead",
                    "file": f"claims/{claim_id}.md",
                })
                report.append(f"CLAIM {claim_id}: {verdict} ({layer})")

        claims.sort(key=lambda c: c["id"])
        for claim_id, note in notes.items():
            write_if_changed(vault / "claims" / f"{claim_id}.md", note, applied, dry)
        write_if_changed(
            vault / "claims" / "_registry.json",
            json.dumps({"schema_version": "1.0", "claims": claims}, indent=2) + "\n",
            applied, dry,
        )

        # Deterministic date anchor (latest claim date) keeps re-runs
        # idempotent where a wall-clock timestamp would not.
        date_anchor = max((str(c.get("recorded", "")) for c in claims), default="") or "backfill"

        existing_aliases = vault / "entities" / "_aliases.json"
        alias_doc = {"schema_version": "1.0", "generated": date_anchor,
                     "aliases": dict(sorted(alias_map.items()))}
        write_if_changed(existing_aliases, json.dumps(alias_doc, indent=2) + "\n", applied, dry)

        proposals_path = vault / "entities" / "_merge-proposals.json"
        proposals_doc = {"schema_version": "1.0", "proposals": []}
        if proposals_path.exists():
            try:
                proposals_doc = json.loads(proposals_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        # Pair identity is order-insensitive: ingest-written proposals may
        # not store entities sorted.
        known_pairs = {frozenset(p.get("entities", [])) for p in proposals_doc.get("proposals", [])}
        for collision in collisions:
            pair = frozenset(collision["entities"])
            if pair in known_pairs:
                continue
            proposals_doc["proposals"].append({
                "id": f"merge-{len(proposals_doc['proposals']) + 1:04d}",
                "entities": collision["entities"],
                "colliding_alias": collision["colliding_alias"],
                "source_project": "backfill",
                "proposed": date_anchor,
                "status": "open",
            })
            known_pairs.add(pair)
        write_if_changed(proposals_path, json.dumps(proposals_doc, indent=2) + "\n", applied, dry)

        master_path = vault / "_registry.json"
        master = json.loads(master_path.read_text(encoding="utf-8"))
        if master.get("stats", {}).get("claims") != len(claims):
            master.setdefault("stats", {})["claims"] = len(claims)
            master["last_updated"] = (
                datetime.now(timezone.utc).replace(microsecond=0)
                .isoformat().replace("+00:00", "Z")
            )
            write_if_changed(master_path, json.dumps(master, indent=2) + "\n", applied, dry)
        report.append("NOTE _INDEX.md not regenerated by backfill — the next ingest run refreshes it (Step 8)")
    finally:
        if not dry and lock.exists():
            lock.unlink()

    mode = "DRY-RUN" if dry else "APPLIED"
    print(f"== backfill-claims {mode} on {vault}")
    for line in report:
        print(f"  {line}")
    print(f"  -- {len([r for r in report if r.startswith('CLAIM')])} claims, "
          f"{len([r for r in report if r.startswith('EXCLUDE')])} excluded, "
          f"{len([r for r in report if r.startswith('SKIP')])} investigations skipped")
    if applied:
        print(f"  -- {len(applied)} file(s) {'would change' if dry else 'written'}:")
        for path in applied:
            print(f"     {path}")
    else:
        print("  -- no changes (idempotent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
