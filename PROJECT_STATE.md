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

## Current corrective contract

Runtime candidate `92d8f69689b6f0d2d15ee13e226590d0e0d543bb` replaces REVIEW-0044's rejected wall-clock/exhaustive-history mutation path with durable issue #7 cursor state, bounded direct check->run->protected-job PR authority, explicit request reserves and shared-head post-condition continuation.

Only the trusted scheduled path receives `actions: write` and `issues: write`; the live contract probe remains read-only.

## Exact proof chain

- Runtime candidate `92d8f69689b6f0d2d15ee13e226590d0e0d543bb` — Bootstrap #111 / `35081681865`: **103/103 tests, 929 statements / 408 branches, 100% line+branch**, live PR #2 probe SUCCESS at **7/100** requests.
- REVIEW-0045 OPEN checkpoint `3ebc471f510ee30685bf9272b22f0fe7d39f86e0` — Bootstrap #112: live probe SUCCESS, self-test correctly rejected the TEST-0009 wildcard traceability regression.
- Corrected REVIEW-0045 OPEN checkpoint `2bd5354dac39914f358bff9e6e71e9847dffb182` — Bootstrap #113 / `35083230784`: self-test SUCCESS and live PR #2 probe SUCCESS. TEST-0009 again explicitly names all regression modules.

## Review lifecycle

- REVIEW-0031..0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0040..0041: `CLOSED` administrative negative evidence.
- REVIEW-0042..0044: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0045: **`IN_PROGRESS`** successor L2. The next checkpoint is state-only above the proven OPEN head; once that descendant passes its own exact-head proof it must be frozen for a single fresh-context independent review.

REVIEW-0045 must re-check all **49 unresolved historical inline findings** and red-team issue-backed cursor durability/concurrency, bounded check/run/job target authority, request-budget forward progress and shared-head post-condition semantics.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **49** PR #5 inline material threads unresolved.
2. Prove the REVIEW-0045 `IN_PROGRESS` checkpoint exact-head.
3. If green, freeze that SHA and invoke exactly one fresh-context independent Codex review on it.
4. Do not mutate the Git tree while REVIEW-0045 runs.
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
