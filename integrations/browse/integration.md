# browse — Skill-Catalog-Driven Browser Automation

The Browse CLI is a second-tier browser-automation integration. Browser Harness remains the primary browser fallback for Spotlight investigations. Use Browse when a [browse.sh](https://browse.sh) skill exists for the target portal and that skill captures real navigation knowledge the investigator would otherwise have to figure out alone.

## When to pick Browse over Browser Harness

Pick Browse if **all** of these are true:

1. The target domain has a curated skill in the browse.sh catalog. Check with `browse skills find <domain>`.
2. The skill captures non-trivial navigation knowledge (auth flow, multi-step form, paginated tables, anti-bot quirks, XHR endpoints) — not just "scrape this static URL," which firecrawl already handles.
3. The use is in `--local` mode (no Browserbase cloud APIs touched).

Otherwise, prefer Browser Harness. Reasons:

- Browser Harness attaches to the user's already-logged-in Chrome via CDP. Browse defaults to launching a fresh Chromium with no existing session state. For sites where the user is already authenticated, Browser Harness is faster and avoids re-login.
- Browser Harness's coordinate-click model passes through iframes, shadow DOM, and cross-origin boundaries at the compositor level. Browse's selector/ref model is cleaner for vanilla pages but needs extra work on iframe-heavy enterprise portals.
- Browser Harness keeps the agent context light (`page_info()` returns ~150 bytes). Browse's `snapshot --compact` returns the full accessibility tree (~60-100KB for a typical page). Across a 30-step investigation that gap is real.
- Browser Harness's per-command latency is ~30ms (daemon-warm); Browse pays ~750ms CLI startup per call.

## Use For

- OpenCorporates company / officer / filings lookups — when an `OPENCORPORATES_API_TOKEN` is available (paid tier or NGO/journalism grant; the skill documents this prerequisite).
- Wayback Machine snapshot resolution — both Browse's and Browser Harness's skills are HTTP-only and equivalent here; either works.
- Any browse.sh skill that already encodes the navigation knowledge for an investigative source.
- Fallback when Browser Harness has no `domain-skills/` entry for the target site and the agent doesn't want to write coordinate-click logic from scratch.

## Do Not Use For

- Sensitive cases. `browse cloud fetch`, `browse cloud search`, and `browse cloud sessions` route requests through Browserbase's US cloud infrastructure. For confidential sources, China-topic work, leaked-document trails, or anything Tom marks sensitive, stay in `--local` mode and do not invoke `browse cloud *`.
- Long interactive loops (30+ commands against the same portal). The per-command CLI startup cost adds up. Browser Harness is faster for sustained sessions.
- Sites where Browser Harness already has a curated `domain-skill`. Use the harness path — it's faster, deeper, and contributes back to the repo.

## Installation

```bash
npm install -g browse
```

That installs the `browse` CLI globally. No Browserbase account, no API key. Verify with `browse --version`.

## Skill Catalog

Browse.sh skills are pre-built navigation workflows for specific sites. Install a skill before using it.

```bash
# Discover skills
browse skills find <keyword>       # search by keyword
browse skills list                 # show installed
browse skills find <domain>        # search by domain (e.g., opencorporates)

# Install a skill
browse skills add <hostname>/<task-slug>

# Example: install the OpenCorporates skill
browse skills add opencorporates.com/find-company-filings-e9ewrz
```

Installed skills land in `~/buried_signals/tools/.agents/skills/<skill-name>/SKILL.md`. The skill body documents the workflow, endpoints, gotchas, and expected output shape — read it before invoking. Spotlight does not auto-install skills; the orchestrator installs on demand when the investigator/fact-checker has identified the target.

## Driver Commands (no skill, manual navigation)

When no curated skill exists and you still want to use Browse:

```bash
browse open --local "<url>"          # always include --local for sovereignty
browse snapshot --compact            # get accessibility tree with @refs
browse click @<ref>                  # click by ref
browse fill @<ref> "<text>"          # fill input by ref
browse type "<text>"                 # type at current focus
browse press Enter                   # press a key
browse get text @<ref>               # read element text
browse eval "<javascript>"           # run JS in page
browse screenshot --path /tmp/x.png  # capture
browse stop                          # close the session
```

For unknown portals, prefer Browser Harness — its coord-click model handles more edge cases.

## Evidence Output

Every Browse acquisition must update `cases/{project}/data/evidence-bundle.json` with:

- `acquisition_method: "browse"`
- `acquisition_subtype:` one of `"browse-skill"` (used a browse.sh skill) or `"browse-driver"` (manual driver commands)
- `skill_slug:` when `acquisition_subtype == "browse-skill"` — the slug from browse.sh (e.g., `opencorporates.com/find-company-filings-e9ewrz`)
- source URL
- access timestamp (ISO 8601)
- raw output path (where the agent saved the captured JSON / markdown)
- screenshot path when relevant
- `local_only: true` if `--local` was enforced; absent or `false` if cloud APIs were touched
- missing-source gate notes
- `human_verification_required` when ambiguity remains

## Sensitive Mode

When the investigation is flagged `sensitive: true`:

- Force `--local` on every command (the CLI does this by default; do not pass `--remote` or use `browse cloud *`).
- Do not install new skills mid-investigation if installing the skill requires touching browse.sh (the catalog is hosted, so installation is a public lookup). Pre-install skills before flagging sensitive.
- Record in the case log that Browse was used in local-only mode and which skills were referenced.

## Cost Model

- `--local` driver commands: free.
- `browse skills install/list/find/add`: free (catalog is open-source).
- Stagehand AI navigation (separate `stagehand` SDK use): requires your own OpenAI/Anthropic/Gemini API key, charged by that provider. **Spotlight does not invoke stagehand directly** — the runtime's agent already provides the AI layer when driving Browse driver commands. Stagehand only matters if you write a standalone Node script that imports `@browserbasehq/stagehand` — outside the scope of this integration.
- `browse cloud *`: requires `BROWSERBASE_API_KEY`. Free tier: 1k fetch + 1k search calls/month. **Out of scope for sensitive cases; do not enable without explicit user consent.**

## Pitfalls

- **Per-command latency.** ~750ms CLI startup per `browse <command>` call. Avoid 50-command loops; batch where possible or fall back to Browser Harness for sustained work.
- **Snapshot verbosity.** `browse snapshot --compact` returns the full accessibility tree (60-100KB). For agent token budgets, read selectively: `browse snapshot --compact | head -<N>` or use `browse get text @<ref>` for specific elements.
- **Fresh-browser default.** Without `--cdp`, Browse launches its own Chromium with no saved cookies. If the user is already logged into the target in their main Chrome, prefer Browser Harness (which attaches to the live session) or pass `--cdp 9222` to Browse to share state.
- **Skill expiry.** Browse.sh skills are dated (frontmatter `updated:`). A skill written 6 months ago may not reflect the current site. Check the `updated:` field; if older than ~3 months, re-verify the workflow against the live site before relying on it.
- **Paid-API skills.** Some skills (e.g., OpenCorporates) document API endpoints that require user-provided tokens. The skill installation is free; the runtime capability depends on the user having (or applying for) the token.

## Drift with browser-harness

This integration is **additive**. Browser Harness remains the primary browser-automation tool. When Browse and Browser Harness both can do a task, the routing in `skills/integrations/SKILL.md` defines which to prefer. Update both when adding new capabilities.
