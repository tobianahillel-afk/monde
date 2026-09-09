# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> This file is the **fast resume point**. Keep it short, current and factual. Detailed implementation history belongs in work items and PRs.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

Goal: make MONDE safely resumable and developable by AI agents without relying on chat history or rediscovering architecture.

## Current sublot

**SUBLOT-0.1 — Governance bootstrap**

## Active work

- `WORK-0001` — bootstrap AI-first governance, navigation, tracking, test/review rules and repository scorecard.

## Current branch

`bootstrap/ai-governance`

## Current status

`IN_PROGRESS`

## Completed in this sublot

- Repository identified and inspected.
- Product-level README expanded.
- Mandatory AI agent operating protocol created.
- Canonical START_HERE reading/resume protocol created.

## Remaining before SUBLOT-0.1 is complete

- MONDE Constitution.
- Work-item schema and first work item.
- Progress/dependency matrices.
- Development lifecycle and lot/sublot protocol.
- Definition of Done and test strategy.
- Development/security rules.
- ADR process.
- PR/issue templates.
- Repository quality scorecard.
- Bootstrap PR review.

## Blockers

None currently identified.

## Important repository setting

Repository visibility was observed as **public** on 2026-09-10. MONDE is expected to contain sensitive architectural material; owner should review whether repository visibility should be private before sensitive specifications are committed.

## Next action

Complete the governance bootstrap files on `bootstrap/ai-governance`, create the bootstrap PR, review it against the scorecard and only then move to product/capability documentation.

## Resume instructions

Next agent must read:

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml` once present
6. files referenced by that work item's `read_before`

Do not begin implementation of MONDE product capabilities during PHASE-0 unless explicitly scheduled by a work item.
