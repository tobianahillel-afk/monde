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

PR #1 was squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`. `WORK-0001` remains `IN_REVIEW` while its post-merge A3 assurance debt is independently corrected and re-reviewed.

## Active work

- `WORK-0001` — corrective assurance work on **PR #3** / branch `chore/work-0001-assurance-closure`; it blocks truthful completion of WORK-0002.
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, last rechecked live at HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`, lifecycle `IN_REVIEW`, with its six fresh-L2 findings still open.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is `REVIEW-0003` through `REVIEW-0011`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key current facts:

- `REVIEW-0007` invalidated the first TEST-0006 PASS because PROJECT_STATE, WORK-0002 and the progress matrix disagreed on the global WORK-0002 lifecycle.
- `REVIEW-0008` invalidated the second TEST-0006 PASS because the PR #3 WORK-0002 mirror referenced two branch-only `read_before` files that were absent from the tested tree.
- `REVIEW-0009`, on `1e3f539b89afbbb07de63271682a1db06f47550c`, found missing reviewed `DONE → IN_REVIEW` reopening semantics and TEST-0004's immutable historical `PLANNED → PASS` edge.
- `REVIEW-0010`, on `14c3d3fcc6dd96af9d2e5acd9f02d2d957c03425`, confirmed those lifecycle corrections but found one R3/P2 traceability gap: TEST-0007 protected REQ-0006, while REQ-0006 still pointed only to the older TEST-0004.
- `REVIEW-0011`, on `c8fbfa51ac04b566f337ee606a806e42881b67f2`, found no new substantive lifecycle/test/traceability defect but identified one R3/P2 handover-currentness defect: this file still told a cold-resuming agent to perform REVIEW-0010/test synchronization that was already complete.

## Current correction and proof

`registry/status-machines.yaml` version 5:

- permits progress `DONE → IN_REVIEW` only as an explicit reviewed reopening when later evidence materially re-questions completion;
- requires normal completion gates before returning to DONE;
- keeps generic TEST lifecycle strict as `PLANNED → READY → RUNNING → PASS`;
- records one exact historical TEST-0004 `PLANNED → PASS` migration exception bound to `98e8cdccc07bd3c2d8313d81f296f49c97c44379 → e8337d833ca0b524bed69318ca4b3691c9ce6c23`;
- marks that exception historical-only and forbids future reuse.

The fourth TEST-0006 execution remains PASS on exact synchronized tree `fa55004d1623ab2aa66c14b62bb036f6e335f041`; result `80eb23da21d76d5b87134164ce46954423a04e95`, history pointer `772f45b2f7eacb3d2dfbeb39f3c1aca089b19959`.

For REVIEW-0010/F-1, REQ-0006 now includes TEST-0007 in both `verification.test_ids` and `verification.acceptance_evidence`, while TEST-0007 continues to protect REQ-0006. TEST-0007 was reopened `PASS → READY`, expanded with explicit forward/reverse traceability assertions, and rerun on exact tree `c27a98b94c4f59c5778b9c7d30e447536a70a452` through `READY → RUNNING → PASS`. The PASS result is `07fb9baf3f76437059b73f7805a5edd36d704cc6`; `7560d7265c873c8ab25ef7de423f75fab8aa33e0` records that execution in history.

REVIEW-0011/F-1 is corrected by this handover update only. No tested contract, requirement mapping, status machine, or TEST-0006/TEST-0007 assertion is changed by the correction; therefore the existing exact-SHA substantive proof remains applicable. The finding remains open until another fresh independent L2 verifies the resulting frozen HEAD.

## WORK-0002 cross-branch boundary

The WORK-0002 record stored on PR #3 is only the globally readable handover mirror needed while WORK-0001 closes. Every path in its PR #3 `read_before` list must exist in the PR #3 tree.

To resume WORK-0002 implementation after WORK-0001/PR #3 completes:

1. checkout `feat/work-0002-governance-ci` (or its rebased successor after PR #3 merge);
2. re-read that branch's `registry/work-items/WORK-0002.yaml`;
3. then read branch-local prerequisites, including `docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`;
4. recheck live PR #2 HEAD/checks/threads before editing.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle state

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. A later independent review can invalidate a SHA-bound PASS if a claimed assertion is false; invalidation is preserved rather than erased.

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain negative outcomes.

A blocking R1/R2 finding may become non-blocking through `ACCEPTED` only with explicit accepting actor, authority role, authority evidence, rationale, date and review condition appropriate to assurance level.

## Next action

1. Reply to REVIEW-0011/F-1 with this exact handover correction, without resolving the thread prematurely.
2. Freeze the resulting PR #3 HEAD and request another fresh-context L2 explicitly against that SHA.
3. If that review finds anything material, correct and re-prove it. If it reports no material defect, record the approval-capable L2 evidence and resolve only findings whose underlying defects have been independently verified as corrected.
4. Finalize WORK-0001/progress/completion only after the approval gate is genuinely satisfied, then merge PR #3.
5. After PR #3 merge, update/rebase PR #2 onto the new main contract, fix its six existing fresh-L2 findings with regression/mutation/exact-SHA CI proof, and obtain its own fresh L2 before merge.
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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0011.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
