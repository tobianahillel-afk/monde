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

REVIEW-0047 is terminal `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `d266d73c15b524413209be16d4970ec42928ea04` via independent review `PRR_kwDOUUI5ts8AAAABN1lrxA`.

REVIEW-0048 is `CLOSED / CHANGES_REQUIRED` administrative negative evidence on frozen HEAD `b5932be9a5f2d36c192bf482a3051a8523b97a34`; its Codex invocation was refused by quota and author-side `PRR_kwDOUUI5ts8AAAABN4OKew` invalidated that candidate.

## REVIEW-0049 — independent terminal negative evidence

REVIEW-0049's V4 write-ahead candidate `7d7f52fe5beb6bf7466a523b0fb0ea75108ff9a5` passed Bootstrap #145, and its frozen lifecycle head `c8f1fec24358c25224771a15b647d56c8a2f0287` passed Bootstrap #147. A fresh Codex L2 ultimately completed on that exact frozen head at `2026-09-16T18:38:10Z` as **`PRR_kwDOUUI5ts8AAAABN4sxvg`**.

REVIEW-0049 is therefore **`COMPLETE / CHANGES_REQUIRED`**, not administrative CLOSED. It added two independent P1 findings:

- `PRRT_kwDOUUI5ts6jEPa-` — a write-ahead pending intent can remain forever at the baseline if the process dies after the issue PATCH but before the rerun POST; without an explicit safe recovery/escalation path, the global poll is permanently wedged.
- `PRRT_kwDOUUI5ts6jEPa_` — closing the pending origin PR cannot erase an already-issued rerun before its terminal head-scoped effect is accounted for.

Author-side `PRR_kwDOUUI5ts8AAAABN4rPMg` independently corroborated the closed-origin race shortly before the Codex L2 completed. PR #5 now has **65 inline material threads**, all intentionally unresolved.

## REVIEW-0050 technical candidate and OPEN lifecycle

REVIEW-0050 addresses both independent REVIEW-0049 P1s without weakening prior fail-closed authority:

1. V5 scheduler state carries exact reversible `pending_head` in addition to origin PR/run/baseline/check authority.
2. Origin-PR closure no longer clears pending state; the exact issued run remains observed to a terminal causally-bound result.
3. A terminal merge-acceptable closed-origin rerun causes current open same-head PRs to be reclassified; any unresolved sibling is durably retained through `scan_pr` before pending state is released.
4. Ambiguous bounded pending observation is now **loud** (`PendingRecoveryRequired`) while durable pending state remains intact; automatic replay remains forbidden.
5. A trusted `workflow_dispatch` break-glass path may clear only an operator-confirmed **unposted** pending intent. It requires the exact pending PR/head/run/baseline/check tuple, an exact confirmation phrase, and an auditable reason.
6. Recovery revalidates that the run attempt is still exactly the baseline and that the prior effective-check identity is unchanged before clearing state.
7. Recovery is serialized with the normal poll and has `actions: read` but **no `actions:write`**, so it cannot itself issue a workflow rerun.

Exact technical candidate **`cbe21fa4cebc1c8f8b3030af17284de5700f9818`** passed MONDE Stale-Green Bootstrap **#154 / run `35152847816` SUCCESS**:

- **194/194 tests PASS**;
- **1,856 statements / 842 branches** across core, snapshot and all authority successors;
- **100% line + branch coverage** with zero missing statements/branches;
- live read-only GitHub contract probe against PR #2 **SUCCESS**;
- recovery job correctly skipped on pull-request CI and its workflow permission set excludes `actions:write`.

REVIEW-0050 is now being opened for independent semantic review. Technical proof is evidence only, not approval. T4/T12/AC-6 remain `IN_REVIEW` and all **65** material inline threads remain unresolved.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **65** PR #5 inline material threads unresolved.
2. Publish the synchronized REVIEW-0049 COMPLETE + REVIEW-0050 OPEN + TEST-0009 + WORK-0002 + PROJECT_STATE checkpoint over the proven `cbe21fa4…` runtime.
3. Exact-head prove that `OPEN` checkpoint; runtime must remain equivalent to candidate #154.
4. If green, transition REVIEW-0050 to `IN_PROGRESS` in a second state-only checkpoint and re-prove that exact SHA.
5. Freeze the resulting SHA, re-query PR #5 HEAD/reviews/65 threads, and update the PR description.
6. Request exactly one fresh independent L2 on the frozen SHA; do not mutate the Git tree while it runs.
7. Red-team especially manual recovery evidence quality, false/stale operator assertions, run/check TOCTOU, closed-origin shared-head revival, recovery permissions, writer serialization and all historical findings.
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
8. registry/reviews/REVIEW-0049.yaml
9. registry/reviews/REVIEW-0050.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/65 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
