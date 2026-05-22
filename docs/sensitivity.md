# Sensitivity — separate ingest vault + dual-query command

Status: design doc — not yet implemented.
Scope: deliberately narrow. See "What this is not" below.

---

## What this is

Spotlight should support **two ingest targets**:

- The **default vault** + default QMD index. This is the existing
  behaviour. Anything a journalist runs through the standard
  Spotlight pipeline ends up here.
- A **separate sensitive vault** + separate QMD index. Opt-in. The
  ingest skill writes here when given an explicit flag.

And **one new query command** that's only available in local-runtime
sessions:

- A wrapper that queries **both** indices and unions the results.
  Standard `qmd ...` in any other context queries the default index
  only.

That's it. Two ingest targets, one union-query wrapper.

## What this is not

This design is explicitly **not**:

- A workflow restriction on cases.
- An enforcement boundary between frontier and local runtimes.
- A protection against an adversarial agent with shell access.
- A guarantee that sensitive material can't leak.

Spotlight is an OSINT investigation orchestrator for open material.
**Sensitive investigations happen elsewhere** — in whatever
environment the journalist deems appropriate (local model on an
isolated machine, encrypted disk, air gap, paper). The output of that
work can optionally be ingested into the sensitive vault so it's
discoverable from future local-runtime Spotlight sessions. Spotlight
itself does not orchestrate the sensitive investigation.

The earlier draft of this doc proposed `spotlight escalate`,
`spotlight declassify`, frontier-runtime hard-blocks, UID separation,
permission templates, and a six-layer enforcement chain. That design
is dropped. The verification work at
`~/buried_signals/investigations_test/` (2026-05-22) showed that
launcher-level wrappers don't survive an agent with raw shell access
without UID separation, and UID separation is too much install-time
machinery for the value delivered. We are not in the business of
building a counter-intelligence system.

## Two ingest targets

The ingest skill currently writes to one vault path determined at
install time. Add a second target.

**Configuration** (in `.env` or `.spotlight-config.json`):

```
SPOTLIGHT_VAULT_PATH=~/Obsidian/main          # existing
SPOTLIGHT_SENSITIVE_VAULT_PATH=~/Obsidian/sensitive  # new, optional
SPOTLIGHT_SENSITIVE_INDEX=sensitive           # new, QMD index name
```

If `SPOTLIGHT_SENSITIVE_VAULT_PATH` is unset, the sensitive ingest
path is disabled and the skill behaves exactly as today.

**Invocation** — the ingest skill accepts an optional flag:

```
invoke-skill ingest --target sensitive
```

When `--target sensitive`, the skill:

1. Writes notes to `SPOTLIGHT_SENSITIVE_VAULT_PATH` instead of the
   default vault path.
2. After writing, runs `qmd --index <SPOTLIGHT_SENSITIVE_INDEX>
   collection add <path>` so the sensitive vault becomes
   independently queryable.

The two vaults never cross-link. Sensitive notes that reference an
entity also present in the default vault may include a textual
mention; they do not write a wikilink that resolves into the default
vault. (This is enforced by ingest behaviour, not by any runtime
gate.)

QMD's native `--index <name>` flag is enough machinery — the 2026-05-22
verification confirmed two named indices stay in separate sqlite
files at `~/.cache/qmd/<name>.sqlite`. No QMD patch required.

## Dual-query command

A wrapper, available in local-runtime sessions only, that queries the
default index and the sensitive index and merges results:

```
qmd-spotlight query "..."          # default behaviour: open index only
qmd-spotlight query "..." --with-sensitive    # union with sensitive index
```

Or, if the merge should be implicit when both indices exist:

```
local-qmd query "..."     # always unions if SPOTLIGHT_SENSITIVE_INDEX is set
```

Pick one shape during implementation. The second is friendlier; the
first is more auditable from logs.

The wrapper is installed on PATH only by the local-runtime launcher
(`~/.local/bin/spotlight-local`). A frontier-runtime launcher does
not install it. **This is not an enforcement boundary** — a frontier
agent with shell access can still run `qmd --index sensitive` and
read the sensitive vault directly. The wrapper is a convenience for
local sessions, not a gate.

If a journalist runs frontier-runtime sessions on the same machine
where the sensitive index exists, they accept that the frontier
agent could in principle reach it. The mitigation for that risk is
operational (don't run frontier sessions on the same machine, use a
separate machine for sensitive material) and lives outside Spotlight.

## Implementation surface

| Touch | Change |
|---|---|
| `.env` / config schema | Add `SPOTLIGHT_SENSITIVE_VAULT_PATH` and `SPOTLIGHT_SENSITIVE_INDEX`. Both optional; absent = sensitive ingest disabled. |
| `skills/ingest/SKILL.md` | Accept `--target sensitive`. When set, write to the sensitive vault path and add the result to the sensitive QMD index instead of the default. Refuse to cross-link into the default vault. |
| New: `~/.local/bin/qmd-spotlight` (or `local-qmd`) | Wrapper that queries the default index, and if `SPOTLIGHT_SENSITIVE_INDEX` is set + the user passes `--with-sensitive` (or always, depending on chosen shape), also queries the sensitive index. Merge and emit. Installed by `install-spotlight.sh` only when the local runtime is selected. |
| `install-spotlight.sh` | Prompt for the sensitive vault path during local-runtime install. Set up the symlink/path that puts the sensitive sqlite at the journalist's preferred location (default: `~/buried_signals/sensitive/qmd/sensitive.sqlite`). |
| `docs/sensitivity.md` | This doc. |

That's the whole change. Roughly 50–100 LOC across config, ingest
skill, and the wrapper.

## Out of scope

- Anything that touches case directories or `case.yaml`.
- Any check on which runtime is active.
- Any blocking, gating, refusal, or warning by the launcher.
- Declassification, escalation, or any state transition between
  vaults. If a journalist wants to promote a sensitive note to the
  open vault, that's a manual file copy and a re-ingest — no special
  command.
- Provenance manifest entries for tier transitions.
- Multi-machine sync hygiene. The sensitive vault is the
  journalist's to manage; if they want it on iCloud they can put it
  on iCloud, and they own that decision.
- UID separation, sandbox profiles, permission templates, air gap.
  Those belong to the operational layer the journalist runs *around*
  Spotlight, not inside it.

## Why this is the right scope

The earlier design tried to make Spotlight responsible for keeping
sensitive material confidential. That is too large a promise for an
OSINT orchestrator to make honestly — confidentiality lives in the
operating environment, not in a workflow tool. By stripping the
restrictions and just providing the plumbing (two ingest targets,
one union query), Spotlight stays focused on what it's actually for
and lets the journalist compose their own sensitive workflow with
whatever tools genuinely match their threat model.
