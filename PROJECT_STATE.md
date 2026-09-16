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

The REVIEW-0048 corrective runtime is exact-head proven at **`86670f6b9f6ae2c1e288686866986fd737421892`** by Bootstrap **#135 / run `35126374186`**: **138/138 tests**, **1,342 statements / 640 branches**, **100% line + branch**, and live read-only PR #2 contract probe **SUCCESS at 7/100** requests.

The synchronized REVIEW-0048 `OPEN` checkpoint **`fd81f349384de1b488edb957645d39908904bf84`** passed Bootstrap **#136 / run `35130228101`** with self-test SUCCESS and live PR #2 probe SUCCESS. REVIEW-0048 is now **`IN_PROGRESS`**; this state-only descendant is the next exact head that must be proven and frozen for the fresh independent L2.

## REVIEW-0048 review mandate

The successor preserves prior protections and must independently re-check all 63 historical findings, with particular red-team focus on:

1. exact POST -> single next workflow attempt -> protected job -> effective required-check causality under concurrent reruns and Actions visibility lag;
2. stale-again retention when a rerun completes merge-acceptable but thread state is unresolved again before/after final observation;
3. selected-PR target-history continuation under insertion, deletion, reordering and drift between consecutive pages in the same invocation;
4. bounded DeferredObservation across scheduler restart/retry without duplicate POST or unsafe cursor advancement;
5. head/base/merge-ref authority at discovery, mutation and post-condition boundaries;
6. issue #7 serialization/migration, exact integer identifiers, three-POST cap, seven-head bound and 100-request reserves;
7. synchronized TEST-0009 / WORK-0002 / PROJECT_STATE / REVIEW-0047 / REVIEW-0048 traceability.

Any new material finding requires correction, exact-head re-proof and another successor review. No historical thread may be resolved while REVIEW-0048 is in progress.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Prove this REVIEW-0048 `IN_PROGRESS` state-only descendant exact-head with the bootstrap self-test and live PR #2 probe.
3. If green, freeze that exact SHA and re-query PR #5 HEAD, all 63 threads and the review list.
4. Update only PR metadata needed for reviewer orientation; do not modify the Git tree after the freeze.
5. Invoke exactly one fresh-context independent L2 on the frozen SHA.
6. Any new material finding requires correction, exact-head re-proof and another successor review.
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
