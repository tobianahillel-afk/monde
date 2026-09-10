# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git; live PR/check/thread truth lives in GitHub and must be rechecked before merge decisions.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

## Current blocking sublot

**SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**

PR #1 was already squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`. WORK-0001 remains `IN_REVIEW` while its post-merge A3 assurance debt is independently corrected and re-reviewed.

## Active work

- `WORK-0001` — post-merge assurance correction on **PR #3** / branch `chore/work-0001-assurance-closure`; it blocks truthful completion of WORK-0002.
- `WORK-0002` — governance automation on open PR #2 / branch `feat/work-0002-governance-ci`; implementation is advanced but remains `IN_REVIEW` and depends on WORK-0001.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 review history

`REVIEW-0003` was a fresh-context L2 of merged bootstrap commit `b88e9edf2a` and found three material gaps: missing atomic REQ identities, missing registry-specific lifecycle machines, and stale post-merge handover state.

`REVIEW-0004` was a fresh-context L2 of PR #3 at `2d4dea7e51a6cc55b159ff3001637e3ca8ec3ee9` and found six additional issues: historical TEST/REVIEW evidence had been widened, CLOSED reviews could count as approval, progress lacked explicit transitions/single-source vocabulary, current N/A values lacked justifications, and REQ-0008 overlapped REQ-0012. `TEST-0004` subsequently passed against exact corrective tree `23ef1a88e9a5106b12144d4c6649868a6a691a8f`; its PASS was recorded in `e8337d833ca0b524bed69318ca4b3691c9ce6c23`.

`REVIEW-0005` was a fresh-context L2 of PR #3 at `d5be907160c7fad3d86b2e0ce84911a3dcaab7d9` and found three further issues: TEST-0001 was still an active unbound PASS, R1/R2 acceptance lacked authority evidence, and REQ-0010 remained compound. The next correction superseded TEST-0001 without inventing a historical SHA, made blocking-finding acceptance authority machine-representable, and split AC-10 normative ownership across REQ-0010 plus REQ-0015..REQ-0019. `TEST-0005` passed against exact substantive tree `2712795dc9f10c1efed2088313d125f6f915cc98`; the PASS record was committed as `89d39c75fe29d8bbcbe016cecaa6c87d935f1c47`.

`REVIEW-0006` is the fresh-context L2 of PR #3 HEAD `8c2fbc9e44ba9f0c810b768be513d988812f1e5c`. It found two remaining issues:

1. a review in state `COMPLETE` with outcome `CHANGES_REQUIRED` or `BLOCKED` could still be interpreted as approval evidence because approval-capable outcomes were not explicitly constrained;
2. TEST-0001 correctly became SUPERSEDED but pointed to TEST-0005, which did not re-execute TEST-0001's original README/PROJECT_STATE resume routing and status-vocabulary scope.

The current fourth corrective pass addresses both findings. `registry/status-machines.yaml` now declares `approval_capable_outcomes: [APPROVE, APPROVE_WITH_FOLLOWUP]` and explicitly states that COMPLETE+CHANGES_REQUIRED/BLOCKED is durable negative evidence, never approval. TEST-0001 now points to `TEST-0006`, which re-executes the original resume-routing, active-work-routing and status-vocabulary contracts on an exact revision and also verifies review-outcome polarity.

`TEST-0006` remains **PLANNED** until this synchronized corrective tree has a stable exact commit SHA. It must then follow the canonical PLANNED → READY → RUNNING → PASS lifecycle and may pass only if the cold-resume path and both REVIEW-0006 failure modes are actually absent.

## WORK-0002 state

PR #2 substantive HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9` previously passed MONDE Gate run `34509930758` after its then-known threads were resolved. A newer fresh-context L2 on that same HEAD found six additional issues that remain open: assurance-derived minimum review independence, mandatory reviewed SHA for completed reviews, substantive PASS test evidence, N/A justification enforcement, direct changed-registry context seeding, and stale handover state.

WORK-0002 remains `IN_REVIEW`; do not merge or mark it DONE before WORK-0001 is DONE and those six findings are corrected, re-proven and freshly re-reviewed.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle/traceability state

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. Active state-bound PASS evidence requires an exact tested commit SHA; unprovable legacy PASS evidence is superseded rather than repaired by guessing, and replacement evidence must preserve or explicitly partition its represented scope.

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain negative outcomes even after individual findings are later resolved.

A blocking R1/R2 finding may be non-blocking through `ACCEPTED` only with explicit accepting actor, authority role, authority evidence, rationale, date and review condition appropriate to the work item's assurance level.

WORK-0001 material bootstrap behavior is represented by `REQ-0001` through `REQ-0019`. AC-10 deliberately maps to several atomic normative owners: REQ-0010 and REQ-0015..REQ-0019.

## Next action

1. Commit this synchronized fourth corrective pass and obtain its exact SHA while TEST-0006 remains PLANNED.
2. Execute TEST-0006 on that exact SHA, including a real cold-read of README → START_HERE/AGENTS → PROJECT_STATE → WORK-0001 and status-machine/matrix checks.
3. Record TEST-0006 PASS only if all checks succeed, then attach exact-SHA proof to both REVIEW-0006 GitHub threads without resolving them.
4. Request another fresh-context L2 review of the corrected PR #3 HEAD.
5. If the reviewer finds anything material, correct and re-prove it; otherwise record the approving review and resolve only verified findings.
6. Finalize WORK-0001/progress/completion evidence and merge PR #3 only after the approval gate is truly satisfied.
7. Rebase/update PR #2 on the new main contract, fix its current fresh-L2 findings with regression/mutation tests and exact-SHA CI proof, and obtain its own fresh L2 before merge.
8. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

## Resume instructions

Minimum manual sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/status-machines.yaml`
7. `registry/requirements/REQ-0001.yaml` through `REQ-0019.yaml`
8. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0006.yaml`
9. `registry/tests/TEST-0004.yaml`, `TEST-0005.yaml`, `TEST-0006.yaml`, plus superseded historical `TEST-0001.yaml`
10. live PR #3 reviews/threads
11. live PR #2 checks and unresolved threads

No prior chat history is required.
