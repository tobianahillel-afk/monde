# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **SUBLOT-0.1 / WORK-0001** is `DONE / A3` and was squash-merged to `main` as `29086643387ff46ab6636dd2fa3014efccc10165`.
- **SUBLOT-0.2 / WORK-0002** is the active `IN_REVIEW / A3` work on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain planned downstream work.

## WORK-0002 integrated state

PR #2 previously diverged from the newly merged WORK-0001 contract at `ab62faa1743705600a0f11335579db68a2166ab3`. Integration commit `b63fc190a0fa3e02ad1b3e03d0d01b16617c9b49` merged that branch-local history with `main@29086643387ff46ab6636dd2fa3014efccc10165`. Git ancestry confirms the main commit remains the merge base and ancestor of the PR #2 line (`behind_by: 0`). WORK-0002 remains `IN_REVIEW`; integration and author-side proof are not completion or independent-approval evidence.

## Latest deterministic WORK-0002 proof

REVIEW-0029 recorded six additional fresh-context findings against frozen predecessor `40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5`. Its negative evidence was durably imported and bound before correction. The guarded corrective runner then operated only from exact predecessor `4eb23ffcae5eab9bb6ead05104258893df96c93a` and published correction candidate `a0d4c112294630a7b82e06925292567bb45c8c52` only after the full deterministic proof passed.

Admin proof run **`34838119366`**, job **`103956543083`**, proves the published correction tree before push:

- **116 tests PASS**;
- governance implementation: **1306/1306 statements** and **686/686 branches**, **100.00% line + branch coverage**;
- **27/27 critical governance mutations killed**;
- repository governance validation: **0 errors / 0 warnings** across 66 records;
- strict governance validation: **0 errors**;
- path-safety validation: **0 errors**;
- base-to-head change guard against `main@29086643387ff46ab6636dd2fa3014efccc10165`: **0 errors**;
- guarded push succeeded from `4eb23ffcae5eab9bb6ead05104258893df96c93a` to exact candidate `a0d4c112294630a7b82e06925292567bb45c8c52`.

The immediately generated pull-request MONDE Gate run **`34838309139`** on `a0d4c112294630a7b82e06925292567bb45c8c52` ended `action_required` because the synchronize event came from `github-actions[bot]`. It created no usable gate proof and must not be treated as success or deterministic failure. This PROJECT_STATE synchronization is intentionally a transition-stable repository-user commit so the real pull-request gate can execute on the new exact candidate.

## Current WORK-0002 independent-review closure set

There are **12 unresolved PR #2 review threads/findings**. None may be author-resolved.

The six earlier findings require:

1. A3/A4 assurance to impose minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. COMPLETE review evidence to bind an exact `artifact.commit_sha`.
3. PASS TEST records to carry substantive protected-contract/case/execution evidence.
4. Every `NOT_APPLICABLE` progress dimension to carry a non-empty justification.
5. Context routing to seed dependency closure from changed non-WORK registry records.
6. Handover state to remain current and transition-stable.

REVIEW-0029 added six further contract findings requiring:

1. lifecycle validation to enforce canonical initial-state materialization while allowing only exact, record/commit-bound historical or preauthorized imports;
2. requirement `PROPOSED → ACCEPTED` transitions to enforce the v10 content-bound independent-review and cold-read preconditions;
3. a current `PASS` TEST used as completion evidence to carry concrete revision-bound execution evidence rather than only a test definition;
4. blocking finding `ACCEPTED` disposition to resolve and validate the exact authority matrix role/rule/evidence contract;
5. COMPLETE review artifact evidence to use a full immutable 40-hex commit that exists and is valid in current ancestry/freshness checks;
6. freshness/change-control to distinguish required TEST contract changes from execution-evidence churn and compute endpoint changes from the actual merge base.

The author-side correction for all 12 findings is now on the PR branch, but correction plus deterministic proof does not itself close any finding.

## Current WORK-0002 gate

Required sequence from this handover state:

1. Re-query live PR #2 HEAD after this transition-stable synchronization and require a complete MONDE Gate on that exact SHA. Treat any validator, schema/change guard, coverage, mutation, secret scan, Dependency Review, CodeQL or live-gate failure as blocking evidence. A workflow with no jobs is never substitute proof.
2. Keep all 12 existing review threads unresolved until independent verification.
3. Obtain a **fresh-context L2** on the exact final gated PR #2 candidate. The reviewer must inspect the accumulated implementation, all 12 open findings, REVIEW-0029 corrections, historical-integration exceptions, PASS TEST revision binding and graph-aware v10 semantics.
4. Only an approval-capable independent result with no new blocking finding may justify durable review evidence and subsequent thread/finding closure.
5. Synchronize WORK-0002 completion only after those independent gates are satisfied, then run the final merge-candidate gate and merge only with an exact-head guard.
6. Continue with WORK-0003, then WORK-0004.

## WORK-0001 provenance boundary

WORK-0001 final closure remains canonical on `main`: REVIEW-0028 independently verified the substantive final-v10 candidate; all 41 historical findings and their matching PR #3 threads were closed; the final deterministic audit passed before squash merge. PR #2 consumes that merged contract and must not recreate or rewrite its history.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public visibility.

## Product/UI/UX owner gate

Product specification and product identity remain owner-gated decisions. Agents must not silently canonize product experience, UI/UX, visual identity, brand, color system, interface density, interaction language, emotional/psychovisual tone or other strong design choices. Major product-function decisions require explicit owner co-design rather than irreversible invention.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/progress/matrix.yaml`
7. `registry/status-machines.yaml`
8. `docs/03_ARCHITECTURE/github-control-plane.md`
9. `docs/13_QUALITY/ai-context-routing.md`
10. `registry/reviews/REVIEW-0029.yaml` plus branch-local REVIEW-0002
11. `registry/tests/TEST-0002.yaml` and `registry/tests/TEST-0003.yaml`
12. live PR #2 HEAD, checks, reviews and all review threads
13. `tools/governance/` and `tests/governance/`

No prior chat history is required.
