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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, last rechecked live at HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`, lifecycle `IN_REVIEW`.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is `REVIEW-0003` through `REVIEW-0014`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key current facts:

- `REVIEW-0007` invalidated the first TEST-0006 PASS because PROJECT_STATE, WORK-0002 and the progress matrix disagreed on the global WORK-0002 lifecycle.
- `REVIEW-0008` invalidated the second TEST-0006 PASS because the PR #3 WORK-0002 mirror referenced two branch-only `read_before` files that were absent from the tested tree.
- `REVIEW-0009`, on `1e3f539b89afbbb07de63271682a1db06f47550c`, found missing reviewed `DONE → IN_REVIEW` reopening semantics and TEST-0004's immutable historical `PLANNED → PASS` edge.
- `REVIEW-0010`, on `14c3d3fcc6dd96af9d2e5acd9f02d2d957c03425`, found missing forward REQ-0006 → TEST-0007 traceability.
- `REVIEW-0011`, on `c8fbfa51ac04b566f337ee606a806e42881b67f2`, found stale PROJECT_STATE next-action ordering.
- `REVIEW-0012`, on `a2a86b96bb3fe39229b9834cd4ab17ee16d8121f`, found WORK-0001 had not yet preserved REVIEW-0011/current gate.
- `REVIEW-0013`, on `9f9bcaa0b91b975296b169cf2511edc297a83e1f`, found WORK-0001.required_tests.e2e omitted current lifecycle proof TEST-0007.
- `REVIEW-0014`, on `c9b75f677f5b79f66189f90a730cb8efbeb8af0c`, found two P1/R2 accumulated-history defects: REVIEW-0004..REVIEW-0013 were first materialized directly `COMPLETE` after the review lifecycle existed, and REQ-0015..REQ-0019 were first materialized directly `ACCEPTED` after the requirement lifecycle existed.

## Current correction and proof

`registry/status-machines.yaml` version 6:

- preserves generic review lifecycle `OPEN → IN_PROGRESS → COMPLETE`; no generic `OPEN → COMPLETE` shortcut exists;
- preserves requirement initial state `PROPOSED` and generic `PROPOSED → ACCEPTED`; `ACCEPTED` is not an alternate initial state;
- adds exact historical import exceptions only for REVIEW-0004..REVIEW-0013, each bound to its real introduction commit, `historical_only: true`, `future_reuse_forbidden: true`, and `REVIEW-0014/F-1`;
- adds exact historical import exceptions only for REQ-0015..REQ-0019 at commit `2712795dc9f10c1efed2088313d125f6f915cc98`, each `historical_only: true`, `future_reuse_forbidden: true`, and bound to `REVIEW-0014/F-2`;
- continues to permit progress `DONE → IN_REVIEW` only as a reviewed reopening after new adverse evidence;
- keeps generic TEST execution strict as `PLANNED → READY → RUNNING → PASS`;
- retains the single exact historical TEST-0004 `PLANNED → PASS` migration exception, record/commit bound and non-reusable.

REVIEW-0014 itself demonstrates the normal review path in immutable Git history: `OPEN` at `ec69110468c7e1cd79984dedb835504de8c0b561` → `IN_PROGRESS` at `2926a070de8371e7ad3aaebeca0d9e424700d43f` → `COMPLETE/CHANGES_REQUIRED` at `b03880759f7dde54b6f59f3ecaf4f2d5889e1eb7`. It is not covered by a historical import exception.

TEST-0007's third execution is **PASS** on exact lifecycle-v6 tree `b03880759f7dde54b6f59f3ecaf4f2d5889e1eb7`; result commit `42a36e1b37855ea107eb94a8f3c9a05fe9cd6c67`; history pointer `ffffb37d680e477fa03f74523dfac624ad74427c`. It verifies exact review/requirement import boundaries, future-reuse prohibition, REVIEW-0014's normal lifecycle, the prior TEST-0004 migration boundary, progress reopening, and REQ-0006 ↔ TEST-0007 traceability.

TEST-0006 was then rerun on exact tree `ffffb37d680e477fa03f74523dfac624ad74427c` and correctly **FAILED**: the v6 contract was present, but PROJECT_STATE and WORK-0001 still described v5/REVIEW-0013, so a cold-resuming agent could not discover the current gate. The FAIL result is `45088fc916b84c7e809d1305fe926724e85b797c`; history pointer `337324fe083fab0ec6a88c0672d7cd86aadf69af`.

This PROJECT_STATE update is paired atomically with the corresponding WORK-0001 synchronization. That fixes the stale-handover cause of the TEST-0006 failure without erasing the negative execution. TEST-0006 must now be reopened and rerun against the resulting synchronized tree before another fresh L2 is requested.

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

Historical import exceptions preserve immutable post-contract materialization only when exact record/status/commit tuples are explicitly reviewed. They never create alternate initial states, generic transitions, or reusable future shortcuts.

## Next action

1. Reopen TEST-0006 from `FAIL → READY`, then execute it `READY → RUNNING` against the exact synchronized WORK-0001/PROJECT_STATE tree.
2. Recheck the complete cold-resume path, all current-tree WORK-0002 `read_before` paths, live PR #2 state, status-machine v6 import isolation, positive-only review approval semantics and TEST-0001 replacement coverage. Record PASS only if every assertion is true.
3. Reply to REVIEW-0014/F-1 and F-2 with the exact v6 + TEST-0007 + rerun TEST-0006 evidence; do not resolve the threads before independent verification.
4. Synchronize final TEST-0006 evidence into WORK-0001/PROJECT_STATE, freeze the resulting PR #3 HEAD and request another fresh-context L2 explicitly against that SHA.
5. If that review reports no material defect, record approval-capable L2 evidence, then resolve only findings independently verified as corrected and finalize WORK-0001/progress/completion. Otherwise correct and re-prove the exact defect.
6. Merge PR #3 only after WORK-0001's A3 assurance gate genuinely passes.
7. After PR #3 merge, rebase/update PR #2 on the new main contract, correct/re-prove its outstanding fresh-L2 work and obtain its own fresh L2 before merge.
8. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0014.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
