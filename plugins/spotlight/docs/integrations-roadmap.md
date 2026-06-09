---
title: "Spotlight Integrations Roadmap"
description: "Forthcoming Spotlight integrations whose architecture is ready but API access has not yet been granted."
type: roadmap
status: tracking
---

# Integrations Roadmap

These integrations have architecture ready in Spotlight (manifest + integration document patterns) and are awaiting API access from the provider before being activated. Each is a three-file drop-in when access arrives: `integrations/<name>/manifest.json`, `integrations/<name>/integration.md`, and an entry in the `skills/integrations/SKILL.md` routing table.

## Deferred

- **Serus AI** — due-diligence platform for investigative leads. Use case: corporate beneficial-ownership and adverse-media screening.
- **Thinkpol** — grey-web intelligence. Use case: monitoring closed forums and dark-web sources for entity mentions and document leaks.
- **Reality Defender** — deepfake detection. Use case: validating image and video evidence for synthetic-media artefacts before citation.
- **Klarety** — disinformation detection. Use case: scoring claims and narratives for coordinated-inauthentic-behaviour signals during fact-checking.

## Activation checklist (when API access arrives)

1. Create `integrations/<name>/manifest.json` per the standard pattern (see existing integrations).
2. Author `integrations/<name>/integration.md` documenting the routing rules, sensitive-mode behaviour, and any auth env vars.
3. Add the integration to the routing table in `skills/integrations/SKILL.md`.
4. Verify `python3 integrations/preflight.py --json` discovers the new integration without code changes.
5. Move the entry out of this roadmap once shipped.
