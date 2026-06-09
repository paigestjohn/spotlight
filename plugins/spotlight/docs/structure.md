# Structure

This doc describes the repo layout: what's where, why, and how the pieces connect. If you want to add a skill, monitoring backend, schema, or runtime adapter, start here.

## Top-level layout

```
spotlight/
├── AGENTS.md                 # Runtime contract — verb registry, agent manifests, skill registry
├── README.md                 # Humans-first entry doc (quick-start per runtime)
├── setup.html                # Browser-based installer — picks runtime, collects keys, generates install script
├── .spotlight-config.json    # Per-session config (search library, vault path, cases root, runtime)
├── .gitignore
├── schemas/                  # JSON schemas — 6 case files, all schema_version 1.0
├── skills/                   # 14 skills (pi-native SKILL.md format)
├── agents/                   # 2 agent prompt bundles (investigator + fact-checker)
├── integrations/             # External tool integrations (dev-browser, Junkipedia, Noosphere C2PA, OSINT Navigator, Unpaywall)
├── docs/                     # You are here. Operator manual.
├── monitoring/               # Case-level monitor registry helper + leads queue
└── cases/                    # Per-investigation output (gitignored)
```

## AGENTS.md — the runtime contract

`AGENTS.md` is loaded by every runtime at session start. It declares:

1. **13-verb registry** — the abstract tool vocabulary every skill instruction uses
2. **Agent manifests** — `investigator` and `fact-checker` with `allowed_verbs`, `iteration_limit`, `preferred_model`
3. **Skill registry** — 14 skills with IDs, paths, and which agents can invoke them
4. **Cases directory structure** — `{CASE_DIR}/{data,research}/` convention
5. **Schema reference** — pointers to `schemas/*.json`
6. **Sensitive mode** — toggle that strips `fetch`/`search` from allowed_verbs

### The 13 verbs

| Verb | Signature | Semantics |
|---|---|---|
| `fetch` | `fetch(url, output_path)` | Scrape URL, save file. Backing: `firecrawl scrape` |
| `search` | `search(query, output_path, limit)` | Web search, save results. Backing: `firecrawl search` |
| `read-file` | `read-file(path)` | Read file contents |
| `write-file` | `write-file(path, content)` | Write file (full overwrite) |
| `edit-file` | `edit-file(path, old, new)` | Targeted string replacement |
| `list-files` | `list-files(pattern)` | Glob / pattern match |
| `grep-files` | `grep-files(pattern, path)` | Regex search file contents |
| `execute-shell` | `execute-shell(command)` | Run shell command, return stdout+stderr |
| `spawn-agent` | `spawn-agent(agent_id, prompt, config)` | Launch sub-agent |
| `wait-agent` | `wait-agent(handle)` | Block until agent completes |
| `invoke-skill` | `invoke-skill(skill_id)` | Load skill instructions into context |
| `query-vault` | `query-vault(vault_path, query)` | Search vault (backing: `qmd query`) |
| `vault-write` | `vault-write(vault_path, note_path, content)` | Write vault note + update registry |

These are **abstract** — the runtime adapter binds each to a concrete tool. See [integrations.md](integrations.md) for per-runtime mappings.

## schemas/ — 6 case files

Every case file validates against a schema. All declare `schema_version: "1.0"`.

| Schema | Case file | Role |
|---|---|---|
| `findings.schema.json` | `{CASE_DIR}/data/findings.json` | Investigator output — claims, evidence, sources, confidence, perspective, monitoring_recommendations |
| `fact-check.schema.json` | `{CASE_DIR}/data/fact-check.json` | Fact-checker output — per-claim verdicts, evidence_for/against, gaps_for_next_cycle |
| `methodology.schema.json` | `{CASE_DIR}/data/methodology.json` | Investigator PLANNING output — investigation_plan, tools_required, opsec_considerations |
| `evidence-bundle.schema.json` | `{CASE_DIR}/data/evidence-bundle.json` | Acquisition artifacts, missing-source gates, hashes, and claim links |
| `investigation-log.schema.json` | `{CASE_DIR}/data/investigation-log.json` | Append-only cycle audit trail |
| `summary.schema.json` | `{CASE_DIR}/data/summary.json` | Gate 1 summary |

Validate a case file:

```bash
python3 -m jsonschema -i {CASE_DIR}/data/findings.json schemas/findings.schema.json
```

## skills/ — 14 skills

Each skill is a directory with `SKILL.md` (+ optional `references/*.md` for large supporting content).

### Orchestrator skill

- **`spotlight`** — the investigation orchestrator. Phase 0 preflight → Brief → Methodology → Execution cycles (max 5) → Gate 1 → Ingestion. Invokes investigator and fact-checker as agents.

### Pipeline-support skills (invocable by orchestrator)

- **`review`** — post-Gate-1 HTML review artifact. Renders a self-contained `{CASE_DIR}/review.html` the journalist opens in any browser, submits structured feedback, downloads as JSON. Mode B re-spawns the investigator to process the feedback and regenerates the HTML. No server required.
- **`integrations`** — routing layer for external tool integrations (dev-browser, Junkipedia, Noosphere C2PA, OSINT Navigator, Unpaywall). Reads live preflight status, maps investigation tasks to integrations. See `integrations/` at repo root for manifests + per-integration usage docs.
- **`ingest`** — archival from case files to vault. 7-step process with `.ingest-lock` concurrency and directory fallback.
- **`monitoring`** — case-level monitoring orchestration. Coordinates Mycroft passive signals, Scoutpost durable monitors, and runtime-native fallbacks.
- **`acquisition-graduation`** — turns repeated dev-browser acquisition successes into durable source/domain guidance without secrets or brittle session details.

### Agent-support skills (invocable by investigator / fact-checker)

- **`web-archiving`** — Wayback → Archive.today → local scrape hierarchy. Chain of custody blocks.
- **`content-access`** — 8-step paywall hierarchy. `access_method` enum.
- **`epistemic-grounding`** — claim-to-evidence grounding, confidence caps, and failure routing for weak or adjacent evidence.
- **`shell-safety`** — safe command construction, validation helpers, and destructive-operation probe rules.
- **`osint`** — tool routing table + 150-tool catalog + OSINT Navigator integration.
- **`investigate`** — step-by-step techniques (geolocation, person, platform, verification, transport).
- **`follow-the-money`** — financial methodology (UBO, offshore, budget, assets).
- **`social-media-intelligence`** — account authenticity, coordination detection, narrative tracking.

### Per-skill anatomy

```
skills/<id>/
├── SKILL.md           # YAML frontmatter + instructions (how the skill works)
└── references/        # Optional — deep reference content the SKILL.md points to
    └── *.md
```

SKILL.md frontmatter:

```yaml
---
name: <skill-id>
description: <one-line>
version: "1.0"
invocable_by: [orchestrator | investigator | fact-checker | user]
requires: [<other-skill-id>]    # optional
env_vars: [ENV_VAR_1]           # optional
---
```

The body is instructions for the runtime's model: what to do when invoked, which other skills to invoke, which verbs to call, what output to produce.

## agents/ — 2 prompt bundles

Unlike skills (which are invoked), agents are **spawned**. Their markdown files are prompt bundles consumed by `spawn-agent`.

- **`investigator.md`** — two modes: `PLANNING` (writes `methodology.json`) and `EXECUTION` (writes `findings.json` + appends `investigation-log.json`). Iteration limit 80. Loads skills acquisition-graduation, osint, investigate, follow-the-money, web-archiving, content-access, epistemic-grounding, shell-safety, social-media-intelligence.
- **`fact-checker.md`** — SIFT methodology, verdict taxonomy, independent from investigator. Iteration limit 50. Loads skills osint, web-archiving, content-access, epistemic-grounding, shell-safety. Cannot `spawn-agent` (no recursive spawning).

Frontmatter declares `allowed_verbs`, `preferred_model` (per-runtime mapping), `vault_context` (whether to query the vault before research).

## monitoring/ — case registry helpers

Spotlight no longer ships a passive feed engine. Passive polling lives in Mycroft; durable always-on scouts live in Scoutpost. Spotlight keeps only the investigation-scoped linkage and handoff state.

```
monitoring/
├── registry.py               # CLI helper for {CASE_DIR}/data/monitoring.json
├── alerts/                   # Optional local alert artifacts / future hooks
└── leads/                    # Scraping queue (monitor → case handoff)
```

`registry.py` owns the local `monitoring.json` shape:

- initialize a v2 external-monitor registry for a case
- normalize or migrate legacy feed-oriented `monitoring.json`
- record linked Mycroft topic slugs
- record linked Scoutpost `project_id` and `scout_id` values
- record runtime-native fallback handles and resume-time checks

See [monitoring.md](monitoring.md) for the lifecycle and registry fields.

## cases/ — investigation output

Every investigation creates an isolated working directory. Gitignored. This is
not the knowledge vault. Spotlight queries the vault when a case starts and
ingests verified material into the vault only after an explicit end-of-case
decision.

```
{CASE_DIR}/
├── brief-directions.txt      # User-approved brief (Phase 1)
├── summary.md                # Gate 1 summary (markdown, human-readable)
├── data/
│   ├── methodology.json
│   ├── findings.json
│   ├── fact-check.json
│   ├── investigation-log.json
│   ├── summary.json
│   └── monitoring.json       # optional external-monitor registry
└── research/
    ├── *.md                  # Scraped web content
    ├── *.json                # Search results
    └── archived/             # Wayback / Archive.today preservation
```

## .spotlight-config.json

Per-machine config created during Phase 0. Fields:

```json
{
  "search_library": "firecrawl",
  "vault_path": "/Users/you/Documents/intelligence/",
  "vault_type": "obsidian|tolaria|directory",
  "case_workspace_root": "/Users/you/Documents/Spotlight/cases",
  "cases_root": "/Users/you/Documents/Spotlight/cases",
  "integrations": {
    "osint_navigator": {
      "status": "unknown",
      "checked_at": "<ISO timestamp>",
      "source": "setup",
      "required_in_phase_2": false,
      "reason": "preflight not run yet"
    }
  },
  "created_at": "ISO 8601",
  "last_used": "ISO 8601",
  "active_project": "<slug>"
}
```

This file is gitignored — each user's config is local.

## How to extend

| Extension | Where | What to write |
|---|---|---|
| New skill | `skills/<new-id>/SKILL.md` | YAML frontmatter + body. Add row to `AGENTS.md` skill registry |
| New monitoring backend | `integrations/<new-id>/` or Mycroft | Integration manifest + usage doc, or Mycroft passive-feed update. Update `skills/monitoring/` references accordingly |
| New schema | `schemas/<new>.schema.json` | Draft-07 JSON Schema with `schema_version: "1.0"`. Update `AGENTS.md` schema reference |
| New runtime adapter | `docs/integrations.md` | New section with verb mapping, sub-agent strategy, sensitive-mode enforcement |
| New agent | `agents/<new-id>.md` | YAML frontmatter with `allowed_verbs`, `iteration_limit`, `preferred_model`. Add to `AGENTS.md` agent manifest. Consider: does this agent need a corresponding agent-support skill? |

Changes to the 13-verb registry are breaking and require bumping `runtime_version` in `AGENTS.md`. All other extensions are additive.

## See Also

- [epistemic-grounding.md](epistemic-grounding.md) — claim-to-evidence grounding and evidence bundles.
- [vulnerabilities.md](vulnerabilities.md) — shell-safety risk model and mitigations.
