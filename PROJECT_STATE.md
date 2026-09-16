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

REVIEW-0045 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `adbc68fb47af26b78edd6a1bd02893c000c3c639` via independent review `PRR_kwDOUUI5ts8AAAABNzc8Sw`. Its six P1 findings remain material negative evidence. PR #5 has **55 inline material threads**, all intentionally unresolved.

## REVIEW-0046 corrective runtime

The REVIEW-0046 runtime candidate is exact SHA **`2ee7c8d9e27d7f402a9619e4da8ea76200ae7f9d`**.

It corrects the six REVIEW-0045 P1 classes without broadening the bootstrap scope:

1. rerun invalidation follows the exact rerun `run_id`, requires a new terminal `run_attempt`, validates the protected `MONDE / Merge Gate` job, then validates the effective exact-head required check before accepting invalidation;
2. selected-PR target discovery scans bounded 12-check pages, at most two pages per invocation, and persists `scan_pr + scan_page` in issue #7 so targets behind newer shared-head checks are not permanently abandoned;
3. direct current-PR authority binds head identity, base repository/ref/SHA, `merge_commit_sha`, canonical `refs/pull/<N>/merge`, and the referenced reusable-workflow SHA;
4. trust-binding app/run/workflow/job/run-attempt identifiers require exact positive non-Boolean integers;
5. every actual rerun POST counts against one invocation-wide maximum of three, including shared-head sibling fallthrough;
6. the trusted scheduled poll uses a dedicated GitHub Actions `concurrency` group with `cancel-in-progress: false`, serializing issue #7 cursor writers.

The mutation path remains capped at 100 script-issued GitHub requests with explicit mutation/post-condition/state-write reserves. The live probe remains read-only; only the trusted schedule receives `actions: write` and `issues: write`.

## Exact REVIEW-0046 runtime proof

Bootstrap **#122 / run `35087404773`** on exact SHA `2ee7c8d9e27d7f402a9619e4da8ea76200ae7f9d` is fully green:

- **110/110 tests PASS**;
- core: 457 statements / 204 branches, 100%;
- authority: 423 statements / 196 branches, 100%;
- snapshot: 207 statements / 88 branches, 100%;
- total: **1,087 statements / 488 branches, 100% line + branch**;
- live PR #2 GitHub contract probe SUCCESS: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`;
- live probe consumed **7/100** script-issued requests under read-only Actions/Checks/Contents/PullRequests permissions.

Intermediate REVIEW-0046 heads deliberately exposed test-harness and uncovered-path gaps while the live contract remained green; those gaps were corrected before this proof. Dead/unreachable duplicate guard code was removed rather than artificially covered.

## REVIEW-0046 lifecycle

REVIEW-0046 is now being materialized as `OPEN`. Its fresh independent L2 has **not** started. The OPEN checkpoint must itself pass exact-head self-test and live contract proof before any `IN_PROGRESS` transition.

The fresh review must actively re-check all **55 unresolved material threads** and red-team at minimum:

- exact rerun attempt -> protected job -> effective exact-head terminal-check causality;
- selected-PR check-page continuation, total-count/page drift, retained-target starvation and issue #7 continuation integrity;
- current head/base/merge-ref authority and retarget races;
- exact numeric typing on every trust boundary;
- actual global three-POST enforcement across shared-head siblings;
- GitHub Actions concurrency semantics for delayed, duplicate and manually rerun schedule executions;
- V1 -> V2 scheduler-state migration, crash/retry behavior and durable progress;
- 100-call budget reserves under long check histories and shared-head sibling sets;
- least privilege, historical regression coverage and TEST/WORK/PROJECT/REVIEW traceability.

No historical thread is resolved merely because the runtime proof is green.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **55** PR #5 inline material threads unresolved.
2. Commit TEST-0009 / WORK-0002 / PROJECT_STATE / REVIEW-0046 `OPEN` atomically above the proven `2ee7c8d9...` runtime.
3. Prove that exact OPEN checkpoint with Bootstrap self-test + live read-only PR #2 contract probe.
4. If green, transition REVIEW-0046 to `IN_PROGRESS` in one synchronized state-only checkpoint and prove that descendant exact-head.
5. Freeze the exact `IN_PROGRESS` SHA and re-confirm 55/55 threads remain unresolved and no fresh exact-head review already exists.
6. Invoke exactly one fresh-context independent L2/Codex review on that frozen SHA.
7. During REVIEW-0046, do not mutate the Git tree, merge, or resolve historical threads.
8. Any new material finding requires correction, exact-head re-proof and another successor review.
9. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0045.yaml
9. registry/reviews/REVIEW-0046.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/55 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
