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

REVIEW-0044 is terminal `COMPLETE / CHANGES_REQUIRED` on `379b4e00aa973f74c9bb973a1e79381f43332f0b`. It added three independent P1s (`PRRT_kwDOUUI5ts6i2qvx`, `PRRT_kwDOUUI5ts6i2qv4`, `PRRT_kwDOUUI5ts6i2qwA`) plus author-side P1 `PRR_kwDOUUI5ts8AAAABNyyfZA`. PR #5 has **49 inline material threads**, all unresolved.

## Current corrective candidate

The successor code candidate is `92d8f69689b6f0d2d15ee13e226590d0e0d543bb`.

It replaces REVIEW-0044's rejected wall-clock/exhaustive-history mutation path with:

- durable machine-managed scheduler cursor in repository issue #7 (`MONDE stale-green scheduler state — machine managed`);
- bounded head processing: at most seven head groups and three reruns per invocation;
- hard request budget of 100 script-issued GitHub calls with explicit target/mutation/post-condition reserves;
- no second global open-PR refresh inside the per-head mutation path; selected PRs are revalidated directly;
- bounded exact-head check candidates as the index to direct canonical run and protected-job validation;
- positive triggering-PR authority from exactly one canonical `refs/pull/<N>/merge` reusable-workflow ref;
- no exhaustive Actions-history reconstruction on the mutation path;
- final current thread-state reclassification immediately before rerun;
- bounded post-rerun observation requiring a new exact-head required check to become non-merge-acceptable/non-completed before invalidation is accepted;
- shared-head continuation: if a first sibling becomes clean and returns green, another still-unresolved sibling is evaluated rather than abandoning the SHA.

Only the trusted scheduled path receives `actions: write` and `issues: write`. The live contract probe remains read-only.

## Exact proof

Bootstrap **#111 / run `35081681865`** on exact candidate `92d8f69689b6f0d2d15ee13e226590d0e0d543bb` is fully green:

- **103/103 tests PASS**;
- core `457 statements / 204 branches` at 100%;
- snapshot adapter `207 / 88` at 100%;
- authority successor `265 / 116` at 100%;
- total **929 statements / 408 branches at 100% line + branch**;
- live PR #2 probe SUCCESS: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`;
- live probe consumed **7/100** script-issued requests under read-only Actions/Checks/Contents/PullRequests permissions.

The prior self-test failures #107-#110 were proof-harness/coverage iterations only; live PR #2 probe remained green throughout. Dead/unreachable guard code was removed rather than artificially covered.

## Review lifecycle

- REVIEW-0031..0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0040..0041: `CLOSED` administrative negative evidence.
- REVIEW-0042..0044: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0045: `OPEN` successor L2 review for the `92d8f696...` corrective contract. It must re-check all 49 unresolved historical inline findings and aggressively red-team cursor durability, bounded check/run/job authority, request-budget forward progress and shared-head post-condition semantics.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **49** PR #5 inline material threads unresolved.
2. Prove this REVIEW-0045 `OPEN` checkpoint exact-head.
3. If green, transition REVIEW-0045 to `IN_PROGRESS` atomically with WORK-0002 / PROJECT_STATE and prove that descendant.
4. Freeze the exact IN_PROGRESS SHA and invoke one fresh-context independent Codex review.
5. Any new material finding requires correction, exact-head re-proof and a successor review.
6. Only a clean independent successor review permits controlled historical-thread verification/resolution; no merge before then.
7. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0044.yaml
9. registry/reviews/REVIEW-0045.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/49 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
