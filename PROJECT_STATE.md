# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git; live PR/check/thread truth lives in GitHub.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

## Current sublot

**SUBLOT-0.2 — Governance automation / P0-P2 hardening**

## Active work

- `WORK-0002` — governance automation and GitHub control-plane hardening.

## Current branch / PR

- Branch: `feat/work-0002-governance-ci`
- Pull request: `#2 — feat(governance): automate MONDE repository validation`
- PR state in repository prose: draft during substantive P0-P2 proof. Always verify live GitHub state before merge decisions.

## Current status

`IN_REVIEW`

## Last completed milestone

PR #1 — `docs: bootstrap AI-first MONDE repository governance and assurance` was squash-merged into `main` at `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`.

## WORK-0002 current scope

The hardened implementation includes:

- deterministic registry/status/reference/path validation;
- JSON Schema validation;
- DONE progress-dimension and review-evidence validation;
- reverse WORK↔progress membership;
- Markdown link-title handling and path containment;
- base/head and per-commit transition validation;
- immutable IDs / published-record deletion guard;
- post-READY semantic scope-drift and review-freshness guards;
- meta-governance A3/A4 change guard;
- immutable Action/Docker pins and high-confidence secret-pattern checks;
- hash-locked Python governance dependencies;
- reusable governance workflow, Dependency Review and CodeQL;
- stable `MONDE / Merge Gate`;
- SHA-bound live GitHub HEAD/mergeability/unresolved-thread gate;
- AI context manifest with MUST_READ / SHOULD_READ / ON_DEMAND tiers;
- CI evidence artifacts and job summaries.

## Review state

The original Codex review on PR #2 identified four unresolved findings on the old HEAD:

- review evidence was not validated deeply enough before DONE;
- DONE progress dimensions could remain incomplete;
- work items could be absent from the progress matrix;
- Markdown links with optional titles could false-fail.

The substantive P0-P2 hardening implements regressions for all four. Do not resolve those GitHub threads until the new substantive HEAD is pushed and CI proves the fixes there.

`REVIEW-0002` remains the same-context L1 review. A fresh L2 review on the substantive final HEAD is required before `WORK-0002 = DONE`.

## Evidence model

`TEST-*` / `REVIEW-*` records define durable obligations. GitHub checks, artifacts, review threads and run logs are live SHA-bound executions. A historical run must never be relabeled as proof of a later HEAD.

## Planned next work

- `WORK-0003` — intentional repository visibility, main/ruleset protection, required gate, merge/security policy and real-setting verification.
- `WORK-0004` — exhaustive capability inventory only after WORK-0003 is complete.

## Owner/admin limitation

The current GitHub connector can modify repository files/branches/PRs but does not expose full repository-administration mutations such as visibility/ruleset changes. WORK-0003 must distinguish settings applied through available tooling from explicit owner actions still required in GitHub UI/API.

## Next action

1. Publish the substantive P0-P2 commit to PR #2.
2. Execute the real MONDE Gate on that exact HEAD.
3. Fix any real CI discrepancy without weakening gates.
4. Resolve Codex threads only after the proven fixes are visible.
5. Move PR out of draft and obtain fresh L2 review on the substantive HEAD.
6. Add only administrative finalization records/statuses, rerun the gate, then merge if all live gates pass.
7. Start WORK-0003; do not begin WORK-0004 first.

## Resume instructions

Use the AI context manifest when available. Minimum manual sequence:

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `docs/03_ARCHITECTURE/github-control-plane.md`
7. `docs/13_QUALITY/ai-context-routing.md`
8. `.github/workflows/governance.yml`
9. `tools/governance/`
10. `tests/governance/`
11. live PR #2 checks and unresolved threads

No previous chat history is required.
