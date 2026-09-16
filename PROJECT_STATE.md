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

## REVIEW-0049 technical candidate and OPEN lifecycle

The V4 successor addresses that predecessor by using write-ahead pending mutation state in issue #7. Before any rerun POST it durably records the selected PR authority digest, exact `run_id`, mutation baseline attempt and prior effective-check id. While pending state exists, a later schedule resumes observation and does **not** issue another rerun POST. Ambiguous POST outcomes retain pending state and fail closed instead of automatically replaying the mutation.

Exact technical candidate **`7d7f52fe5beb6bf7466a523b0fb0ea75108ff9a5`** passed MONDE Stale-Green Bootstrap **#145 / run `35133808117` SUCCESS**:

- **167/167 tests PASS**;
- **1,613 statements / 754 branches** across core, PR snapshot, authority, REVIEW-0048 and REVIEW-0049 adapters;
- **100% line + branch coverage** with zero missing statements/branches;
- live read-only GitHub contract probe against PR #2 **SUCCESS**.

Regression development also exposed and corrected a V4 trust-boundary defect before review lifecycle opening: coercive pending PR-number equality (`True == 1`) and malformed PR state acceptance are now rejected with exact positive non-Boolean integer and closed-world `open|closed` validation.

REVIEW-0049 is now **`OPEN`**. No reviewer, reviewed commit, independent outcome, or finding closure is claimed at this stage. Technical green proof is evidence only, not semantic approval. All **63** historical inline material threads remain unresolved.

A key REVIEW-0049 red-team target is the deliberate safety/liveness tradeoff at the write-ahead boundary: if issue #7 pending state is durably acknowledged and the process dies before the rerun POST actually occurs, the bridge cannot safely prove that absence and therefore must not automatically replay. The candidate favors no duplicate mutation over autonomous liveness; independent review must assess the safe recovery/escalation contract.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **63** PR #5 inline material threads unresolved.
2. Exact-head prove the REVIEW-0049 `OPEN` state-only checkpoint; runtime must remain equivalent to the proven `7d7f52fe…` candidate.
3. If green, transition REVIEW-0049 to `IN_PROGRESS` in a second state-only checkpoint and re-prove that exact SHA.
4. Freeze the resulting `IN_PROGRESS` SHA and re-check live PR #5 HEAD, reviews and thread count.
5. Update the PR description to the frozen REVIEW-0049 proof chain.
6. Request exactly one fresh independent L2 only when the external review surface accepts it; quota refusal is an administrative blocker, not review evidence.
7. During independent review, do not mutate the Git tree and do not resolve historical threads.
8. Any material finding requires correction, exact-head re-proof and another successor review.
9. Only a clean exact-head independent successor review permits controlled verification/resolution and a guarded PR #5 merge decision.
10. WORK-0003 and WORK-0004 remain blocked.

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
10. registry/reviews/REVIEW-0049.yaml
11. issue #7 scheduler state
12. live PR #5 exact HEAD/checks/reviews/63 threads
13. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
