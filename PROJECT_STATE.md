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

PR #2 previously diverged from the newly merged WORK-0001 contract at `ab62faa1743705600a0f11335579db68a2166ab3`. An exact-head merge probe against `main@29086643387ff46ab6636dd2fa3014efccc10165` found four semantic conflicts only: `PROJECT_STATE.md`, `registry/progress/matrix.yaml`, `registry/work-items/WORK-0002.yaml`, and `registry/work-items/WORK-0003.yaml`.

The integration preserves the final WORK-0001/v10 canonical state from `main`, keeps the richer branch-local WORK-0002 implementation/review/test graph from PR #2, and keeps the expanded WORK-0003 control-plane plan from PR #2. WORK-0002 remains `IN_REVIEW`; this integration is not completion evidence.

## Current WORK-0002 gate

The latest branch-local corrective slice addresses six fresh-context findings from the earlier L2 on `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`:

1. A3/A4 assurance must impose minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. COMPLETE review evidence must bind an exact `artifact.commit_sha`.
3. PASS TEST records must carry substantive protected-contract/case/execution evidence.
4. Every `NOT_APPLICABLE` progress dimension needs a non-empty work-item justification.
5. Context routing must seed dependency closure from changed non-WORK registry records.
6. Handover state must remain current and transition-stable.

After this main integration, the required sequence is:

1. Run the complete MONDE Gate on the exact integrated PR #2 HEAD. Treat any deterministic validator, schema/change guard, coverage, mutation, secret scan, Dependency Review, CodeQL or live-gate failure as blocking evidence.
2. Recheck the six review threads against exact integrated evidence; do not resolve them by author assertion.
3. Obtain a new fresh-context L2 on the final integrated PR #2 candidate.
4. Only a clean approval-capable independent result may close the review gate and allow WORK-0002 completion synchronization.
5. Run the final merge-candidate gate and merge only with an exact-head guard.
6. Continue with WORK-0003, then WORK-0004.

## WORK-0001 provenance boundary

WORK-0001 final closure remains canonical on `main`: REVIEW-0028 independently verified the substantive final-v10 candidate; all 41 historical findings and their matching PR #3 threads were closed; the final deterministic audit passed before squash merge. PR #2 must consume that merged contract, not recreate or rewrite its history.

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
10. branch-local REVIEW-0002 / TEST-0002 / TEST-0003 records
11. live PR #2 HEAD, checks, reviews and threads
12. `tools/governance/` and `tests/governance/`

No prior chat history is required.
