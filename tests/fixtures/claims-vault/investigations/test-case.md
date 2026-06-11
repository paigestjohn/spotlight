---
id: test-case
title: "Test Case: Acme Consultancy Payments"
status: confirmed
date: 2026-06-01
regions: [Testland]
entities: [acme-corp, john-doe]
methodology: []
tools: []
tags: [fixture]
verified_count: 1
total_findings: 3
---

## Summary

Fixture investigation used by tests/vault-claims-check.py.

## Key Findings

### F1 — Undisclosed consultancy contract

- **Claim:** Acme Corp paid John Doe through an undisclosed consultancy contract.
- **Confidence:** high
- **Verdict:** verified
- **Evidence:** Registry filing 123.
- **Sources:** https://example.org/registry/filing-123 (accessed 2026-06-01)
- **Perspective:** independent observer

### F2 — Payment routed via subsidiary

- **Claim:** The payments were routed through an Acme subsidiary.
- **Confidence:** medium
- **Verdict:** partially_verified
- **Evidence:** Bank reference codes consistent with subsidiary accounts.
- **Sources:** https://example.org/leak/doc-9 (accessed 2026-06-01)
- **Perspective:** official (leaked)

### F3 — Doe approved the contract himself

- **Claim:** John Doe approved his own contract.
- **Confidence:** low
- **Verdict:** unverified
- **Evidence:** Single anonymous statement.
- **Sources:** interview note
- **Perspective:** affected community

## Connections

[[acme-corp]], [[john-doe]]

## Gaps

- Approval chain unresolved (F3).

## Methodology Applied

None (fixture).
