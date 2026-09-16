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

REVIEW-0048 is now `OPEN`. Its corrective runtime is exact-head proven at **`86670f6b9f6ae2c1e288686866986fd737421892`** by Bootstrap **#135 / run `35126374186`**: **138/138 tests**, **1,342 statements / 640 branches**, **100% line + branch**, and a successful live read-only PR #2 contract probe at **7/100** script-issued requests.

## REVIEW-0048 corrective contract

The successor preserves prior protections and specifically addresses REVIEW-0047's three P1 classes plus the pending-observation interleaving:

1. **Stale-again retention.** A completed merge-acceptable rerun followed by a current unresolved-thread observation does not let the scheduler treat the head as safely completed; the selected PR/head remains retained for further processing.
2. **Exact single-attempt attribution.** The mutation path refreshes its workflow attempt baseline and rejects ambiguous attempt jumps rather than attributing another actor's rerun to this invocation.
3. **Intra-invocation pagination drift detection.** Consecutive offset pages are boundary-checked; a membership shift restarts the target scan rather than declaring incomplete history complete.
4. **Bounded deferred observation.** A post-condition that cannot yet be established returns durable continuation rather than accepting an unproven state or silently advancing the head.
5. **All prior authority and resource guards remain active.** Current head/base/merge authority, exact integer IDs, serialized issue #7 writer, three-POST cap, seven-head bound, 100-request cap/reserves, fail-closed metadata and live read-only probe remain required.

The #135 live probe confirms the installed REVIEW-0048 adapter works against real PR #2 GitHub APIs; it is wiring/contract evidence, not an independent semantic approval.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Prove this synchronized REVIEW-0048 `OPEN` checkpoint exact-head with the bootstrap self-test and live PR #2 probe.
3. If green, transition REVIEW-0048 `OPEN -> IN_PROGRESS` with WORK-0002 and PROJECT_STATE synchronized in one state-only checkpoint.
4. Prove that exact `IN_PROGRESS` descendant, freeze its SHA, and re-query all 63 threads/reviews.
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
