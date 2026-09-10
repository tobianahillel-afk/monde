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

The durable review chain is `REVIEW-0003` through `REVIEW-0009`. Earlier corrective tests are `TEST-0004`, `TEST-0005`, `TEST-0006`, and the new lifecycle-history proof `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key current facts:

- `REVIEW-0007` invalidated the first TEST-0006 PASS because PROJECT_STATE, WORK-0002 and the progress matrix disagreed on the global WORK-0002 lifecycle.
- `REVIEW-0008` invalidated the second TEST-0006 PASS because the PR #3 WORK-0002 mirror referenced two branch-only `read_before` files that were absent from the tested tree.
- A third TEST-0006 execution passed on exact corrected tree `0b2c2f6a92051760e759bf2e64518188e8266012`; result was recorded in `badf011c82fc07e86d85d0e5d6efcb21223ca8cb` and its history pointer in `5dc3153ceee2db22496186d54180815c09e3afa2`.
- Fresh-context `REVIEW-0009` then reviewed PR #3 at `1e3f539b89afbbb07de63271682a1db06f47550c` and found two additional R2/P1 lifecycle-history defects: progress could not truthfully reopen `DONE → IN_REVIEW`, and TEST-0004's immutable historical `PLANNED → PASS` edge violated the newly canonical test lifecycle.

## REVIEW-0009 correction

`registry/status-machines.yaml` version 5 now:

- permits progress `DONE → IN_REVIEW` only as an explicit reviewed reopening after new evidence, a review finding, dependency change, or invalidated proof materially re-questions completion;
- requires the owning handover/evidence to identify that trigger and requires normal completion gates before returning to DONE;
- keeps the generic test lifecycle strict as `PLANNED → READY → RUNNING → PASS`;
- records one exact historical migration exception only for TEST-0004 `PLANNED → PASS`, bound to before-commit `98e8cdccc07bd3c2d8313d81f296f49c97c44379` and transition commit `e8337d833ca0b524bed69318ca4b3691c9ce6c23`;
- forbids reuse of that exception for any other record or future transition.

`TEST-0007` independently checked these rules against the real PR #3 Git history on exact substantive tree `d1d0b32e321cd56ada21f76c4d3e08856a792db5`. It followed `PLANNED → READY → RUNNING → PASS`; PASS was recorded in `a280fed4123a476dc5d5a22651b8b8e1c3aa1240`, and `03b6b85adc9e48b038a609e83c890c16fc313d34` records the result commit in its history.

Because the canonical status contract changed, `TEST-0006` was deliberately reopened from `PASS → READY`; its earlier third PASS remains historical evidence for its tested tree, but the current contract/resume behavior must be rerun before another fresh L2.

No REVIEW-0009 finding is resolved merely because TEST-0007 passed.

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

1. Synchronize WORK-0001 with REVIEW-0009 and TEST-0007 while keeping completion false/IN_REVIEW.
2. Recheck live PR #2 and rerun TEST-0006 from its current `READY` state against the resulting exact PR #3 tree, using `READY → RUNNING → PASS`.
3. Attach TEST-0007 and the new TEST-0006 evidence to REVIEW-0009/F-1 and F-2 without force-closing either thread.
4. Request another fresh-context L2 on the resulting frozen PR #3 HEAD.
5. If that review finds anything material, correct and re-prove it. Only a positive approval-capable L2 with no unresolved blocking issue may allow verified findings and WORK-0001 completion to close.
6. Merge PR #3 only after the approval gate is genuinely satisfied; then update/rebase PR #2, fix its six existing findings, re-prove CI and obtain its own fresh L2.
7. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0009.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
