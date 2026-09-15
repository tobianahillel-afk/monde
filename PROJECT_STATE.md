# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **WORK-0001** is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- **WORK-0002** remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain blocked until WORK-0002 independently closes.

## PR #5 — trusted default-branch stale-green predecessor

PR #5 (`chore/work-0002-stale-green-bootstrap`) exists because GitHub scheduled workflows execute trusted default-branch code; PR #2 cannot prove its own pre-merge stale-green invalidation before the predecessor is on `main`.

The bootstrap now follows a **positive-authority / closed-world** split:

1. Effective merge state is read directly from the exact latest GitHub Actions-owned `MONDE / Merge Gate` check for the exact head SHA.
2. A PR becomes an invalidation candidate only when that exact check is completed with GitHub merge-acceptable conclusion `success`, `neutral`, or `skipped` **and** GraphQL review threads are unresolved.
3. Only after that positive stale-green classification does MONDE sample closed-PR overlap history and canonical Actions workflow history for the current PR incarnation.
4. Actions workflow history is only rerun-capability evidence, never merge-state authority.
5. The selected target run must be canonical/current-incarnation and expose exactly one valid current-attempt protected `MONDE / Merge Gate` job before rerun.
6. Clean, incomplete, non-merge-acceptable, or thread-clean PRs never trigger target-history/closed-history discovery.

Additional hardening remains in force:

- canonical workflow ID `354465551` and path `.github/workflows/governance.yml`;
- strict positive non-Boolean integer typing for workflow_id, PR/run/job/check IDs and attempts where applicable;
- filtered workflow-run searches partition into closed non-overlapping second windows below GitHub's 1,000-result search ceiling;
- a saturated one-second interval fails closed;
- accepted filtered windows require exact unique IDs and two identical canonical snapshots;
- Actions `workflow_runs` and `jobs` pagination validates typed/stable authoritative `total_count`, exact identities and completeness;
- closed PR history is requested `updated desc` and bounded to lifetimes capable of overlapping the earliest **stale-green** active incarnation;
- overlap attribution does not trust a closed PR's final SHA snapshot as complete historical identity;
- exact required-check state is cached per SHA; target-job validation is cached per `(run_id, run_attempt)`;
- schedule is every 10 minutes; only trusted scheduled default-branch code has `actions: write`;
- live contract probe uses read-only `Actions`, `Checks`, `Contents`, and `PullRequests` permissions;
- GraphQL reviewThreads pagination fails closed on malformed nodes/pageInfo/cursors;
- workflow test discovery covers `test_stale_green_bootstrap*.py`;
- TEST-0009 lists all **six** current regression modules, including explicit poll-order tests.

## Review lifecycle

- REVIEW-0031 through REVIEW-0039 are terminal `COMPLETE / CHANGES_REQUIRED` negative evidence and are never reopened or rewritten.
- REVIEW-0039 independent review `PRR_kwDOUUI5ts8AAAABNuOmoQ` on `402519d73d55a2b45507b23e319c8fb42ad440f1` added six P1 findings and raised the historical inline PR #5 material-thread set to **42**.
- REVIEW-0040 reached `IN_PROGRESS` on exact `3f31658ca2f892e1dd24c7faa4462e3d7e958aaf`, which passed Bootstrap #82 / `35028081680` at 100% line+branch with live probe.
- Before an independent REVIEW-0040 result returned, author-side adversarial review `PRR_kwDOUUI5ts8AAAABNuingg` found a new P1: rerun-target history was snapshotted before the exact check/thread classification, so a run completing between those observations could publish a stale-green check absent from the earlier target snapshot.
- REVIEW-0040 is therefore **`CLOSED` administrative negative evidence**, not independent approval evidence.
- REVIEW-0041 is **`OPEN`** and becomes the next true L2 review target after its lifecycle checkpoints are independently proven exact-head.

All **42 historical inline material PR #5 threads remain unresolved**. The REVIEW-0040 race finding is one additional material author-side finding recorded as review `PRR_kwDOUUI5ts8AAAABNuingg`; it is not an inline PRRT and must not be miscounted as a 43rd inline thread.

## REVIEW-0040 race correction

The scheduled poll was reordered from:

`open PRs -> target-history snapshot -> exact check -> review threads -> rerun`

to:

`open PRs -> exact check -> review threads -> stale-green set -> fresh overlap/target history -> target job -> rerun`.

This closes the stale target-snapshot race and also reduces API cost: clean or non-merge-acceptable PRs no longer incur closed-history or double-read Actions target-history work.

Explicit regressions were added in `.github/scripts/test_stale_green_bootstrap_poll_order.py` and traced in TEST-0009. They prove:

- target-history discovery happens only after exact check + unresolved-thread classification;
- the selected history receives only positively stale-green PR identities;
- clean and non-merge-acceptable PRs do not call overlap-window discovery, target-run discovery, target-job validation, or rerun.

## Exact proof chain after REVIEW-0039

- `9f2fccc254937ca1b1e28be26bcbad60f85308e0` — Bootstrap #80 / `35026563188`: 63/63 tests, 450/450 statements, 200/200 branches, 100% line+branch, live PR #2 probe SUCCESS.
- REVIEW-0040 OPEN proof descendant `ce2581d4cb112251296aff611490023f878caa92` — #81 / `35027740434`: same 63/450/200/100 proof + live probe SUCCESS.
- REVIEW-0040 IN_PROGRESS proof descendant `3f31658ca2f892e1dd24c7faa4462e3d7e958aaf` — #82 / `35028081680`: same 63/450/200/100 proof + live probe SUCCESS.
- Race corrective runtime `e221fece4bcbd438195c06a5431f7759440e6f90` — #85 / `35028424764`: 63 tests, 457/457 statements, 204/204 branches, 100% line+branch, live probe SUCCESS.
- Regression-complete correction `e594e88c1c635d3fd8a5180e37930719dc4c0103` — #87 / `35028626562`: **65/65 tests, 457/457 statements, 204/204 branches, 100% line+branch**, live PR #2 probe SUCCESS.

The synchronized REVIEW-0040-CLOSED / REVIEW-0041-OPEN / WORK / PROJECT_STATE checkpoint created after #87 must receive its own exact-head proof before REVIEW-0041 may move `IN_PROGRESS`.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031..REVIEW-0039 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0040 (CLOSED) + REVIEW-0041 (OPEN)`

REQ-0026 remains `PROPOSED` and TEST-0009 remains `PLANNED`; prior execution evidence is not retroactively promoted into acceptance/PASS evidence.

## WORK-0002 / PR #2 relationship

PR #2 remains open at known head **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** unless live GitHub now reports otherwise. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

Known PR #2 state before any fresh re-query:

- 73 unresolved material threads;
- Gate #228 / run `34997568781` proved its branch-local core after PR-numbered run-name hardening;
- final closure still needs trusted-base bootstrap integration, durable poller parity, exact durable/live T12 identities, full re-proof, fresh L2, and eligible non-author exact-head APPROVED review.

After PR #5 eventually merges, PR #2 must integrate the new `main` through an explicit two-parent merge and port/reuse the hardened contract into its older permissive `tools/governance/thread_state_poll.py`, including:

- exact required Checks authority;
- stale-green-first classification;
- current-incarnation rerun-target discovery only after classification;
- filtered-search cap partitioning + stable unique snapshots;
- bounded closed-history overlap detection;
- strict identifiers/attempts;
- exact target protected-job authority;
- `success|neutral|skipped` merge semantics;
- per-poll caches / request-budget controls;
- malformed-record fail-closed behavior.

T12 cannot close merely because PR #5 exists or merges.

## Repository visibility

MONDE intentionally remains public. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data.

## Current next action

1. Prove the synchronized REVIEW-0040 `CLOSED` + REVIEW-0041 `OPEN` + WORK-0002 + PROJECT_STATE checkpoint exact-head.
2. Keep all 42 historical inline PR #5 material threads unresolved.
3. If the OPEN checkpoint is green, atomically transition REVIEW-0041 / WORK-0002 / PROJECT_STATE to `IN_PROGRESS`.
4. Prove that exact IN_PROGRESS descendant.
5. Freeze the exact head and invoke a fresh-context independent Codex REVIEW-0041.
6. REVIEW-0041 must re-check all 42 historical inline findings plus the REVIEW-0040 ordering race, and actively red-team remaining TOCTOU between Checks, GraphQL threads and later target discovery, shared-head PRs, exact check ambiguity, target-current-incarnation attribution, filtered snapshots, closed-history bounds, strict typing, cache identity, permissions and API budget.
7. Any new material finding requires correction/re-proof and another successor review. Do not mechanically resolve historical threads.
8. Only a clean exact-head independent successor review permits controlled verification/resolution of historical threads and a guarded PR #5 merge decision.
9. After PR #5 merge, integrate main into PR #2, port durable poller parity, prove T12, run fresh PR #2 L2, obtain eligible non-author exact-head APPROVED review, then consider WORK-0002 closure.
10. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/requirements/REQ-0026.yaml`
7. `registry/tests/TEST-0009.yaml`
8. `registry/reviews/REVIEW-0039.yaml`
9. `registry/reviews/REVIEW-0040.yaml`
10. `registry/reviews/REVIEW-0041.yaml`
11. live PR #5 exact HEAD/checks/reviews/threads
12. live PR #2 exact HEAD/checks/reviews/threads
13. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
