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

REVIEW-0048 reached exact frozen HEAD **`b5932be9a5f2d36c192bf482a3051a8523b97a34`**, proven by Bootstrap **#137 / run `35130503995` SUCCESS**. Its runtime predecessor **`86670f6b9f6ae2c1e288686866986fd737421892`** passed Bootstrap #135 with **138/138 tests**, **1,342 statements / 640 branches**, **100% line + branch**, and live read-only PR #2 probe **SUCCESS at 7/100** requests.

The REVIEW-0048 Codex invocation comment `5702006501` was refused by platform code-review quota, so **no independent L2 exists for REVIEW-0048**. During the frozen period, author-side review `PRR_kwDOUUI5ts8AAAABN4OKew` found a material P1: scheduler V3 persists only cursor/scan state and does not durably bind an already-issued rerun POST to a pending `run_id / baseline-or-expected-attempt / prior-check / selected-PR authority`. Under delayed Actions/Checks visibility, the next schedule can still see the previous completed attempt and issue a duplicate rerun.

Accordingly REVIEW-0048 is **`CLOSED / CHANGES_REQUIRED` administrative negative evidence**, not `COMPLETE`. The 63 inline material threads remain unresolved.

## Required REVIEW-0049 correction

The next successor must preserve every prior protection and add a positively authorized durable mutation-observation state:

1. an accepted rerun POST must become durable state that can be resumed without another POST even if GitHub has not yet published the next attempt/check;
2. durable pending state must bind the selected PR's current authority, `run_id`, mutation baseline/expected next attempt, and prior effective-check identity strongly enough to reject unrelated activity;
3. restart/crash ordering around state persistence and POST must be explicitly designed and tested—no gap may permit `POST succeeded but durable state says no mutation in flight`;
4. pending state may clear/advance only after terminal causally-bound post-condition evidence or an explicit fail-closed authority-change path;
5. existing target-history drift detection, stale-again retention, exact integer typing, issue #7 serialization, seven-head bound, three-POST cap, 100-request reserves and fail-closed metadata remain required.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Prove this REVIEW-0048 terminal state-only checkpoint exact-head before functional correction.
3. Implement durable pending-mutation identity and crash/retry ordering as a narrow REVIEW-0049 successor.
4. Add adversarial regressions for delayed API visibility across scheduled invocations and crash boundaries around POST/state persistence.
5. Exact-head prove 100% line+branch and live read-only PR #2 contract probing.
6. Only then create REVIEW-0049 `OPEN`, prove it, transition to `IN_PROGRESS`, prove/freeze, and request one fresh independent L2 when the review surface is available.
7. Do not merge or resolve historical threads before a clean successor review.
8. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0047.yaml
9. registry/reviews/REVIEW-0048.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/63 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
