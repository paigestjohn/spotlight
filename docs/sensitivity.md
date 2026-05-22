# Sensitivity — protecting sensitive material in mixed-runtime investigations

Status: design doc — not yet implemented.
Author: design pass following installer/RAM cleanup work in PR #28.

---

## What this protects against

A Spotlight investigation often mixes two kinds of evidence:

- **Open** material: corporate filings, archived web pages, public records,
  press coverage, scraped social posts. Safe to expose to a frontier model
  (Claude, Gemini, OpenAI) because exposure to the provider is acceptable
  — the material is already public.
- **Sensitive** material: source-protected documents, leaks, off-record
  interview notes, unpublished tip identities. Exposure to *any* third
  party is unacceptable — legally, ethically, or both.

The leak vector this document is designed to close is **knowledge-base
search at the start of a new case**. Spotlight's ingest skill writes
investigation outputs into a markdown vault, which QMD indexes. The next
investigation's agent searches that index during methodology and execution.
If sensitive content has been ingested into the same index the frontier
runtime queries, the frontier provider sees sensitive content the moment
QMD returns a matching chunk. That is the failure mode this design exists
to eliminate.

## What this does not protect against

This is not a counter-intelligence system. It does not protect against:

- A compromised local machine (rootkit, malware, physical access).
- A journalist deliberately copying sensitive content into the open store.
- Sensitive content arriving in screenshots, OCR'd PDFs, or other forms the
  ingest skill cannot inspect.
- Provider-side data retention from an *earlier* frontier session that
  legitimately handled material later reclassified as sensitive.
- Adversaries with subpoena power against the journalist or the providers.

If your threat model includes any of those, this design is necessary but
not sufficient. Talk to a security professional and reach for an
air-gapped machine.

## The one design decision

Reject every variant of "soft gating": env-vars consulted at query time,
frontmatter filters in QMD, agent prompts that say "do not query the
`sensitive` collection." Every soft gate is a single line of code or
configuration that can be silently broken by:

- A QMD upgrade that drops the env-var check.
- A new agent runtime that issues filesystem reads outside the
  spotlight-aware read wrapper.
- A backup tool, metadata indexer, or cloud-sync agent that doesn't know
  the convention.
- Prompt injection from open-case material instructing the agent to `cat`
  or `rg` a sensitive path.
- Future contributors who don't understand the invariant.

The only design that survives all of those is **physical separation**:
sensitive material lives outside the case directory tree entirely, in a
separate filesystem location that frontier-runtime launchers literally
never configure as a search path. There is no flag to forget, because
there is no flag.

## Layout

```
~/buried_signals/investigations/cases/peter-thiel-europe/
  case.yaml                       # carries `sensitive_store:` pointer if escalated
  brief-directions.txt
  data/                           # OPEN evidence — visible to all runtimes
    methodology.json
    findings.json
    fact-check.json
    investigation-log.json
    summary.json
  report.html                     # publishable report
                                  # ← note: no `sensitive/` subdirectory.
                                  #   sensitive content lives OUTSIDE
                                  #   this tree.

~/buried_signals/sensitive/peter-thiel-europe/    # MIRROR — local runtime only
  findings.json                   # sensitive findings only
  sources/                        # source-protected docs, leaks, off-record notes
  fact-check.json                 # sensitive verifications (if needed)
  notes/                          # working notes during sensitive phase
  report.html                     # internal report (never published)

~/.qmd/knowledge.db               # OPEN ingest target — every runtime queries this
~/buried_signals/sensitive/qmd/sensitive.db
                                  # SENSITIVE ingest target — only local-runtime
                                  # QMD invocations include this path
```

Three invariants the launcher enforces:

1. **Case dir contains no sensitive content.** If `case.yaml` has a
   `sensitive_store:` pointer, the journalist promises that anything
   classified as sensitive lives at that pointer's resolved path and
   *not* in any subdirectory of the case dir. Spotlight provides the
   tooling (`spotlight escalate`, `spotlight ingest`) so the journalist
   doesn't have to manually maintain this; tooling refuses to write
   sensitive output into the case dir.
2. **Frontier launchers cannot read the sensitive root.** The frontier
   launcher (`spotlight` with runtime `claude`, `gemini`, `codex`,
   `opencode`) does not read, resolve, or pass through any path under
   `~/buried_signals/sensitive/`. Backup tooling and Spotlight metadata
   indexing are configured at install time to exclude this directory.
3. **Frontier QMD invocations cannot reach the sensitive index.** The
   frontier launcher exports a fixed `QMD_DB_PATHS` value that points
   only at the open index. The local launcher exports a value that
   includes both. QMD is unmodified by this design — the gate is
   *which database paths the binary is invoked against*, not what the
   binary does internally.

## Workflow

### Step 1 — Open case start (frontier runtime, default path)

```
$ spotlight new peter-thiel-europe
```

Creates `cases/peter-thiel-europe/` with `case.yaml`:

```yaml
slug: peter-thiel-europe
created_at: 2026-05-22T10:00:00Z
sensitive_store: null
```

`sensitive_store: null` means open-only. Frontier launchers attach
freely. QMD search hits `~/.qmd/knowledge.db` only.

The preflight skill displays a one-line reminder:

> This case is open-tier — any evidence you save here is visible to your
> frontier model. If sensitive material arrives, run `spotlight escalate
> <slug>` before saving it.

### Step 2 — Open research (frontier runtime)

Normal pipeline: Brief → Methodology → 5 execution cycles → Gate 1 →
Ingest. Findings land in `cases/peter-thiel-europe/data/findings.json`.
Ingest writes notes into `~/.qmd/knowledge.db` and into the open
Obsidian vault.

### Step 3 — Escalation (when sensitive material arrives)

A leak / off-record document / source identity appears. **Before** the
journalist saves it anywhere on disk, they run:

```
$ spotlight escalate peter-thiel-europe
```

This:

1. Creates `~/buried_signals/sensitive/peter-thiel-europe/`.
2. Writes `sensitive_store: ~/buried_signals/sensitive/peter-thiel-europe`
   into `case.yaml`.
3. From this point, the frontier launcher refuses to attach to this
   case. The error message names the case and the runtime command to
   use instead.
4. Tells the journalist: drop the sensitive file into
   `~/buried_signals/sensitive/peter-thiel-europe/sources/` and switch
   to the local runtime.

If the journalist *has already* saved sensitive material into the case
dir before realizing they should have escalated, `spotlight escalate`
warns clearly: the frontier runtime that touched that case dir has
already seen the material. The escalation cannot undo that exposure.
At that point the case is editorially compromised; the journalist must
decide whether to continue.

### Step 4 — Sensitive phase (local runtime only)

```
$ spotlight --runtime=local peter-thiel-europe
```

The local launcher:

1. Reads `case.yaml`, resolves the `sensitive_store` pointer.
2. Exports `QMD_DB_PATHS=~/.qmd/knowledge.db,~/buried_signals/sensitive/qmd/sensitive.db`.
3. Launches the agent runtime with both `cases/peter-thiel-europe/` and
   `~/buried_signals/sensitive/peter-thiel-europe/` exposed as inputs.

The agent sees the full picture. Sensitive findings are written to
`~/buried_signals/sensitive/peter-thiel-europe/findings.json`. The
investigation-log entry for each cycle records *which* store each
finding came from.

### Step 5 — Report writing (local runtime)

The review skill produces two outputs from one set of findings:

- `cases/peter-thiel-europe/report.html` — **publishable**. Filtered to
  open findings only. Citations only reference sources under the
  open case dir. Same finding IDs as the internal report — auditable
  diff.
- `~/buried_signals/sensitive/peter-thiel-europe/report.html` —
  **internal**. Full picture. Never published. Citations include both
  open and sensitive sources.

The publishable report carries a frontmatter marker
`omitted_findings: <n>` so the reader (the journalist's editor) knows
the open report is a redacted view, not the entire case.

### Step 6 — Ingestion (local runtime)

Open findings ingest as today — entity notes and methodology notes
write to the Obsidian vault and into `~/.qmd/knowledge.db`.

Sensitive findings ingest separately:

- Entity notes for entities that appear *only* in sensitive findings
  write to the sensitive Obsidian vault path and into
  `~/buried_signals/sensitive/qmd/sensitive.db`.
- Entity notes for entities that appear in *both* tiers get split: the
  open Obsidian note holds public-record context only; a sibling
  sensitive note holds the source-protected context. The two notes
  share an entity ID but only the open one is visible to frontier
  runtimes.

### Step 7 — Next case (frontier runtime, fresh investigation)

```
$ spotlight new al-thani-shell-co
$ spotlight al-thani-shell-co
```

QMD search during methodology hits `~/.qmd/knowledge.db` only. The
peter-thiel-europe sensitive findings, the leaked documents, the
off-record notes — all invisible. The frontier runtime never has a
path through which it could even attempt to read them.

### Step 8 — Declassification (explicit, one-way, audit-logged)

Sometimes a sensitive source becomes public — they consent to
attribution, the document gets published elsewhere, an embargo lifts.
The journalist runs:

```
$ spotlight declassify peter-thiel-europe F23
```

Where `F23` is a sensitive finding's ID. The command:

1. Moves the finding from
   `~/buried_signals/sensitive/peter-thiel-europe/findings.json` to
   `cases/peter-thiel-europe/data/findings.json`.
2. Moves any sensitive sources cited by `F23` from
   `~/buried_signals/sensitive/peter-thiel-europe/sources/` to
   `cases/peter-thiel-europe/data/sources/`.
3. Re-ingests the finding's entity notes from the sensitive QMD
   database into the open knowledge database.
4. Writes an entry to the case's provenance manifest recording:
   timestamp, finding ID, reason (free-text the journalist supplies),
   and the human who authorized it.

Declassification is one-way by design. There is no `spotlight
reclassify` command. If a finding declassified in error must be
re-protected, that requires a manual cleanup of the open knowledge
base and an acknowledgement that the frontier provider may already
have seen the content during the period it was open. The
provenance-manifest entry is the audit trail for that conversation.

## Schema changes

### `case.yaml` — new field

```yaml
sensitive_store: null            # default (open-only)
# or
sensitive_store: ~/buried_signals/sensitive/<slug>    # after escalation
```

A boolean would do the job but the explicit path makes the relationship
inspectable without consulting any config file. Tooling resolves `~`
at runtime.

### `findings.json` — no schema change

The case dir's `findings.json` carries open findings. The sensitive
store's `findings.json` carries sensitive findings. Same schema. No
mixed file ever exists.

Finding IDs are allocated from a single counter recorded in
`case.yaml` so cross-tier references in the internal report remain
unambiguous.

### `provenance-manifest.json` — new event types

```json
{
  "event": "escalation",
  "case": "peter-thiel-europe",
  "timestamp": "...",
  "sensitive_store_path": "..."
}
{
  "event": "declassification",
  "case": "peter-thiel-europe",
  "finding_id": "F23",
  "timestamp": "...",
  "reason": "Source consented to on-record attribution on 2026-05-21.",
  "authorized_by": "tom@buriedsignals.com"
}
```

## Enforcement chain

The 2026-05-22 verification test (see
`~/buried_signals/investigations_test/VERIFICATION.md`) confirmed that
a launcher-installed wrapper alone is **not sufficient**. A frontier
agent with raw shell access (Claude Code's Bash tool, OpenCode's
exec, etc.) can ignore the wrapper and run `qmd --index sensitive`
directly. The wrapper protects honest agents and prompt-injection
victims; it does not protect against agents that go around it.

Therefore: UID separation is the load-bearing defense, not the
"optional recommended" footnote it was in the earlier draft.

In order from outermost (cheap, weak) to innermost (expensive,
strong):

1. **`case.yaml` pointer.** Frontier launcher reads it; if non-null,
   refuses to attach. Single point of failure: if `case.yaml` is
   corrupted or unreadable, fail closed (refuse all runtimes until the
   journalist verifies). Catches the common-case misclick.
2. **Launcher-installed wrapper (`qmd-spotlight`).** Frontier launcher
   installs a `qmd-spotlight` shim on PATH that hard-codes
   `--index knowledge`. Local launcher installs a different shim that
   queries both indices and merges. Defends against honest agents
   that call the tool as named. **Does not defend against agents
   with raw `qmd` access.**
3. **Runtime permission template.** The frontier launcher writes a
   per-runtime permission file (Claude Code's `.claude/settings.json`
   allowlist, Codex's permissions, OpenCode's tool allowlist) that
   denies bare `qmd` invocation — only `qmd-spotlight` is allowed.
   Closes the prompt-injection escape route on cooperating runtimes.
   Still a soft gate at the runtime layer.
4. **UID separation (load-bearing).** Frontier agent runs under a
   different macOS UID from the journalist's primary login. The
   sensitive sqlite file and `~/buried_signals/sensitive/` directory
   are `chmod 0700` and owned by the journalist's primary UID. The
   frontier-UID process literally cannot read the sensitive index
   regardless of how clever the agent or its prompt is. **This is
   the gate the design relies on for actual confidentiality.**
   Implementation: a dedicated `spotlight-frontier` Unix account on
   the journalist's Mac, the frontier launcher invokes the runtime
   via `sudo -u spotlight-frontier`. Home directory and sqlite cache
   are per-UID. The journalist's primary UID retains read/write on
   open case dirs (group ownership) so the frontier session can still
   write findings.
5. **Filesystem-attribute exclusion (install-time, one-time).** The
   Spotlight installer adds `~/buried_signals/sensitive/` to:
   - `~/Library/Preferences/com.apple.spotlight.plist` excluded paths
     (so macOS Spotlight doesn't index it — prevents `mdfind` leakage).
   - Time Machine exclusions (`tmutil addexclusion`).
   - Any documented backup tools the journalist names at install time
     (Arq, Backblaze, iCloud, Dropbox, Syncthing) — install script
     prompts and refuses to proceed if a watched-path conflict is
     detected.
6. **Air gap (Phase 6, opt-in).** Sensitive workflow on a separate
   machine entirely (the existing Mac mini under Hermes, no network
   during sensitive sessions). Strongest guarantee, highest
   operational cost. Reach for this when the material's
   confidentiality has criminal-prosecution implications.

The order matters: an attacker (or a buggy upgrade) has to defeat
*every* layer in the path to the data. The wrapper alone is one
layer. UID separation makes the wrapper meaningfully harder to
bypass because the bypass route (`qmd --index sensitive`) now also
requires escaping the UID — which requires a macOS privilege
escalation, not just a clever prompt.

## Open questions to resolve before implementation

1. **Multi-machine sync.** If the journalist works on a laptop and a
   Mac mini, both with Spotlight installed, the open case dir is in
   the synced workspace but `~/buried_signals/sensitive/` must not be.
   How do we encode "do not sync this path" in a way that survives the
   journalist setting up their next sync tool? Probably: store the
   sensitive root under a path that is gitignored *and* outside the
   usual `iCloud` / `Dropbox` / `Syncthing` watched paths by default.
   Document this as an install-time check.
2. ~~**QMD's actual support for multi-db invocations.**~~ **Resolved
   2026-05-22.** QMD's native `--index <name>` flag resolves to a
   separate sqlite file per name. The verification test confirmed
   this works without any QMD patch. Production should still consider
   relocating the sensitive sqlite to a path outside `~/.cache/qmd/`
   (e.g. `~/buried_signals/sensitive/qmd/sensitive.sqlite`); the
   simplest implementation is a symlink, the cleaner one is a small
   QMD feature for `--index-path <abs-path>`.
3. **What "sensitive runtime" means at the OpenCode layer.** OpenCode
   routes to a provider via `npm`. The local-runtime variant routes to
   a local Ollama or llama-server. The frontier-runtime variants route
   to Anthropic/Google/OpenAI/OpenRouter. The launcher determines
   which set of providers is "local-runtime" — currently the test is
   "is the OpenCode provider config pointing at 127.0.0.1?" This needs
   a hardening pass: a config that *claims* to be local but routes
   externally must be rejected.
4. **What happens to the open part of an escalated case if the
   journalist never returns to the local runtime?** Probably nothing
   — the case stays escalated, frontier runtime refuses, the
   journalist resolves it when they next have time. Worth surfacing
   in the UI rather than letting cases silently stall.
5. **Entity-note splitting at ingest is the trickiest piece.** A
   person who appears in 12 open findings and 2 sensitive ones
   currently gets one entity note. After this change, the open note
   carries 12 findings' worth of context, the sensitive note carries
   2 — but the sensitive note may reference the open note's existence
   ("see also the public-record context at <link>"). The reverse must
   not happen (open note must never reference the existence of a
   sensitive note). The ingest skill needs explicit rules here.
6. **UID-separation account provisioning.** The new load-bearing
   defense requires a dedicated `spotlight-frontier` macOS user
   account on the journalist's machine. Provisioning needs sudo at
   install time; the installer must explain to the journalist what
   it's doing and why (a non-trivial security ask). Group permissions
   need to be set so the frontier UID can still read/write open case
   dirs. Sketch the install script's UX before committing.

## Implementation phases

In order, each shippable independently:

**Phase 1 — `case.yaml` schema + launcher gate.** Add the field, write
the case-creation skill update, teach the frontier launchers to refuse
escalated cases. No QMD work yet, no sensitive-store directory
creation — the launcher just hard-blocks. Lets us validate the
journalist UX before touching any data path.

**Phase 2 — Sensitive-store directory + local launcher + dual QMD
indices.** Add `spotlight escalate`. Local launcher exposes both case
dir and sensitive store, installs the `local-qmd` wrapper that
queries both indices. Frontier launcher installs `frontier-qmd`
wrapper that queries the open index only. Ingest split based on
finding sensitivity tag. Entity-note splitting rules implemented
here.

> The 2026-05-22 verification confirmed QMD's `--index <name>` flag
> is enough machinery for this phase — no QMD patch required.
> Production deployments should consider symlinking the sensitive
> sqlite out of `~/.cache/qmd/` to `~/buried_signals/sensitive/qmd/`
> for backup-exclusion alignment.

**Phase 3 — UID separation (load-bearing).** Provision the
`spotlight-frontier` macOS user account at install time. Frontier
launcher invokes the agent runtime via `sudo -u spotlight-frontier`.
The sensitive store is `chmod 0700` and owned by the journalist's
primary UID. Frontier process literally cannot read the sensitive
sqlite or the sensitive directory regardless of what its agent tries.
**This is the phase where confidentiality becomes load-bearing**;
phases 1–2 ship a system that defends only against honest agents,
which is enough for most newsroom work but not for source protection
under legal threat.

**Phase 4 — Runtime permission templates + declassification.** Write
per-runtime permission files (Claude Code, Codex, OpenCode) that the
frontier launcher installs to deny bare `qmd` invocation — only
`qmd-spotlight` is permitted. `spotlight declassify` command.
Provenance-manifest entries. Tests for the one-way ratchet.

**Phase 5 — Backup / indexer exclusions + multi-machine docs.**
Installer adds the right exclusions (Spotlight, Time Machine, named
cloud sync tools). Multi-machine setup documentation. Reverse-audit
script that scans `~/buried_signals/sensitive/` for backup-tool
sentinel files (`.dropbox`, `iCloud Drive` metadata, Time Machine
markers) and warns.

**Phase 6 — Air gap (opt-in).** For cases where UID separation isn't
enough — criminal-prosecution stakes, hostile-state threats. Sensitive
workflow on the existing Mac mini, network disabled during sensitive
sessions, files moved between machines via signed-only mechanism.
Scope to be defined when first needed; do not pre-build.

Phases 1–2 give the journalist a usable system with launcher-level
defense; Phase 3 is the gate that makes "absolutely sure" defensible.
Phases 4–6 are hardening and quality-of-life.

## Out of scope

- Encrypted disk image for the sensitive root. macOS-native FileVault
  full-disk encryption is the assumed baseline. A separate encrypted
  sparse bundle for sensitive content is a future hardening pass.
- Per-finding cryptographic redaction (publish the open report with
  hashes of the redacted finding IDs so an editor can verify what was
  hidden). Future enhancement.
- Multi-journalist collaboration on a shared case with different
  access tiers. This design assumes one journalist per case for
  sensitive material. A team workflow needs additional thought.
