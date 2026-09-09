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
- Machine-readable `REQ-*`, `ASM-*`, `RISK-*`, `REVIEW-*`, `TEST-*` and `EXP-*` contracts created.
- Canonical registry index and end-to-end traceability contract created.
- Phase → lot → sublot → work item → task → run development lifecycle defined.
- Definition of Ready and Definition of Done defined.
- Canonical Specification Quality Protocol created for documentation/spec work.
- Multi-role Review Council and risk-based assurance levels created.
- Comprehensive testing strategy defined, including 100% meaningful line/branch coverage target and real-system validation.
- Advanced verification ladder defined: property, fuzzing, mutation, metamorphic, differential, historical replay, fault injection and narrow formal/model-based verification.
- Reproducibility/backtesting protocol defined with strict knowledge-at-T / temporal-leakage rules.
- Non-functional quality attributes formalized: performance, freshness, reliability, SLOs, cost/resources, observability, recovery, security and maintainability.
- Research protocol created so material specification facts are verified from explicit sources rather than implicit model memory.
- Threat-modeling protocol created for security-sensitive trust-boundary changes.
- Development/security rules and ADR process defined.
- PR and feature/bug issue templates created.
- 50-criterion / 100-point engineering scorecard created with non-compensable hard gates.
- Phase-0 roadmap created.
- Follow-up work items created for governance automation, repository protections and historical capability inventory.
- Bootstrap PR #1 opened and received structured review; one status-vocabulary inconsistency was found and fixed.

## Remaining before SUBLOT-0.1 is complete

- Re-review PR #1 after the specification/scientific-governance expansion.
- Resolve any additional review findings.
- Owner/final review of PR #1.
- Merge only when review gates are satisfied.
- After merge, update `WORK-0001`/progress state to `DONE` and activate the next approved work item explicitly.

## Planned next work

- `WORK-0002` / `SUBLOT-0.2` — automate governance/specification/traceability validation in CI, including registry schemas, orphan detection and architecture fitness functions.
- `WORK-0003` / `SUBLOT-0.3` — configure repository visibility, branch protection, required checks and merge policy.
- `WORK-0004` / `LOT-1 / SUBLOT-1.1` — inventory every previously validated MONDE capability and assign stable CAP IDs using the new specification-quality protocol.

No planned work item becomes active automatically.

## Blockers / owner actions

### Repository visibility

Repository visibility was observed as **public** on 2026-09-10. MONDE is expected to contain sensitive architectural material. The repository owner should review and preferably change visibility to private before later sensitive/high-risk specifications are committed.

This connector does not expose a repository-visibility mutation, so this setting has not been changed automatically.

### Repository protection

No CI status checks are currently attached to PR #1. Branch protection/security settings still require `WORK-0002`/`WORK-0003` and owner configuration where GitHub permissions/settings are not exposed through the current connector.

## Current quality interpretation

The governance framework is now substantially stronger, but the repository must **not** claim maturity merely from documentation. Automated enforcement, actual tests, MONDE Mini, architecture fitness functions, real-system validation and production implementation remain future work. The current numeric score remains intentionally conservative.

## Next action

Perform a fresh structured review of PR #1 using the Review Council, especially Architecture/Reuse, V&V, Security, Data/Epistemic, Performance/SRE, Documentation/Traceability and Skeptic perspectives. Do not start product capability implementation until SUBLOT-0.1 is merged/completed and the next work item is explicitly activated.

## Resume instructions

Next agent must read, in order:

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/README.md`
6. `registry/work-items/WORK-0001.yaml`
7. files listed in `WORK-0001.read_before`
8. PR #1 discussion/diff for current review state

No prior chat history is required to understand the current bootstrap state.
