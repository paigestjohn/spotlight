# Entity Model

Note types, frontmatter contracts, and wikilink conventions for vault ingestion.

---

## Note Types

### 1. Investigation Note

**Path:** `{vault}/investigations/{project-id}.md`

```yaml
---
id: project-id
title: Human-readable title
status: confirmed
date: YYYY-MM-DD
regions: [list]
entities: [entity-id-1, entity-id-2]
methodology: [technique-id-1]
tools: [tool-id-1]
tags: [tag1, tag2]
verified_count: N
total_findings: N
---
```

**Body structure:**

1. **Summary** — Brief overview of the investigation and its conclusions.
2. **Key Findings** — One section per finding:
   - Claim
   - Confidence (high / medium / low)
   - Verdict (confirmed / unconfirmed / debunked)
   - Evidence
   - Sources
   - Perspective
3. **Connections** — Wikilinked entities involved in this investigation.
4. **Gaps** — Open questions and unresolved leads.
5. **Methodology Applied** — Techniques and tools used, with wikilinks.

---

### 2. Entity Note

**Path:** `{vault}/entities/{entity-id}.md`

```yaml
---
id: entity-id
type: person|organization|company|place
subtype: optional-subtype
aliases: [list]
country: XX
region: region-name
investigations: [project-id-1]
first_seen: YYYY-MM-DD
---
```

**Body structure:**

1. **Description** — Who or what this entity is.
2. **Role in Investigations** — Table:

| Investigation | Role | Date |
|---------------|------|------|
| [[project-id]] | description of role | YYYY-MM-DD |

3. **Key Relationships** — Wikilinks to other entities with relationship context.

---

### 3. Methodology Note

**Path:** `{vault}/methodology/{technique-id}.md`

```yaml
---
id: technique-id
type: technique
category: osint-category
tools: [tool-id-1]
investigations: [project-id-1]
---
```

**Body structure:**

1. **Description** — What this technique does and when to use it.
2. **Steps** — Ordered procedure.
3. **Tools** — Wikilinked tools used by this technique.
4. **Usage History** — Table:

| Investigation | Context | Date |
|---------------|---------|------|
| [[project-id]] | how it was applied | YYYY-MM-DD |

5. **Lessons Learned** — What worked, what failed, what to do differently.

---

### 4. Tool Note

**Path:** `{vault}/tools/{tool-id}.md`

```yaml
---
id: tool-id
type: tool
category: osint-category
url: https://...
access: free|freemium|paid|signup-required
methodology: [technique-id-1]
investigations: [project-id-1]
usage_count: N
---
```

**Body structure:**

1. **Capabilities** — What this tool does.
2. **Access Notes** — How to get access, cost, rate limits.
3. **Usage History** — Table (max 10 entries, most recent first):

| Investigation | Context | Date |
|---------------|---------|------|
| [[project-id]] | how it was used | YYYY-MM-DD |

4. **Tips for Future Agents** — Curated advice for effective use.

---

### 5. Claim Note

**Path:** `{vault}/claims/{claim-id}.md` where `claim-id` is `{project-id}-f{n}` (lowercased finding ID of the originating case — e.g. `acme-files-f1`). The claim's identity stays bound to the case that first recorded it; later cases append to it rather than minting a new ID.

```yaml
---
id: acme-files-f1
project: acme-files
finding_id: F1
entities: [acme-corp, john-doe]
verdict: verified
confidence: high
confidence_cap: high
layer: durable
recorded: YYYY-MM-DD
verified: YYYY-MM-DD
verified_by: acme-files
needs_verification: false
---
```

**Field semantics:**

- `verdict` — the fact-check verdict, exactly one of the existing taxonomy values that pass the eligibility gate: `verified` or `partially_verified`. Other verdicts never produce claim notes (see eligibility below).
- `confidence` / `confidence_cap` — carried from the finding and its grounding object, unchanged.
- `layer` — derived, never set by hand: `verified` → `durable`; `partially_verified` → `lead`.
- `recorded` — the ingest date.
- `verified` / `verified_by` — fact-check date and the project whose fact-check produced the verdict.
- `needs_verification` — `true` for every `lead`-layer claim; `false` for `durable`.

**Eligibility gate (hard rule).** A finding becomes a claim note only when ALL hold:

1. Fact-check verdict is `verified` or `partially_verified`.
2. Grounding `confidence_cap` is above `low`.
3. At least one source reference is present.
4. The finding is not RLM-derived (RLM artifacts are leads inside a case, never vault knowledge).

Findings that fail the gate stay in the investigation note (flagged, as today) and case files. The claims layer is the cross-case queryable surface; it admits verified intelligence only.

**Body structure:**

1. **Claim** — the exact claim text, verbatim from the finding.
2. **Evidence Summary** — brief description of the supporting evidence.
3. **Sources** — list with URLs/refs and access dates, carried from the finding.
4. **Supersession History** — append-only table; a later investigation that re-verifies, strengthens, or supersedes this claim appends a row and never rewrites prior rows:

| Date | Investigation | Event | Verdict |
|------|---------------|-------|---------|
| YYYY-MM-DD | [[project-id]] | re-verified / superseded / strengthened | verified |

5. **Connections** — wikilinks to `[[entity-id]]`s and the originating `[[project-id]]`.

**Sensitive-vault parity:** when a sensitive vault is enabled, it carries the same `claims/` structure; the existing rule that the two vaults never cross-link applies to claim notes unchanged.

---

## Wikilink Conventions

| Reference type | Format |
|----------------|--------|
| Entity | `[[entity-id]]` |
| Investigation | `[[project-id]]` |
| Methodology | `[[technique-id]]` |
| Tool | `[[tool-id]]` |
| Claim | `[[claim-id]]` |

**ID rules:**
- All IDs are **kebab-case** (lowercase, hyphens, no spaces).
- Examples: `swiss-leaks`, `john-doe`, `reverse-image-search`, `bellingcat-osm`.
- Claim IDs are `{project-id}-f{n}`: `acme-files-f1`.

**Directory fallback** — When wikilinks don't resolve (e.g., flat export or non-Obsidian vault), use relative links:

```markdown
[entity-id](../entities/entity-id.md)
```
