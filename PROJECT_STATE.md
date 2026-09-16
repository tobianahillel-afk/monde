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

REVIEW-0045 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `adbc68fb47af26b78edd6a1bd02893c000c3c639` via independent review `PRR_kwDOUUI5ts8AAAABNzc8Sw` submitted at `2026-09-16T10:14:02Z`.

It added **six** independent P1 findings:

- `PRRT_kwDOUUI5ts6i4YR8` — non-terminal queued/in-progress successor checks were accepted too early as durable invalidation;
- `PRRT_kwDOUUI5ts6i4YSC` — fixed twelve-check truncation can permanently omit the unresolved PR's only positively bound rerun target;
- `PRRT_kwDOUUI5ts6i4YSI` — direct PR revalidation omitted base repository/ref/SHA identity, allowing retarget drift;
- `PRRT_kwDOUUI5ts6i4YSM` — the declared three-rerun cap was not enforced inside a shared-head sibling loop;
- `PRRT_kwDOUUI5ts6i4YST` — direct run/job authority reintroduced coercive numeric equality for trust-binding identifiers;
- `PRRT_kwDOUUI5ts6i4YSZ` — overlapping schedules can race issue #7 cursor PATCHes and regress durable progress.

PR #5 therefore has **55 inline material threads**, all intentionally unresolved.

## Rejected REVIEW-0045 candidate and proof

The reviewed runtime family introduced durable issue #7 scheduler state, bounded direct check->run->protected-job PR authority, explicit request reserves and shared-head fallthrough. Its exact proof chain remained technically green:

- runtime candidate `92d8f69689b6f0d2d15ee13e226590d0e0d543bb` — Bootstrap #111 / `35081681865`: **103/103 tests, 929 statements / 408 branches, 100% line+branch**, live PR #2 probe SUCCESS at **7/100** requests;
- corrected REVIEW-0045 OPEN checkpoint `2bd5354dac39914f358bff9e6e71e9847dffb182` — Bootstrap #113 / `35083230784`: self-test SUCCESS + live probe SUCCESS;
- exact REVIEW-0045 IN_PROGRESS head `adbc68fb47af26b78edd6a1bd02893c000c3c639` — Bootstrap #114 / `35083395796`: self-test SUCCESS + live probe SUCCESS;
- terminal REVIEW-0045 negative checkpoint `24eca777e018f3a9555dede8bdf79f9191ae7c1c` — Bootstrap #115 / `35084261652`: self-test SUCCESS + live probe SUCCESS, but its first registry write accidentally omitted one of the six new PRRT IDs; the immediate successor state-only correction fixes that traceability error before runtime work resumes.

Green CI is explicitly not sufficient evidence of semantic closure; REVIEW-0045 disproved six assumptions that the tests did not cover.

## Required successor correction

A REVIEW-0046 candidate must at minimum:

1. observe a **terminal** new required-check conclusion after rerun and accept invalidation only when that terminal state is non-merge-acceptable;
2. replace fixed twelve-check truncation with a bounded continuation/completeness strategy that can positively find the selected PR's retained target without falling back to exhaustive history;
3. bind direct current-PR authority to base repository/ref/SHA and current merge-ref context so a retarget cannot reuse old-base workflow execution;
4. enforce the invocation-wide rerun limit at the actual mutation point, including same-head sibling fallthrough;
5. require exact positive non-Boolean integer typing for every direct run/workflow/job identifier and attempt;
6. serialize scheduled cursor writers (or use versioned CAS/lease semantics) so issue #7 progress cannot regress under overlapping schedule/re-run executions;
7. add adversarial regressions for all six P1s, preserve 100% meaningful line/branch coverage, and retain a real read-only PR #2 contract probe.

All prior 49 findings remain unresolved; none may be silently superseded or resolved by the new implementation.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **55** PR #5 inline material threads unresolved.
2. Prove the corrected terminal REVIEW-0045 state checkpoint exact-head.
3. Correct the six P1s in a code+tests candidate without broadening scope.
4. Re-prove 100% line+branch and live read-only PR #2 contract on the corrective head.
5. Synchronize TEST-0009 / WORK-0002 / PROJECT_STATE and create REVIEW-0046 `OPEN`, then `IN_PROGRESS` only after an OPEN proof.
6. Freeze the exact REVIEW-0046 candidate for one fresh independent L2.
7. No merge or thread resolution before a clean successor review.
8. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0045.yaml
9. issue #7 scheduler state
10. live PR #5 exact HEAD/checks/reviews/55 threads
11. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
