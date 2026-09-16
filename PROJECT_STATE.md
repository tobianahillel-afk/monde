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

REVIEW-0046 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `e9c22ab562f724ba77e21f32cf8195b0b1ed5b5b` via independent review `PRR_kwDOUUI5ts8AAAABNz-eNg`. It added five material findings to the prior 55.

REVIEW-0047 is now terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD **`d266d73c15b524413209be16d4970ec42928ea04`** via independent review **`PRR_kwDOUUI5ts8AAAABN1lrxA`**. It added three P1 findings, bringing PR #5 to **63 inline material threads**, all intentionally unresolved.

## REVIEW-0047 proof and findings

The REVIEW-0047 corrective runtime first reached a fully proven checkpoint at `efac4c61aa7dd61b17088e5f8a5b1fae82199d3c` with Bootstrap #127 / run `35102314409`: **116/116 tests**, **1,153 statements / 522 branches**, **100% line + branch**, and a successful live read-only PR #2 contract probe at **7/100** requests.

The synchronized `OPEN` checkpoint `f2f94a25acef881d0928e2ef80d073dcd9540c41` passed Bootstrap #128 / run `35103307534` with the same proof. The frozen `IN_PROGRESS` checkpoint `d266d73c15b524413209be16d4970ec42928ea04` then passed Bootstrap **#129 / run `35103667502`** with self-test SUCCESS and live PR #2 probe SUCCESS.

The fresh exact-head L2 nevertheless found three new P1 interleavings:

1. **`PRRT_kwDOUUI5ts6i9Tl3` — retain a rerun that is already stale again.** A rerun can evaluate while the PR is clean, finish merge-acceptable, then see a newly reopened/unresolved thread before the final GraphQL read. Raising and advancing the cursor leaves that green check usable. The selected head/PR must remain selected or be retried instead.
2. **`PRRT_kwDOUUI5ts6i9Tl_` — bind the POST to one specific workflow attempt.** Another actor can rerun the same workflow between target discovery and this poll's POST. Accepting any `run_attempt > previous_attempt` can attribute the wrong completed attempt to this invocation while its own newer attempt is still queued. The mutation baseline and exact created attempt must be positively identified.
3. **`PRRT_kwDOUUI5ts6i9TmE` — detect drift between pages in one invocation.** Offset check-history pagination can change after page 1 and before page 2, causing the only PR-bound target to shift into an already-read page. Cross-invocation anchors alone do not prove same-invocation completeness.

Author-side adversarial inspection additionally requires the successor to prove that a rerun still pending after the bounded local waiter is resumed by exact run/attempt identity **without issuing another rerun POST** on the next scheduler invocation.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Correct the three REVIEW-0047 P1 classes and the pending-rerun duplicate-POST interleaving without broadening T12.
3. Add regressions for stale-again retention, exact POST-attempt attribution under concurrent reruns, intra-invocation page drift, and pending observation resumed without a second POST.
4. Re-run the bootstrap self-test at 100% line + branch coverage and the live read-only PR #2 contract probe.
5. Synchronize TEST-0009 / WORK-0002 / PROJECT_STATE and open a successor REVIEW-0048 only after the corrected runtime is exact-head proven.
6. Freeze the synchronized REVIEW-0048 head and invoke exactly one fresh-context independent L2.
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
9. issue #7 scheduler state
10. live PR #5 exact HEAD/checks/reviews/63 threads
11. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
