#!/usr/bin/env python3
"""Regression checks for the Spotlight classroom profile contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "spotlight" / "SKILL.md"


def main() -> int:
    text = SKILL.read_text(encoding="utf-8")

    required_fragments = [
        'SPOTLIGHT_PROFILE=classroom',
        'profile = "classroom"',
        'Set `VAULT_PATH="none"`',
        'Do not query a vault.',
        'Do not write vault notes.',
        'Do not run ingestion.',
        'Do not create Scoutpost, Mycroft, or other durable monitors.',
        'Do not run provenance signing.',
        'skip persistent config writes',
        'skip provenance packaging and signing',
        'skip this phase. End after the local HTML review/report',
    ]

    missing = [fragment for fragment in required_fragments if fragment not in text]
    if missing:
        print("Missing classroom profile contract fragments:")
        for fragment in missing:
            print(f"- {fragment}")
        return 1

    planning_pos = text.find("MODE: PLANNING")
    execution_pos = text.find("MODE: EXECUTION")
    fact_checker_pos = text.find('agent_id: "fact-checker"')
    if min(planning_pos, execution_pos, fact_checker_pos) < 0:
        print("Could not locate all agent prompt blocks")
        return 1

    for label, pos in [
        ("planning prompt", planning_pos),
        ("execution prompt", execution_pos),
        ("fact-checker prompt", fact_checker_pos),
    ]:
        window = text[pos : pos + 1800]
        if "PROFILE: {profile}" not in window:
            print(f"{label} does not pass profile to the agent")
            return 1
        if "CLASSROOM PROFILE:" not in window:
            print(f"{label} does not include classroom constraints")
            return 1

    monitoring_pos = text.find("Process monitoring recommendations")
    if monitoring_pos < 0:
        print("Could not locate monitoring recommendation phase")
        return 1
    monitoring_window = text[monitoring_pos : monitoring_pos + 1200]
    if 'profile == "classroom"' not in monitoring_window:
        print("Monitoring phase is not gated by classroom profile")
        return 1
    if 'invoke-skill("monitoring")' not in monitoring_window:
        print("Full profile monitoring path disappeared")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
