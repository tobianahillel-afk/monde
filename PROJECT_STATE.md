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

## Current branch / PR

- Branch: `bootstrap/ai-governance`
- Pull request: `#1 — docs: bootstrap AI-first MONDE repository governance`

## Current status

`IN_REVIEW`

## Completed in this sublot

- Product-level README expanded.
- Mandatory `AGENTS.md` protocol created.
- Canonical START_HERE reading/resume protocol created.
- MONDE Constitution created.
- Documentation architecture created.
- Machine-readable work-item/progress/dependency/capability registry contracts created.
- Phase → lot → sublot → work item → task → run development lifecycle defined.
- Definition of Done defined.
- Comprehensive testing strategy defined, including 100% meaningful line/branch coverage target and real-system validation.
- Development/security rules defined.
- ADR process defined.
- PR and feature/bug issue templates created.
- 50-criterion / 100-point engineering scorecard created.
- Bootstrap PR #1 opened for review.

## Remaining before SUBLOT-0.1 is complete

- Review PR #1 against scope/reuse, architecture, testing, security, documentation/handover gates.
- Resolve any review findings.
- Update `WORK-0001` and progress matrix with review result.
- Merge only when review gates are satisfied.

## Blockers / owner actions

### Repository visibility

Repository visibility was observed as **public** on 2026-09-10. MONDE is expected to contain sensitive architectural material. The repository owner should review and preferably change visibility to private before later sensitive/high-risk specifications are committed.

This connector does not expose a repository-visibility mutation, so this setting has not been changed automatically.

## Next action

Perform structured review of PR #1. Do not start product capability implementation until SUBLOT-0.1 is merged/completed and the next work item is explicitly activated.

## Resume instructions

Next agent must read, in order:

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. files listed in `WORK-0001.read_before`
7. PR #1 discussion/diff for current review state

No prior chat history is required to understand the current bootstrap state.
