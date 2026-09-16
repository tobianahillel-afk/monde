# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- PHASE-0 and LOT-0 remain `IN_PROGRESS`.
- WORK-0001 is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- WORK-0002 remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain blocked until WORK-0002 independently closes.

## PR #5 / T12 trusted predecessor

PR #5 (`chore/work-0002-stale-green-bootstrap`) remains the narrow trusted-default-branch predecessor for WORK-0002/T12. No merge and no review-thread resolution is permitted while material findings remain open.

The current corrective candidate uses bounded progress-preserving scheduling:

1. stable unique open Pull Requests authority is read;
2. PRs are grouped by exact head SHA;
3. head groups rotate by a ten-minute fairness slot;
4. at most seven head groups are considered per invocation;
5. exact merge-acceptable required-check state is confirmed per selected head;
6. stable open authority is refreshed before target resolution;
7. a PR-bound target is resolved per sibling using canonical `refs/pull/<N>/merge` authority and its protected current-attempt job is validated;
8. current review-thread state is read immediately before rerun decision;
9. a now-clean sibling is skipped; at most one unresolved sibling is rerun for a shared SHA in one invocation;
10. at most three reruns occur per invocation;
11. the 60-call hard limit remains the last-resort network guard.

Only the trusted scheduled default-branch path has `actions: write`; the live PR #2 probe remains read-only.

## Review lifecycle

- REVIEW-0031..0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0040 and REVIEW-0041: `CLOSED` administrative negative evidence.
- REVIEW-0042: `COMPLETE / CHANGES_REQUIRED` on `1120bbb9d1548bf0b20c6c1052731c0bf4154a00`.
- REVIEW-0043: `COMPLETE / CHANGES_REQUIRED` on `3bce7808d7d30b361559d54663bc0808ab4cdcf6`; independent review `PRR_kwDOUUI5ts8AAAABNyER4A` added `PRRT_kwDOUUI5ts6i1TEN` and `PRRT_kwDOUUI5ts6i1TES`.
- PR #5 has **46 inline material threads**, all still unresolved.
- REVIEW-0044 OPEN checkpoint `71a1d0ff13ec25674f2d27201b261b7cbd149ae2` passed Bootstrap #104 / `35075414885` with **86/86 tests, 664 statements, 292 branches, 100% line+branch, live PR #2 probe 7/60**.
- REVIEW-0044 is now **`IN_PROGRESS`**. The synchronized IN_PROGRESS descendant must itself pass before any independent Codex invocation.

## Corrective proof chain after REVIEW-0043

- `9d66a80104e9f2fc98db362bd41f13f923313cf0` — REVIEW-0043 terminal-negative checkpoint; Bootstrap #100 / `35070576172` green.
- `38eceaab2da8320bad8a5b3929425bf1f14df54a` — first progress scheduler; #101 live probe green, self-test exposed one historical assertion mismatch.
- `bc1a665f2d38efaa313393565ad2c66f789f8a42` — per-PR sibling target resolution; #102 had 85 tests PASS and live probe green but one uncovered branch.
- `a1441f506fb1a0f42dbdf984d42e1f847e55db51` — coverage-only fallthrough regression; #103 / `35075010644`: **86/86 tests, 664 statements / 292 branches, 100%, live probe 7/60**.
- `71a1d0ff13ec25674f2d27201b261b7cbd149ae2` — REVIEW-0044 OPEN state checkpoint; #104 / `35075414885` repeated the same exact proof: **86/86, 664/292, 100%, live probe 7/60**.

The fourteen-head adversarial regression models the nominal request path and requires the first three reruns at request counts **10, 18 and 26**, rather than 60 calls before the first mutation.

## REVIEW-0044 mandate

REVIEW-0044 must independently challenge:

- fairness of time-derived ten-minute rotation under missed/delayed/duplicated schedules;
- starvation when clean heads occupy the seven-head selected window;
- request-budget exhaustion under pathological pagination/history expansion;
- whether one-rerun-per-shared-SHA plus final thread reclassification prevents clean-sibling green revival;
- state changes or independent same-head gate completion after the final GraphQL read;
- per-PR `refs/pull/<N>/merge` authority, including rerun attempts;
- target protected-job/current-attempt authority;
- remaining Checks / PR authority / Actions / GraphQL / rerun TOCTOU;
- exact test discovery, least privilege, hard-budget accounting and traceability;
- all **46 unresolved historical material threads**.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final behavior into `tools/governance/thread_state_poll.py`.

Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all 46 PR #5 inline material threads unresolved.
2. Publish REVIEW-0044 `IN_PROGRESS` + WORK-0002 + PROJECT_STATE atomically above the proven OPEN checkpoint.
3. Prove that exact IN_PROGRESS descendant with Bootstrap self-test and live PR #2 contract probe.
4. Freeze that exact SHA and invoke exactly one fresh-context independent `@codex review` for REVIEW-0044.
5. Any new material finding requires correction, re-proof and another successor review; do not resolve historical threads mechanically.
6. Only a clean exact-head independent successor permits controlled verification/resolution and guarded PR #5 merge consideration.
7. After PR #5 merge, integrate main into PR #2, port parity, prove T12, run fresh PR #2 L2 and obtain eligible non-author exact-head APPROVED evidence before WORK-0002 closure.
8. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0043.yaml
9. registry/reviews/REVIEW-0044.yaml
10. live PR #5 exact HEAD/checks/reviews/46 threads
11. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
