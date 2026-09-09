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

- `WORK-0001` — bootstrap AI-first governance, specification quality, navigation, tracking, testing/review rules and repository assurance framework.

## Current branch / PR

- Branch: `bootstrap/ai-governance`
- Pull request: `#1 — docs: bootstrap AI-first MONDE repository governance and assurance`

## Current status

`IN_REVIEW`

## Completed in this sublot

- Product-level README and mandatory AI resume protocol.
- MONDE Constitution and canonical documentation architecture.
- Machine-readable work/progress/dependency/capability contracts.
- `REQ-*`, `ASM-*`, `RISK-*`, `REVIEW-*`, `TEST-*`, `EXP-*` registry contracts and central registry index.
- End-to-end traceability contract.
- Phase → lot → sublot → work item → task → run development lifecycle.
- Definition of Ready and Definition of Done.
- Specification Quality Protocol for canonical documentation.
- Research Protocol for evidence-based specification work.
- Review Council with explicit engineering/scientific/security/operations hats and review independence levels.
- Risk-based assurance levels A0–A4.
- Comprehensive testing strategy and 100% meaningful line/branch coverage target.
- Advanced verification ladder: property, fuzzing, mutation, metamorphic, differential, historical replay, fault injection and narrow formal/model-based verification.
- Reproducibility/backtesting protocol with strict knowledge-at-T / temporal-leakage rules.
- Non-functional quality attributes: performance, freshness, reliability, cost/resources, observability, recovery/SLO direction, security and maintainability.
- Threat-modeling protocol for security-sensitive changes.
- Development/security rules and ADR process.
- PR/feature/bug templates synchronized with current assurance process.
- 50-criterion / 100-point engineering scorecard with non-compensable hard gates.
- Phase-0 roadmap and planned `WORK-0002`, `WORK-0003`, `WORK-0004`.
- Structured review evidence stored as `REVIEW-0001` and first repository-resume validation stored as `TEST-0001`.

## Review findings resolved during bootstrap

- Status vocabulary mismatch between registry state and canonical vocabulary.
- Missing specification/research/assumption/traceability governance in the initial process.
- PR template drift after assurance framework expansion.
- Feature proposal template missing assumptions/research/NFR/review requirements.

These defects were found through the review process and corrected before merge.

## Remaining before SUBLOT-0.1 is complete

- Fresh-context/owner L2 review of PR #1 (current structured review is same-context L1).
- Owner decision/action on repository visibility before sensitive/high-risk specifications are added.
- Resolve any findings from that independent review.
- Merge only when required gates are satisfied.
- After merge, set `WORK-0001`/progress state to `DONE` and activate the next approved work item explicitly.

## Planned next work

- `WORK-0002` / `SUBLOT-0.2` — automate governance/specification/traceability validation in CI, including registry schemas, orphan detection, review completion and architecture fitness functions.
- `WORK-0003` / `SUBLOT-0.3` — configure repository visibility, branch protection, required checks and merge policy.
- `WORK-0004` / `LOT-1 / SUBLOT-1.1` — inventory every previously validated MONDE capability and assign stable CAP IDs using the specification-quality process.

No planned work item becomes active automatically.

## Blockers / owner actions

### Repository visibility

Repository visibility was observed as **public** on 2026-09-10. MONDE is expected to contain sensitive architectural material. The repository owner should review and preferably change visibility to private before later sensitive/high-risk specifications are committed.

This connector does not expose a repository-visibility mutation, so this setting has not been changed automatically.

### Automated enforcement

No CI status checks are currently attached to PR #1. The rules now exist as canonical contracts, but automated enforcement still belongs to `WORK-0002`; branch/security settings belong to `WORK-0003`.

## Current quality interpretation

The governance/specification framework is now deliberately rigorous, but the repository must **not** claim maturity from documentation alone. Automation, executable architecture/epistemic fitness functions, MONDE Mini, real application test suites and production evidence remain future work.

The next quality gain should come from **enforcement**, not adding more parallel governance prose.

## Next action

Perform a fresh-context/owner structured review of PR #1 using the required Review Council hats. If accepted, merge the bootstrap and then explicitly activate the next work item; recommended order is `WORK-0002` (automation) before deep product specification so the documentation process can enforce itself.

## Resume instructions

Next agent must read, in order:

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/README.md`
6. `registry/work-items/WORK-0001.yaml`
7. `registry/reviews/REVIEW-0001.yaml`
8. files listed in `WORK-0001.read_before`
9. PR #1 discussion/diff for current review state

No prior chat history is required to understand the current bootstrap state.
