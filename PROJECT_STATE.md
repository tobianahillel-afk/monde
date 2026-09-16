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

REVIEW-0046 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `e9c22ab562f724ba77e21f32cf8195b0b1ed5b5b` via independent review `PRR_kwDOUUI5ts8AAAABNz-eNg`. It added five material findings (four P1, one P2), bringing PR #5 to **60 inline material threads**, all intentionally unresolved.

## REVIEW-0047 corrective runtime

The first fully proven REVIEW-0047 runtime checkpoint is exact SHA **`efac4c61aa7dd61b17088e5f8a5b1fae82199d3c`**.

It corrects the five REVIEW-0046 finding classes without broadening the bootstrap scope:

1. delayed reruns remain durably selected across scheduled invocations instead of being forgotten after the local observation window;
2. terminal invalidation is causally bound to the exact rerun `run_id`, new `run_attempt`, protected job identity and effective required check;
3. the complete current PR head/base/merge-ref authority fingerprint is revalidated immediately before mutation and before accepting the post-condition;
4. selected-PR target-history continuation persists a page-membership anchor and restarts safely when retained history drifts;
5. scheduler issue identity requires an exact positive non-Boolean integer, consistent with the other trust-binding identifier boundaries.

The prior protections remain in force: serialized issue #7 writers, global three-POST cap, at most seven head groups per invocation, 100 script-issued GitHub requests with explicit reserves, fail-closed malformed metadata, and a read-only live PR #2 contract probe.

## Exact REVIEW-0047 proof chain

Bootstrap **#127 / run `35102314409`** on exact runtime SHA `efac4c61aa7dd61b17088e5f8a5b1fae82199d3c` is fully green:

- **116/116 tests PASS**;
- core: 457 statements / 204 branches, 100%;
- authority: 489 statements / 230 branches, 100%;
- snapshot: 207 statements / 88 branches, 100%;
- total: **1,153 statements / 522 branches, 100% line + branch**;
- live PR #2 GitHub contract probe SUCCESS: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`;
- live probe consumed **7/100** script-issued requests under read-only Actions/Checks/Contents/PullRequests permissions.

Two intermediate proof attempts were intentionally not accepted: Bootstrap #125 exposed an old shared-head test harness that mocked only one PR-authority read, and Bootstrap #126 passed all 115 functional tests but exposed five uncovered successor guard paths. Both gaps were corrected before #127; the coverage threshold was never lowered.

The synchronized REVIEW-0047 `OPEN` checkpoint **`f2f94a25acef881d0928e2ef80d073dcd9540c41`** then passed Bootstrap **#128 / run `35103307534`** with the same **116 tests / 1,153 statements / 522 branches / 100%** proof and live PR #2 probe SUCCESS at **7/100** requests.

## REVIEW-0047 lifecycle

REVIEW-0047 is now `IN_PROGRESS`. No independent L2 result has been accepted yet. This synchronized `IN_PROGRESS` checkpoint must itself pass the exact-head bootstrap self-test and live PR #2 probe; after that proof its SHA is frozen for exactly one fresh-context independent L2/Codex review.

The successor review must re-check all **60 unresolved material threads** and red-team at minimum:

- rerun persistence across scheduler invocations and delayed completion beyond one local observation loop;
- exact `run_id` / `run_attempt` / protected-job / effective-check causal binding under unrelated shared-head completions;
- PR authority races immediately before POST and immediately before post-condition acceptance;
- anchored target-history continuation under deletion, insertion, reordering and `total_count` drift;
- V1/V2-to-V3 issue #7 migration, exact integer typing and crash/retry behavior;
- global three-POST and 100-request reserve enforcement under long histories and large sibling sets;
- least privilege, regression discovery and TEST-0009 / WORK-0002 / PROJECT_STATE / REVIEW-0046 / REVIEW-0047 traceability;
- every historical finding: no assumption that tests or 100% coverage alone prove semantic closure.

No historical thread is resolved merely because the runtime proof is green.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **60** PR #5 inline material threads unresolved.
2. Prove this exact synchronized REVIEW-0047 `IN_PROGRESS` checkpoint with Bootstrap self-test + live read-only PR #2 contract probe.
3. Freeze the exact proven SHA and re-confirm 60/60 threads remain unresolved and no fresh exact-head review already exists.
4. Invoke exactly one fresh-context independent L2/Codex review on that frozen SHA.
5. During REVIEW-0047, do not mutate the Git tree, merge, or resolve historical threads.
6. Any new material finding requires correction, exact-head re-proof and another successor review.
7. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0046.yaml
9. registry/reviews/REVIEW-0047.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/60 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
