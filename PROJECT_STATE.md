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

REVIEW-0049 is terminal `COMPLETE / CHANGES_REQUIRED` independent negative evidence on exact head `c8f1fec24358c25224771a15b647d56c8a2f0287` via `PRR_kwDOUUI5ts8AAAABN4sxvg`.

## REVIEW-0050 — administrative terminal negative evidence

REVIEW-0050 technical candidate `cbe21fa4cebc1c8f8b3030af17284de5700f9818` passed Bootstrap #154 / run `35152847816` with **194/194 tests**, **1,856 statements / 842 branches**, **100% line + branch**, and live read-only PR #2 contract probe SUCCESS. Its OPEN checkpoint `871850ac5b66a43cfd8491ef445d1738ad09d822` passed #155 and frozen IN_PROGRESS head `f2ec7e8a0ca30b2be3272b2b1f022b7dabd7048c` passed #156.

REVIEW-0050 is nevertheless now **`CLOSED / CHANGES_REQUIRED`**. No exact-head independent L2 was submitted before author-side adversarial review **`PRR_kwDOUUI5ts8AAAABN7LvGQ`** invalidated the frozen head.

The P1 is a positive-authorization failure in break-glass recovery: recovery reads the baseline run attempt and prior effective-check identity, then later clears issue #7. The workflow concurrency group serializes this bootstrap workflow with itself, but cannot serialize collaborators, GitHub UI, REST clients or another workflow capable of rerunning the canonical run. An external rerun can therefore start after the last GET and before the issue PATCH, leaving a new head-scoped mutation in flight after the only durable pending identity has been erased.

A third or fourth GET cannot solve this TOCTOU. REVIEW-0051 must remove recovery's authority to clear pending state from non-atomic observations.

All **65** historical inline material threads remain unresolved. No merge is permitted.

## REVIEW-0051 corrective direction

The minimum safe successor is intentionally simpler:

- preserve the proven REVIEW-0050 V5 poll and closed-origin pending observation behavior;
- replace break-glass clear with an inspection/authorization runbook that **never writes scheduler state and never automatically reruns**;
- require the exact durable pending tuple, exact confirmation phrase and auditable reason;
- positively revalidate unchanged baseline attempt and prior effective-check identity only to establish that the operator is looking at the intended pending record;
- keep issue #7 pending unchanged throughout recovery inspection;
- instruct the operator to rerun the exact canonical run manually if they have independently established that the original POST never occurred;
- let the normal serialized poll observe `baseline+1` under the existing durable pending identity;
- if another actor races and attribution becomes ambiguous, retain pending state and fail closed rather than erasing authority;
- keep recovery permissions read-only for Actions and without `actions:write`;
- add regressions proving recovery cannot call `_write_state` or `rerun_workflow` and cannot clear pending under any accepted request.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **65** PR #5 inline material threads unresolved.
2. Exact-head prove this REVIEW-0050 `CLOSED / CHANGES_REQUIRED` state-only checkpoint.
3. Implement REVIEW-0051 as a new recovery adapter; do not rewrite REVIEW-0050 history.
4. Remove every recovery clear/write path and preserve durable pending authority.
5. Add exact-tuple inspection and manual-rerun runbook regressions.
6. Preserve live read-only PR #2 probing and 100% line+branch proof.
7. Only after a fully green runtime create REVIEW-0051 `OPEN`, prove it, then `IN_PROGRESS`, prove/freeze, and request one fresh exact-head L2.
8. Resolve no historical thread before a clean successor review.
9. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0049.yaml
9. registry/reviews/REVIEW-0050.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/65 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
