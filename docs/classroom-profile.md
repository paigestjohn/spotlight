---
title: "Spotlight Classroom Profile"
description: "Classroom-ready profile of the main Spotlight skill: keep multi-agent cycles and HTML review, skip vault/monitoring/ingestion/provenance."
type: tool-spec
status: draft
created: 2026-05-20
updated: 2026-05-20
tags: [tools, spotlight, teaching, firecrawl, antigravity, classroom-profile]
---

# Spotlight Classroom Profile

This replaces the idea of a separate `spotlight-lite` repo. The teaching version should be a **profile flag inside the main Spotlight skill**, not a fork or mirror.

## Decision

Use one canonical Spotlight skill with a runtime profile:

```text
SPOTLIGHT_PROFILE=classroom
```

or an explicit prompt instruction:

```text
Run Spotlight in classroom profile.
```

The classroom profile keeps the core investigation machinery:

- brief
- methodology
- multi-cycle investigator execution
- independent fact-checker pass
- editorial readiness check
- local HTML review/report

It skips the infrastructure-heavy phases:

- vault loading
- QMD / Obsidian
- vault ingestion
- Scoutpost monitor creation
- provenance signing
- long-term knowledge storage
- optional vendor integrations unless already configured

## Why This Is Better Than A Mirror Repo

A separate `spotlight-lite` repository would drift. Any change to grounding, fact-checking, review HTML, acquisition rules, or agent prompts would need to be copied manually.

The classroom profile keeps **one source of truth**: the main Spotlight skill. The class simply changes which phases run.

## Profile Behavior

### Full profile

Run all phases:

```text
brief -> methodology -> investigation cycles -> fact-check cycles -> Gate 1 -> provenance -> review.html -> monitoring -> ingestion
```

### Classroom profile

Run only:

```text
brief -> methodology -> investigation cycles -> fact-check cycles -> Gate 1 summary -> review.html
```

Write only local files under the student's current course folder.

## Phase Rules

Add profile gates to the main `skills/spotlight/SKILL.md`:

```text
If profile == classroom:
  - Set VAULT_PATH="none" unless explicitly provided.
  - Do not query vault.
  - Do not write vault notes.
  - Do not run ingestion.
  - Do not create Scoutpost monitors.
  - If monitoring recommendations exist, list them only.
  - Do not run provenance signing.
  - Generate the local HTML review/report.
```

The investigator and fact-checker agents still run. Their output remains useful:

- `findings.json`
- `fact-check.json`
- `evidence-bundle.json`
- `investigation-log.json`
- `summary.md`
- `review.html`

## Firecrawl Integration

Default classroom path:

```text
Antigravity agent
→ Spotlight skill in classroom profile
→ Firecrawl MCP or API/CLI fallback
→ local course folder
→ review.html
```

Prefer Firecrawl MCP/API where the desktop app exposes it. Keep CLI fallback for instructor machines, but do not teach students Firecrawl commands.

If subagents cannot access Firecrawl tools directly, the orchestrator should acquire sources first and pass local files to investigator/fact-checker.

## Antigravity Class Installation

Use the canonical Spotlight repository, not a copied single `SKILL.md`. The orchestrator depends on `AGENTS.md`, agent prompts, skills, schemas, and review templates in the repo.

Canonical source:

```text
https://github.com/buriedsignals/spotlight.git
```

Use project-scoped skills when possible. If Antigravity supports a workspace skill path, install the Spotlight skill into that workspace scope. If the exact workspace-skill path is unavailable or unstable, keep the full Spotlight checkout inside the course folder and have the student prompt reference the local files directly.

Target shape:

```text
ai-journalism-class/
  .spotlight/
    AGENTS.md
    agents/
    skills/
    schemas/
    scripts/
  01-scrape/
  02-osint-map/
  03-fact-check/
  04-parse-extract/
  05-data-cleaning/
  06-spotlight/
```

The class should prefer workspace/local scope so students do not alter global agent behavior. The prompt must explicitly scope all writes to the current course folder.

## Student Prompt

The final class prompt should be short:

```text
Pull Spotlight from https://github.com/buriedsignals/spotlight.git into `.spotlight/` in this course folder if it is not already present.

Use the Spotlight skill from `.spotlight/skills/spotlight/SKILL.md` in classroom profile.

Scope: this current course folder only.
Use the sources, documents, CSVs and HTML outputs from folders 01 to 05.
Keep investigator/fact-checker cycles.
Skip vault loading, QMD/Obsidian, vault ingestion, monitoring creation and provenance signing.
Generate 06-spotlight/report.html.
Respond in French.
```

## Maintenance

Do not maintain a second skill file by hand.

Maintain the main Spotlight skill and add a small profile test:

```text
Run Spotlight on demo-temps in classroom profile.
Assert that review.html is created.
Assert that no vault, monitoring, ingestion or provenance files are created.
```

If a generated classroom export is useful later, generate it from the canonical skill with a script:

```text
scripts/build-classroom-profile.py
```

But the primary strategy remains: one skill, profile flag, phase gates.
