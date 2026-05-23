---
name: report-drafting
description: Post-Gate-1 sub-skill for Spotlight — draft the journalist-grade public-facing report.html from a verified investigation. Distinct from the review skill (editorial feedback loop) and the ingest skill (knowledge-base archival). Ships a working report-template.html skeleton (CSS variables, novelty + confidence pill classes, .path replication-block per finding, inline .sources strip per finding) and the design discipline that produces it: phase-by-phase methodology section that absorbs the adversarial fact-check verdict table inside Phase 3 — not as a separate top-level section. Hybrid-aware — when invoked after a data-detective handover, methodology walks upstream (data-detective phases) and downstream (Spotlight phases) in one ordered trail. Editing protocol: never run greedy regex on the live HTML; use anchored read+edit. Triggers on draft the report, build the public report, journalist-grade output, hand-off report, or final report.html.
version: "1.0"
invocable_by: [orchestrator, user]
requires: []
---

# report-drafting — Public-facing report deliverable

Spotlight ships three HTML artifacts in different roles:

| Skill | Output | Role |
|---|---|---|
| `review` | `review.html` | Self-contained editorial feedback loop — journalist inspects + submits feedback. Internal loop artifact. |
| **`report-drafting`** | **`report.html`** | **Public-facing journalism artifact — designed deliverable for editors / publication.** |
| `ingest` | (vault notes) | Knowledge-base archival in Obsidian / Tolaria / directory. |

This skill builds `report.html`. Read `references/report-template.html` before drafting — it is the working skeleton.

Invoked at Phase 5 (after Gate 1, before Phase 6 ingestion). Optional — the orchestrator presents it to the user as the choice between editorial-review-only and public-report-output. Mandatory when invoked via data-detective handover (data-detective stops at its Gate 1 and delegates the final report to Spotlight).

---

## Required deliverables

| File | Audience | What it is |
|---|---|---|
| `cases/{project}/report.html` | Publication / external reader | Public-facing journalism artifact. Styled, scannable, with inline replication paths and archived primary sources. |
| `cases/{project}/findings-report.md` | Editor / fact-checker | Narrative audit document. Plain prose + tables. Authoritative claim-by-claim record. |
| `cases/{project}/evidence-map.json` | Audit / replication | Machine-readable ledger: claim → sources → archive URLs. |

The HTML is not a markdown render. It is a designed document. Build from the template, not from scratch.

---

## Required structure per finding (HTML)

Every `<section class="finding">` MUST contain, in order:

1. **Header row** — `<h2>` with embedded finding ID, plus `.pill-novel` (purple, for genuinely new evidence) OR `.pill-connected` (outline, for new framings of public facts), plus `.pill-high` / `.pill-med` / `.pill-low` for confidence.
2. **Deck** — one-line subhed under the H2 in `<p class="deck">` (≤60ch).
3. **Stats grid** (optional) — `<div class="stats">` for findings with quantitative spine.
4. **Body paragraphs** — `<p>` (auto-constrained to ≤72ch via column width).
5. **`<div class="path" aria-label="How we got here">`** — REPLICATION PATH. One `.step` + `.what` pair per phase that produced this finding. Cite scripts, archived URLs, source documents. This block is what makes the finding auditable in under a minute. **Mandatory.**
6. **`<div class="sources">`** — primary-source URLs with archive references. **Mandatory.**

Optional add-ins:
- `<div class="flag">` for legal qualifications — use `<span class="flag-label">` for the in-line label, NOT `<strong style="display:block">`.
- `<div class="timeline">` for chronological evidence chains (2-column grid: date, event).
- `<div class="pull">` for a 1-2 sentence pull quote inside the finding body.

---

## The `.path` block — Spotlight phase vocabulary

Each `.step` label names the Spotlight phase that produced that step. Standard vocabulary:

- `P1 brief` — what scope was approved
- `P2 method` — what investigator's planning phase decided
- `P3 cycle N` — execution cycle N (which detector / search / source was queried)
- `P3 fact-check` — what the fact-checker added or corrected
- `P3 archive` — which web sources were archived (firecrawl + Wayback)
- `P3 social` — when social-media-intelligence is used (account authenticity, coordination)
- `P3 follow-the-money` — when follow-the-money skill traced financial flows
- `P4 gate` — what the user iterated at Gate 1

When invoked via **data-detective handover**, also use:

- `P0/P1 upstream` — data-detective ingest + resolve that produced the lead
- `P3 upstream detect` — data-detective detector name + SQL hash that flagged the lead
- `P6 handover` — the data-detective spotlight-handoff brief that triggered the Spotlight cycle

Each finding's `.path` block walks the actual trail. Don't invent steps that didn't happen.

---

## Methodology section pattern (highest-leverage learning)

The methodology section serves a dual purpose: it documents the skill (the algorithm) AND it logs the actual run. It is NOT a separate generic methodology. It is the audit trail of THIS investigation, in phase order.

Structure: one `<div class="phase">` per executed phase.

**Critical:** do NOT break the adversarial fact-check verdict table into a separate top-level section. It reads out of phase order. Instead, place it INSIDE the Phase 3 `<div class="phase">`.

When invoked via **data-detective handover**, the methodology section spans BOTH orchestrators:

```
<div class="phase">P0 upstream · data-detective ingest</div>
<div class="phase">P1 upstream · data-detective resolve</div>
<div class="phase">P3 upstream · data-detective detect (which detector flagged the lead)</div>
<div class="phase">P6 upstream · data-detective spotlight-handoff (the brief)</div>
<div class="phase">P1 · Spotlight brief (this orchestrator)</div>
<div class="phase">P2 · Spotlight methodology</div>
<div class="phase">P3 · Spotlight execution cycles + adversarial fact-check (verdict table INSIDE)</div>
<div class="phase">P4 · Spotlight Gate 1</div>
<div class="phase">P5 · Spotlight report-drafting (this document)</div>
```

Read the case's `data/investigation-log.json` (Spotlight's) and (if hybrid) `case-trace/data-detective/investigation-log.json` (upstream) to enumerate the actual phases executed.

---

## Design discipline

CSS variables already in the template (`--ink`, `--paper`, `--rule`, `--bg-soft`, `--red`, `--mono`, `--sans`, `--serif`). Do not reinvent them per finding.

**Max-width rules** (the template enforces these; do not override per-element):
- `h1` → 28ch
- `h2` → 32ch
- `.deck` (subhed) → 60ch
- Body `<p>` → constrained by the column, max-width:none
- `.lede` → constrained by the column, max-width:none
- Tables / `.stats` / `.path` / `.sources` / `.flag` / `.timeline` / `.phase` → full column width

**Pill semantics:**
- `.pill-novel` (purple) — genuinely new evidence not previously published.
- `.pill-connected` (outline) — new framing of public facts via cross-source join.
- `.pill-verified` (green) — fact-checker confirmed.
- `.pill-partial` (amber) — fact-checker partial verdict.
- `.pill-high` / `.pill-med` / `.pill-low` — confidence levels.
- `.pill-id` (mono, light) — finding ID badge.

**TL;DR table** at the top: one row per finding, `<a href="#f-NNN">` linked, with novelty + confidence pills inline.

---

## HTML editing protocol (hard rule)

NEVER run greedy regex substitution on the HTML file. Use anchored read+edit only. A greedy `re.sub` destroyed a 800-line report mid-pass in a prior investigation and forced a full rebuild.

Specifically:
- For per-finding additions: anchor the replace pattern on the closing element of the prior block + the opening of the target block.
- For methodology restructuring: extract the existing section, rewrite as a single block, replace with one edit call.
- If you must regex, do it in a one-shot Python script that prints the diff first, never `re.sub(..., re.DOTALL)` on the whole file.

---

## Workflow

```
1. Read references/report-template.html. Copy to cases/{project}/report.html.
2. Fill the header (title, deck, byline, lede) and the TL;DR table from data/findings.json.
3. For each verified finding in data/findings.json:
   a. Drop a <section class="finding"> from the template's finding-stub block.
   b. Fill the H2 + pills (novelty inferred from finding's origin + corroboration; confidence from fact-check verdict).
   c. Write the body (3-6 paragraphs, prose).
   d. Insert the .path block — one .step+.what pair per phase that produced this finding. Cite scripts, archived URLs, source documents.
   e. Insert the .sources strip — primary-source URLs only (not secondary commentary).
4. Fill methodology section:
   a. One .phase block per executed Spotlight phase (P0..P5). If hybrid: also one .phase block per executed upstream data-detective phase.
   b. INSIDE Phase 3: adversarial fact-check verdict table.
5. Fill "Open monitoring targets" section from data/findings.json's unresolved-gaps and monitoring_recommendations[].
6. Fill footer: conflicts of interest, source attributions.
7. Write findings-report.md in parallel (narrative form, no styling, every claim sourced).
8. Write evidence-map.json (audit ledger).
9. Validate HTML tags balance.
10. Append report_drafted to data/investigation-log.json.
```

---

## Inputs / Outputs

**Reads:**
- `cases/{project}/data/findings.json` (verified claims)
- `cases/{project}/data/fact-check.json` (adversarial verdicts)
- `cases/{project}/data/investigation-log.json` (phase log)
- `cases/{project}/data/provenance-manifest.json` (if present)
- `cases/{project}/summary.md` (Gate 1 artifact)
- (hybrid) `cases/{project}/data-detective-handover/` (upstream case-trace + briefs)

**Writes:**
- `cases/{project}/report.html`
- `cases/{project}/findings-report.md`
- `cases/{project}/evidence-map.json`

---

## Anti-patterns

- **Wall-of-text findings.** Every finding gets a `.path` block. If you find yourself writing "we cycled through three search rounds, then verified with the fact-checker, then archived" in the prose, lift it out into the path block.
- **Methodology-at-the-bottom dumping ground.** The methodology section is the run log; phases must appear in phase order, with the fact-check verdict table INSIDE the relevant Phase 3 block.
- **Sources at the end of the document.** Sources go inline per-finding via `.sources` strip. Readers should never have to scroll to a bibliography.
- **`.flag strong { display: block }`.** Breaks inline legal citations to new lines. Use `<span class="flag-label">` instead.
- **Markdown-style HTML.** The HTML is a designed document, not a markdown render. If your HTML reads like a `pandoc` output, restart from the template.
- **Regex on the live file.** Use anchored read+edit. A greedy substitution will destroy hours of work.

---

## Template

`references/report-template.html` is a working skeleton with:
- Full CSS variables + classes (.pill-*, .path, .sources, .stats, .flag, .timeline, .phase, .pull, .deck, .tldr)
- A `<head>` block with the typography stack
- Header, TL;DR table, finding-stub, methodology stub (with hybrid-mode upstream phase blocks commented in), open-targets stub, footer
- HTML comments marking the agent customization points

Copy it, fill it, ship it.
