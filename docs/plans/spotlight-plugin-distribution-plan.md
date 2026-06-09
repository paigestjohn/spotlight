---
title: Spotlight Plugin Distribution Plan
status: draft
created: 2026-06-09
source_request: "Replicate the EveryInc compound-engineering-plugin distribution shape for Spotlight, using ce-plan."
---

# Spotlight Plugin Distribution Plan

## Problem Frame

Spotlight currently has two practical install paths:

1. `setup.html` generates a local installer with pinned dependencies and local config.
2. A user can point an agent at the GitHub repository and ask it to install the skill.

The second path is too informal. It depends on the agent discovering the right files, and it can blur the line between "install the skill" and "install unreviewed runtime packages." For OPSEC-sensitive users, especially journalists, the distribution contract should make that boundary explicit.

The EveryInc `compound-engineering-plugin` repository provides the pattern to copy:

- root marketplace manifests for Claude and `.agents` discovery,
- a canonical plugin payload under `plugins/<plugin-name>/`,
- per-target plugin metadata inside the payload,
- flat `skills/` and `agents/` directories inside the payload,
- contributor docs that clearly separate authoring context from runtime instructions,
- release/validation checks that keep marketplace manifests and plugin payload metadata in sync.

## RLM Prompt Clarification

Spotlight does not prompt during runtime preflight with "Do you want to use RLM?" RLM capability is selected at setup time:

- `setup.html` has an optional RLM checkbox and mode selector.
- `install-spotlight.sh` defaults to `SPOTLIGHT_INT_RLM=false` and `SPOTLIGHT_RLM_MODE=off`.
- when RLM is enabled, setup writes the RLM env/config values.
- runtime preflight reports integration availability/readiness; it does not ask an interactive yes/no question.
- Phase 2 methodology proposes RLM for the specific case only when setup enabled it and the configured mode is available.

Decision: keep RLM off by default and configuration-driven. The plugin install path should not introduce a preflight prompt. It should document that RLM is optional, requires the setup/runtime config path, and still requires per-case methodology approval before it runs.

## Goals

- Make Spotlight installable as a first-class plugin from the repository for Claude-style and `.agents`/Codex-style runtimes.
- Preserve the reviewed dependency boundary: plugin install loads skills/agents/docs; package installation remains in the pinned setup installer.
- Keep the setup page as the recommended full local install path for non-technical users.
- Make the GitHub "install this skill" path deterministic by exposing marketplace manifests and plugin metadata.
- Avoid stale duplicated skill payloads by generating or validating the plugin package from canonical source files.
- Add tests that fail on unpinned package installs, missing plugin metadata, manifest drift, or stale plugin payload files.

## Non-Goals

- Do not reintroduce Docker.
- Do not make plugin install silently run `npm install`, `pip install`, `uv tool install`, or similar package installs.
- Do not change the Spotlight investigation flow.
- Do not make RLM default-on.
- Do not publish to a public marketplace in this first pass unless the repository install flow works locally.

## External Reference Findings

Reference repository: <https://github.com/everyinc/compound-engineering-plugin>

Observed structure:

```text
.claude-plugin/
  marketplace.json
.agents/
  plugins/
    marketplace.json
plugins/
  compound-engineering/
    .claude-plugin/
      plugin.json
    .codex-plugin/
      plugin.json
    agents/
      *.md
    skills/
      */SKILL.md
    AGENTS.md
    CLAUDE.md
    README.md
```

Claude marketplace shape:

- root file: `.claude-plugin/marketplace.json`
- each plugin entry contains `name`, `description`, `author`, `homepage`, `tags`, and `source`
- `source` points to `./plugins/compound-engineering`

`.agents` marketplace shape:

- root file: `.agents/plugins/marketplace.json`
- each plugin entry contains `name`, nested local `source`, `policy`, and `category`
- the local source points to `./plugins/compound-engineering`
- install policy is explicit, using `installation` and `authentication`

Payload metadata shape:

- Claude payload metadata lives at `plugins/compound-engineering/.claude-plugin/plugin.json`
- Codex payload metadata lives at `plugins/compound-engineering/.codex-plugin/plugin.json`
- the Codex metadata includes `skills: "./skills/"` plus an `interface` block with display name, descriptions, category, capabilities, website URL, default prompts, and screenshots.

Important lesson from EveryInc contributor docs: root `AGENTS.md`/`CLAUDE.md` are authoring context. Runtime behavior must live inside installed skill files and their references, because installed users run against their own project instructions.

## Proposed Spotlight Structure

Add a plugin distribution layer without moving the canonical source files yet:

```text
.claude-plugin/
  marketplace.json
.agents/
  plugins/
    marketplace.json
plugins/
  spotlight/
    .claude-plugin/
      plugin.json
    .codex-plugin/
      plugin.json
    agents/
      *.md
    skills/
      */SKILL.md
    docs/
      *.md
    integrations/
      */integration.md
      */manifest.json
    schemas/
      *.json
    AGENTS.md
    CLAUDE.md
    README.md
scripts/
  build-plugin-payload.py
tests/
  plugin-distribution-check.py
```

The canonical authoring sources remain:

- `skills/`
- `agents/`
- `docs/`
- `integrations/`
- `schemas/`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `VALIDATED_DEPENDENCIES.md`

The generated payload under `plugins/spotlight/` should be deterministic and validated, not hand-maintained.

## Key Decisions

### Decision 1: Plugin Install Is Skills, Not Runtime Packages

Plugin installation should install Spotlight's agent-facing instructions and metadata. It should not install runtime dependencies. Runtime dependencies stay behind the existing pinned setup path.

Rationale: this directly addresses the supply-chain concern. If an agent points at GitHub and installs the plugin, it should not fetch new PyPI/npm packages. If a user wants Firecrawl, Maigret, RLM, browser automation, or other executable tooling, they use the setup page or a documented pinned install command.

### Decision 2: Keep Setup Page as Full Install Path

`setup.html` remains the recommended path for users who need a working local Spotlight runtime. It should link or explain plugin install as "agent instructions only" and setup install as "agent instructions plus reviewed local runtime dependencies."

Rationale: plugin systems are good at distributing skills, but they are not a clean OPSEC answer for package review. The setup path is where dependency pinning and user consent belong.

### Decision 3: Generate the Payload

Add a payload builder that copies an allowlisted set of files into `plugins/spotlight/`. The builder should exclude local cases, secrets, transient outputs, stale Docker files, caches, and any test fixtures that are not needed at runtime.

Rationale: duplicated skill payloads go stale quickly. A builder plus validator makes the plugin package auditable.

### Decision 4: Validate Manifest Parity

Add a test that checks:

- `.claude-plugin/marketplace.json` points to `./plugins/spotlight`
- `.agents/plugins/marketplace.json` points to `./plugins/spotlight`
- `plugins/spotlight/.claude-plugin/plugin.json` and `plugins/spotlight/.codex-plugin/plugin.json` share name/version/description
- Codex `skills` points to `./skills/`
- declared skills directory exists
- no plugin metadata points outside the repository

Rationale: marketplace manifests are easy to break with small edits.

### Decision 5: Surface RLM as Optional Capability, Not Preflight Prompt

The payload README and setup page should say RLM is optional and off by default. The plugin should not ask users to enable RLM during preflight. If setup enabled RLM, Spotlight should propose it during methodology approval and run it only after the user approves it for that case.

Rationale: RLM needs local model/runtime choices and should not be activated accidentally by a skill install.

## Implementation Units

### Unit 1: Confirm Manifest Contracts and Create Baseline Metadata

Files:

- `.claude-plugin/marketplace.json`
- `.agents/plugins/marketplace.json`
- `plugins/spotlight/.claude-plugin/plugin.json`
- `plugins/spotlight/.codex-plugin/plugin.json`
- `plugins/spotlight/README.md`

Work:

- Mirror the EveryInc marketplace structure for one plugin named `spotlight`.
- Use conservative metadata:
  - category: `Research` or `Productivity` depending on runtime expectations.
  - capabilities: `Interactive`, `Read`, `Write`.
  - no default prompt that causes package installation.
- Include a short README that distinguishes "plugin install" from "full local setup."

Test scenarios:

- Claude marketplace manifest resolves `spotlight` to `./plugins/spotlight`.
- `.agents` marketplace manifest resolves `spotlight` to `./plugins/spotlight`.
- Codex plugin metadata declares `skills: "./skills/"`.
- Plugin README contains the dependency boundary: no runtime package install is implied.

### Unit 2: Build Deterministic Plugin Payload Sync

Files:

- `scripts/build-plugin-payload.py`
- `tests/plugin-distribution-check.py`
- `plugins/spotlight/skills/`
- `plugins/spotlight/agents/`
- `plugins/spotlight/docs/`
- `plugins/spotlight/integrations/`
- `plugins/spotlight/schemas/`
- `plugins/spotlight/AGENTS.md`
- `plugins/spotlight/CLAUDE.md`
- `plugins/spotlight/VALIDATED_DEPENDENCIES.md`

Work:

- Add a script that copies allowlisted runtime files into `plugins/spotlight/`.
- Make the script deterministic by removing and rebuilding only the generated payload subtrees.
- Preserve per-target plugin metadata while syncing runtime files.
- Add a generated marker file so reviewers can tell what is source and what is generated.

Test scenarios:

- Running the builder twice produces no diff.
- The plugin payload contains every `skills/*/SKILL.md` file expected for Spotlight.
- The payload does not contain `cases/`, `.env`, `.venv`, `.firecrawl`, Docker files, or stale sandbox docs.
- Every copied skill reference path resolves inside its copied skill directory.

### Unit 3: Preserve Reviewed Dependency Pins Across Install Surfaces

Files:

- `VALIDATED_DEPENDENCIES.md`
- `install-spotlight.sh`
- `setup.html`
- `plugins/spotlight/README.md`
- `plugins/spotlight/VALIDATED_DEPENDENCIES.md`
- `tests/dependency-pins-check.py`
- `tests/plugin-distribution-check.py`

Work:

- Keep `VALIDATED_DEPENDENCIES.md` as the canonical dependency review ledger.
- Make the plugin README point users to setup for runtime installation.
- Add checks that the plugin payload does not contain executable install snippets with unpinned packages.
- Ensure setup-generated install commands use exact versions already validated.

Test scenarios:

- Dependency pin check passes for setup and installer.
- Plugin payload has no unpinned `pip install <package>`, `npm install <package>`, `uv tool install <package>`, or `npx <package>` commands.
- Any dependency mentioned in plugin docs either has an exact pin or is explicitly described as user-provided/external.

### Unit 4: Documentation and Setup Page Alignment

Files:

- `README.md`
- `setup.html`
- `docs/runtimes.md`
- `docs/integrations.md`
- `plugins/spotlight/README.md`

Work:

- Add a "Plugin Install" section to `README.md` explaining the two install modes:
  - setup page: full local install with reviewed/pinned dependencies.
  - plugin install: agent-facing skills and docs only.
- Update `setup.html` copy so users understand it is the pinned dependency path.
- Keep the removed agent prompt path out of the setup page.
- Mention RLM is optional/off by default, enabled only by setup/config, and approved per case during methodology.

Test scenarios:

- `tests/setup-generator-check.js` still confirms no agent prompt path is present.
- Documentation uses "plugin install" only for the skills/docs payload.
- Documentation uses "setup install" for local dependency installation.
- RLM documentation does not imply preflight asks users to enable it.
- RLM documentation states that methodology approval is the per-case opt-in point.

### Unit 5: CI and Local Verification

Files:

- `.github/workflows/ci.yml`
- `tests/smoke.sh`
- `tests/plugin-distribution-check.py`
- `tests/dependency-pins-check.py`

Work:

- Add plugin-distribution validation to smoke tests.
- Keep dependency pin validation in smoke tests.
- Add JSON parse checks for all plugin manifests.
- Fail CI when generated plugin payload is stale.

Test scenarios:

- `python3 tests/plugin-distribution-check.py`
- `python3 tests/dependency-pins-check.py`
- `node tests/setup-generator-check.js`
- `bash tests/smoke.sh`
- `bash tests/eval.sh`

## Acceptance Criteria

- A user or agent can discover Spotlight through `.claude-plugin/marketplace.json`.
- A user or agent can discover Spotlight through `.agents/plugins/marketplace.json`.
- Both manifests point to one canonical payload: `plugins/spotlight/`.
- The payload includes Spotlight skills, agents, documentation, integrations, schemas, and dependency review notes.
- The payload does not include secrets, case data, caches, Docker files, or generated investigation outputs.
- Plugin install does not install runtime packages.
- Setup install remains the path that installs pinned runtime dependencies.
- Tests catch stale payloads, manifest drift, unpinned installs, and RLM copy that implies interactive preflight enablement.

## Adversarial Review Notes

Failure scenario: an agent sees `plugins/spotlight/README.md`, tries to be helpful, and installs Maigret or other packages without pins.

Countermeasure: plugin docs must explicitly say "do not install runtime packages from plugin install; use setup for pinned dependencies." Add test scanning plugin docs for unpinned package install commands.

Failure scenario: duplicated `skills/` under `plugins/spotlight/` drifts from root `skills/`.

Countermeasure: generate the payload and add a stale-payload check.

Failure scenario: RLM becomes accidentally enabled because a default prompt says "run Spotlight with RLM."

Countermeasure: no default prompt should enable RLM. RLM remains setup/config-gated and methodology-approved per case.

Failure scenario: marketplace metadata claims a capability that the payload does not support.

Countermeasure: keep capabilities conservative: interactive/read/write only. Do not claim network, model, browser, or package management capabilities in plugin metadata.

Failure scenario: users confuse plugin install with full setup and expect Firecrawl/Maigret/RLM commands to work.

Countermeasure: docs must use two names consistently: "plugin install" and "setup install."

## Sequencing

1. Create plugin metadata and a minimal hand-built payload.
2. Add the payload builder and make it reproduce the hand-built payload.
3. Add manifest/payload validation tests.
4. Update docs and setup copy.
5. Run smoke, eval, setup generator, dependency pin, and plugin-distribution checks.
6. Only after local install works, decide whether to publish to a public marketplace or keep GitHub-source install as the supported path.

## Open Questions

- Which category should `.agents` use: `Research`, `Productivity`, or `Coding`? The EveryInc plugin uses `Coding`; Spotlight is better described as `Research` if the target registry allows it.
- Should Spotlight ship any custom subagents as native `agents/*.md` files now, or should the first plugin version ship only skills and docs?
- Should release versioning be manual for now, or should a release-please style validator be added before public publishing?
- What exact public GitHub repository URL should be used in metadata once this local work is ready to push?
