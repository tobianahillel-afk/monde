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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, live HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`; its global lifecycle snapshot is `IN_REVIEW` with six fresh-L2 findings still open.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 review history

`REVIEW-0003` was a fresh-context L2 of merged bootstrap commit `b88e9edf2a` and found three material gaps: missing atomic REQ identities, missing registry-specific lifecycle machines, and stale post-merge handover state.

`REVIEW-0004` was a fresh-context L2 of PR #3 at `2d4dea7e51a6cc55b159ff3001637e3ca8ec3ee9` and found six additional issues: historical TEST/REVIEW evidence had been widened, CLOSED reviews could count as approval, progress lacked explicit transitions/single-source vocabulary, current N/A values lacked justifications, and REQ-0008 overlapped REQ-0012. `TEST-0004` passed against exact corrective tree `23ef1a88e9a5106b12144d4c6649868a6a691a8f`; its PASS was recorded in `e8337d833ca0b524bed69318ca4b3691c9ce6c23`.

`REVIEW-0005` was a fresh-context L2 of PR #3 at `d5be907160c7fad3d86b2e0ce84911a3dcaab7d9` and found three further issues: TEST-0001 was still an active unbound PASS, R1/R2 acceptance lacked authority evidence, and REQ-0010 remained compound. The next correction superseded TEST-0001 without inventing a historical SHA, made blocking-finding acceptance authority machine-representable, and split AC-10 normative ownership across REQ-0010 plus REQ-0015..REQ-0019. `TEST-0005` passed against exact substantive tree `2712795dc9f10c1efed2088313d125f6f915cc98`; the PASS record was committed as `89d39c75fe29d8bbcbe016cecaa6c87d935f1c47`.

`REVIEW-0006` was the fresh-context L2 of PR #3 HEAD `8c2fbc9e44ba9f0c810b768be513d988812f1e5c`. It found two issues: negative COMPLETE review outcomes could still be interpreted as approval, and TEST-0001's replacement did not preserve the original resume/status scope. The fourth corrective pass constrained approval-capable outcomes and made TEST-0006 the scope-preserving replacement.

`REVIEW-0007` was the fresh-context L2 of PR #3 HEAD `71ecfea253066a66df6ae8302172c07f78f35752`. It found one R2/P1 defect: the first TEST-0006 tree had PROJECT_STATE describing WORK-0002 as `IN_REVIEW` while the PR #3 WORK-0002 record and progress matrix still said `PLANNED`, invalidating that first PASS.

The global WORK-0002 snapshot was reconciled through legal `PLANNED → READY → IN_PROGRESS → IN_REVIEW` transitions. TEST-0006 was then rerun on `3b4477f00953f1a352fe7c40497853fc01e103b6` and recorded PASS in `1558b2d9e85f64c755bacd623d310474ef838719`.

`REVIEW-0008` is the fresh-context L2 of PR #3 HEAD `cd7bf6a0429b4fab09fd2512c29cb4ba0a8a1e5f`. It found one R2/P1 defect: the synchronized WORK-0002 mirror imported two `read_before` paths (`docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`) that do not exist in the PR #3 tree and exist only on the PR #2 branch. That made the second TEST-0006 PASS semantically false.

Both earlier TEST-0006 executions remain preserved and explicitly `INVALIDATED` by REVIEW-0007/F-1 and REVIEW-0008/F-1 respectively. The PR #3 WORK-0002 mirror now lists only `read_before` paths that resolve in this tree. Before editing WORK-0002 implementation, an agent must explicitly checkout `feat/work-0002-governance-ci` and then follow that branch's WORK-0002 record, where `github-control-plane.md` and `ai-context-routing.md` are present and mandatory.

A third exact-SHA TEST-0006 execution was run against corrective tree `0b2c2f6a92051760e759bf2e64518188e8266012`. It verified every PR #3 WORK-0002 `read_before` path from the exact Git tree, rechecked the two branch-only documents on `feat/work-0002-governance-ci`, rechecked live PR #2 at `c50c33009d90f079e645f0ca9e1befe1a4a77ba9 / IN_REVIEW`, and revalidated lifecycle, supersession and review-outcome semantics. The third run is **PASS**, recorded in `badf011c82fc07e86d85d0e5d6efcb21223ca8cb`; `5dc3153ceee2db22496186d54180815c09e3afa2` records that result commit in TEST-0006 history.

No REVIEW-0008 finding is considered resolved solely because TEST-0006 passed. A new fresh-context L2 of the synchronized current PR #3 HEAD is still required before any completion claim.

## WORK-0002 state

PR #2 live HEAD is `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`. MONDE Gate run `34509930758` previously succeeded on that substantive head before a newer fresh-context L2 found six material issues:

1. minimum review independence must be derived from A3/A4 assurance, not only a declared target;
2. COMPLETE reviews must carry an exact reviewed commit SHA;
3. PASS test records must contain substantive proof fields, not only `id/status`;
4. every `NOT_APPLICABLE` progress dimension needs an enforced reviewed justification;
5. changed non-WORK registry records must directly seed dependency-aware context routing;
6. PR #2's own PROJECT_STATE handover must be refreshed.

WORK-0002 remains `IN_REVIEW`; its synchronized matrix dimensions are deliberately non-terminal where those six findings affect implementation/tests/review/handover. It cannot become DONE while WORK-0001 remains IN_REVIEW.

### Cross-branch resume boundary

The WORK-0002 record stored on PR #3 is only the globally readable handover mirror needed while WORK-0001 is being closed. Every path in its `read_before` list must exist in the PR #3 tree. Branch-local WORK-0002 documents are not copied into PR #3 merely to make references resolve.

To resume WORK-0002 implementation after WORK-0001/PR #3 completes:
1. checkout `feat/work-0002-governance-ci` (or its rebased successor after PR #3 merge);
2. re-read that branch's `registry/work-items/WORK-0002.yaml`;
3. then read its branch-local prerequisites, including `docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`;
4. recheck live PR #2 HEAD/checks/threads before editing.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle/traceability state

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. Active state-bound PASS evidence requires an exact tested commit SHA; a later independent review can invalidate a semantically false PASS even when its execution SHA was correctly recorded, and that invalidation must remain durable rather than being erased.

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain negative outcomes even after individual findings are later resolved.

A blocking R1/R2 finding may be non-blocking through `ACCEPTED` only with explicit accepting actor, authority role, authority evidence, rationale, date and review condition appropriate to the work item's assurance level.

WORK-0001 material bootstrap behavior is represented by `REQ-0001` through `REQ-0019`. AC-10 deliberately maps to several atomic normative owners: REQ-0010 and REQ-0015..REQ-0019.

## Next action

1. Attach the exact third TEST-0006 proof (`0b2c2f6a…` tested, `badf011c…` result, `5dc3153c…` history pointer) to REVIEW-0008/F-1 without resolving the thread.
2. Request another fresh-context L2 review of the synchronized current PR #3 HEAD after administrative evidence synchronization.
3. If the reviewer finds anything material, correct and re-prove it; otherwise record the approval-capable review and resolve only verified findings.
4. Finalize WORK-0001/progress/completion evidence and merge PR #3 only after the approval gate is truly satisfied.
5. Rebase/update PR #2 on the new main contract, fix its six current findings with regression/mutation tests and exact-SHA CI proof, and obtain its own fresh L2 before merge.
6. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

## Resume instructions

Minimum manual sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/work-items/WORK-0002.yaml`
7. `registry/status-machines.yaml`
8. `registry/progress/matrix.yaml`
9. `registry/requirements/REQ-0001.yaml` through `REQ-0019.yaml`
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0008.yaml`
11. `registry/tests/TEST-0004.yaml`, `TEST-0005.yaml`, `TEST-0006.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
