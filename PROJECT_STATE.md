# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- PHASE-0 / LOT-0 remain `IN_PROGRESS`.
- WORK-0001 is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- WORK-0002 remains `IN_REVIEW / A3`; WORK-0003 and WORK-0004 remain blocked.

## PR #5 / T12 trusted predecessor

PR #5 (`chore/work-0002-stale-green-bootstrap`) remains the narrow trusted-default-branch predecessor for WORK-0002/T12. No merge and no historical review-thread resolution is permitted while material findings remain open or a successor review is incomplete.

REVIEW-0047 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `d266d73c15b524413209be16d4970ec42928ea04` via independent review `PRR_kwDOUUI5ts8AAAABN1lrxA`. It added three P1 findings, bringing PR #5 to **63 inline material threads**, all intentionally unresolved.

REVIEW-0048 is `CLOSED / CHANGES_REQUIRED` administrative negative evidence on frozen HEAD `b5932be9a5f2d36c192bf482a3051a8523b97a34`. Bootstrap #137 / run `35130503995` was green, but Codex invocation comment `5702006501` was refused by platform code-review quota, so no independent L2 exists. Author-side `PRR_kwDOUUI5ts8AAAABN4OKew` found the missing durable identity of an already-issued rerun across DeferredObservation.

## REVIEW-0049 — terminal negative evidence

The V4 successor added write-ahead pending mutation state in issue #7. Before any rerun POST it durably records selected PR authority digest, exact `run_id`, mutation baseline attempt and prior effective-check id. While pending state exists, later schedules are observation-only and cannot automatically issue another rerun POST.

Its exact technical candidate **`7d7f52fe5beb6bf7466a523b0fb0ea75108ff9a5`** passed Bootstrap **#145 / run `35133808117` SUCCESS** with **167/167 tests**, **1,613 statements / 754 branches**, **100% line + branch**, and live read-only PR #2 contract probe SUCCESS. REVIEW-0049 `OPEN` checkpoint `32128d507ed2ee3bbebf90ce51d08515dbf2e9e1` passed #146; frozen `IN_PROGRESS` head **`c8f1fec24358c25224771a15b647d56c8a2f0287`** passed Bootstrap **#147 / `35134919307` SUCCESS**.

REVIEW-0049 is nevertheless now **`CLOSED / CHANGES_REQUIRED`**. The fresh Codex trigger comment `5702590288` produced no exact-head review before author-side adversarial review **`PRR_kwDOUUI5ts8AAAABN4rPMg`** invalidated the frozen head.

The P1 is lifecycle/authority-critical: when the selected pending PR reports `closed`, V4 clears pending state immediately, before fetching/observing the exact already-issued rerun. A closed PR does not cancel its workflow mutation. If PR A and PR B share one head, A's pending rerun has already been POSTed, A closes, B remains unresolved, and A's rerun later completes merge-acceptable, that head-scoped green check can make B stale-green after V4 has forgotten the mutation.

Therefore PR closure is **not** terminal authorization to delete pending mutation identity. A successor must preserve reversible pending head/run/attempt/check authority after original-PR closure, observe the exact external mutation to a causally-bound terminal result, and if that result is merge-acceptable reclassify/retain current open same-head PRs before clearing pending state. If the external post-condition cannot be proven, behavior must remain fail-closed.

All **63** historical inline material threads remain unresolved. No merge is permitted.

## REVIEW-0050 next corrective direction

REVIEW-0050 should be a new successor rather than rewriting REVIEW-0049. The minimum safe design should:

- persist an exact `pending_head` (or an equally reversible exact head binding), not only a non-reversible PR-authority digest;
- keep pending mutation identity after the originating PR closes;
- observe `pending_run_id` against `pending_baseline_attempt + 1` and the prior effective-check identity without requiring the original PR to remain open;
- preserve protected-job and effective-check causal binding;
- on terminal non-merge-acceptable outcome, clear safely;
- on terminal merge-acceptable outcome, snapshot/reclassify current open PRs sharing `pending_head`, and retain/invalidate any unresolved sibling before scheduler progress advances;
- preserve the no-duplicate-POST invariant across delayed visibility/restart;
- keep the separate pre-POST write-ahead liveness ambiguity explicit rather than solving it with unsafe replay;
- add adversarial regressions for `POST -> origin PR closes -> sibling unresolved -> rerun later green`, delayed visibility and restart boundaries;
- restore 100% line+branch proof and live read-only PR #2 contract probe before opening REVIEW-0050 lifecycle.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Publish a state-only REVIEW-0049 `CLOSED / CHANGES_REQUIRED` checkpoint and exact-head prove it.
3. Build REVIEW-0050 as a new adapter/successor; do not rewrite REVIEW-0049 history.
4. Preserve pending mutation across origin-PR closure and carry exact reversible pending head authority.
5. Account for the exact issued run/attempt/job/effective-check result before any pending clear.
6. Reclassify current open same-head siblings after a terminal merge-acceptable closed-origin rerun.
7. Add delayed-visibility/restart/shared-head adversarial regressions and preserve the three-POST/seven-head/100-request bounds.
8. Reach exact-head 100% line+branch plus live PR #2 probe before creating REVIEW-0050 `OPEN`.
9. Then use the normal `OPEN -> proof -> IN_PROGRESS -> proof -> freeze -> fresh L2` lifecycle.
10. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0048.yaml
9. registry/reviews/REVIEW-0049.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/63 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
