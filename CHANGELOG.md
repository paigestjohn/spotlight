# Changelog

All notable changes to Spotlight. Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

> **Next tag will be [2.0.0]** (SemVer major bump): the `grounding` object schema
> drops three fields and `findings.sources` demotes three required fields to
> optional. Both are breaking changes for downstream consumers parsing
> `cases/{project}/data/findings.json`, `fact-check.json`, or
> `provenance-manifest.json`. The classroom profile flag is also removed.

### Removed

- **Classroom profile flag.** `SPOTLIGHT_PROFILE=classroom` is no longer
  recognised. The main investigation flow (brief → methodology → multi-cycle
  investigator → fact-checker → Gate 1 → HTML review → ingestion) is the only
  path; runtime is independent of teaching vs newsroom context. Removed
  `docs/classroom-profile.md`, `tests/classroom-profile-check.py`, the
  classroom test in `tests/eval.sh`, and 16 conditional branches in
  `skills/spotlight/SKILL.md`. Reason: profile-as-flag added cognitive load
  for a single concrete use case; if classroom needs return, document them
  in a separate teaching profile rather than as a runtime branch.

### Changed (breaking)

- **`grounding` object trimmed from 10 fields to 7.** Removed
  `grounding_strength` (overlapped `support_type`: `direct` → `full`,
  `insufficient` → `none`), `quote_match` (implied by `support_type` +
  `source_role`), and `contradictions` array (merged into the existing
  free-text `grounding_rationale`). Same trim applied to
  `grounding_assessment` in `fact-check.schema.json` (dropped
  `grounding_strength` and `contradiction_search` — the latter merged into
  `assessment`). Updated:
  `schemas/findings.schema.json`, `schemas/fact-check.schema.json`,
  `skills/epistemic-grounding/SKILL.md`, `skills/review/SKILL.md`,
  `skills/review/references/template.html`,
  `skills/spotlight/references/evidence-grounding.md`,
  `agents/investigator.md`, `agents/fact-checker.md`,
  `scripts/build-provenance-manifest.py`, and all fixtures + tests.
  Reason: the dropped fields were redundant by construction; the cross-check
  theory ("two angles catch errors") did not earn its keep in practice and
  was creating write-fatigue and lower-quality fills.
- **`findings.sources` required fields reduced.** `archive_url`,
  `access_method`, and `local_file` demoted from required to optional in
  `schemas/findings.schema.json`. Same demotion for `archive_url` and
  `access_method` in `fact-check.schema.json`'s `evidence_item`. Reason: in
  practice these are best-effort fields that the validator does not enforce
  presence of. Schema contract now matches actual behaviour.
- **`findings.lead` demoted from required to optional.** Top-level `lead` is
  no longer required in `findings.schema.json`. It remains available as an
  optional field. Reason: never consumed by any renderer or validator;
  required-ness was aspirational.

### Changed (non-breaking)

- **`provenance-manifest.schema.json` cleanup.** `signing.credential_id` and
  `signing.endpoint` removed from `required` array (they were required but
  typed as `["string", "null"]`, which is contradictory). Now properly
  optional. `claim.grounding_strength` replaced with `claim.support_type`
  for vocabulary consistency with `findings.grounding.support_type`.
- **Integrations roadmap moved out of skill.**
  `skills/integrations/SKILL.md` no longer carries the "Current deferred
  integrations" bullet list. Moved to `docs/integrations-roadmap.md` with
  an activation checklist. Skill is leaner; roadmap stays tracked.

### Changed (earlier in [Unreleased])

- Monitoring ownership split is now explicit:
  - `mycroft` owns passive feed polling, scoring, deduplication, and topic-linked signal storage
  - `spotlight` owns investigation-scoped monitoring orchestration and case linkage
  - `scoutpost` remains unchanged and is used through existing `projects`, `scouts`, and `units` surfaces
- Spotlight no longer ships the legacy `monitoring/feeds/` framework.
- `cases/{project}/data/monitoring.json` is now treated as an external-monitor registry rather than a feed-execution config.

### Added

- `spotlight/monitoring/registry.py` for initializing, normalizing, and migrating `monitoring.json` to schema v2.
- `integrations/scoutpost/` as the default durable-monitor integration surface.
- `mycroft/monitoring/` as the passive-monitor single source of truth, including `poll`, `query`, `preflight`, `topic`, and `prune`.
- Installer-generated `spotlight-doctor` and `spotlight-update` wrappers. Manual updates now fetch `origin/main`, fast-forward only, and run doctor.
- QMD setup in the installer, including automatic registration of the selected vault as the `spotlight` collection.

### Fixed

- Agent setup ZIP now includes local form-provided API key values in the private manifest and instructs local agents to write `.env` without printing secrets.
- Local runtime launch now routes through `spotlight-local` instead of the old `pi` fallback.
- Installer shell startup block is replaced on rerun, so changed runtime, install path, or vault path choices are reflected.

## [1.0.0] — 2026-04-17

Initial public release. Runtime-agnostic OSINT investigation system for journalists.

### Included

- **11 skills**: orchestrator (`spotlight`), `review`, `integrations`, `ingest`, `monitoring`, `web-archiving`, `content-access`, `osint`, `investigate`, `follow-the-money`, `social-media-intelligence`
- **2 agents**: `investigator` (PLANNING + EXECUTION modes), `fact-checker` (independent SIFT methodology)
- **5 JSON schemas**: findings, fact-check, methodology, investigation-log, summary — all `schema_version: "1.0"`
- **5 feed sources**: GDELT, RSS investigative (Bellingcat, ICIJ, Intercept, Crisis Group), RSS regional (17 outlets), GDACS, ACLED
- **3 external integrations**: browser-use, Junkipedia, OSINT Navigator
- **Runtime support**: pi (default for Local mode), Claude Code, Gemini, Codex, OpenCode (OpenRouter / Fireworks / Together)
- **Six readiness criteria** enforced before Gate 1
- **Post-Gate-1 review loop** via self-contained `review.html` artifact
- **Sensitive mode** strips network verbs for local-only investigations
- **One-click install** via `setup.html` — copy-paste or download-and-run
- **`spotlight` shell command** with `update`, `doctor`, `help` subcommands

### Documentation

- 8 user-facing docs under `docs/` (README, structure, runtimes, integrations, investigating, fact-checking, monitoring, recovery)
- `CONTRIBUTING.md` with drop-in patterns for new runtimes, integrations, feed sources, skills
- `DISCLAIMER.md` — editorial responsibility, OPSEC scope, third-party ToS, data handling
- `LICENSE` — MIT, with methodology attributions to Bellingcat, GIJN, Jim Shultz, Jay Amditis, OCCRP/ICIJ

### Tests

- `tests/smoke.sh` — structural integrity (27+ checks, <2s)
- `tests/eval.sh` — contract compliance + sample data validation
- CI via GitHub Actions on every push + PR

### Attribution

Methodology synthesized from:
- Bellingcat training materials (investigate skill)
- GIJN publications (follow-the-money skill)
- Jim Shultz, *Follow the Money* (Revenue Watch / Open Society Institute, 2005)
- Jay Amditis, [claude-skills-journalism](https://github.com/jamditis/claude-skills-journalism) — MIT (web-archiving, content-access, social-media-intelligence)
- Derek Bowler, EBU Eurovision News Spotlight (follow-the-money)
- OCCRP / ICIJ investigative practice

### Known limitations

- Fine-tuned journalism model not yet published on Hugging Face — Local mode installer warns gracefully
- Windows native not supported — WSL required
- OSINT Navigator requires application approval for API access
- Junkipedia access is application-based

### Deferred for future releases

- Integrations: Serus AI, Thinkpol, Reality Defender, Klarety, Scoutpost (awaiting API access or access approval)
- Agent eval harness with real LLM-backed test scenarios
- Release automation + signed installers
- i18n for review.html

---

_Format notes: entries include breaking changes (`!:`), new features (`feat:`), fixes (`fix:`), docs (`docs:`), refactors (`refactor:`), chores (`chore:`). See `CONTRIBUTING.md` for commit-message conventions._
