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

PR #5 (`chore/work-0002-stale-green-bootstrap`) is the narrow T12 predecessor required because scheduled workflows execute trusted default-branch code; PR #2 cannot prove its own pre-merge stale-green invalidation before that predecessor exists on `main`.

The bootstrap currently follows this positive-authority sequence:

1. Read the complete open Pull Requests set through **two identical canonical authority snapshots** with exact unique positive PR numbers.
2. Read the exact latest GitHub Actions-owned `MONDE / Merge Gate` check for each exact head SHA.
3. For merge-acceptable exact checks (`success`, `neutral`, `skipped`), read GraphQL review-thread state.
4. Build only the positively stale-green PR set.
5. For each stale-green branch identity, read bounded closed Pull Requests history through **two identical canonical authority snapshots** with exact unique positive PR numbers.
6. Discover canonical current-incarnation Actions rerun targets only for that stale-green set.
7. Validate exactly one protected current-attempt `MONDE / Merge Gate` job on the selected target run.
8. Rerun that canonical workflow run.

Actions workflow history is never merge-state authority. Clean, incomplete, non-merge-acceptable or thread-clean PRs do not incur target-history/closed-history discovery.

## PR authority snapshot hardening

REVIEW-0041 found that open and closed Pull Requests lists were still single offset-paginated traversals even though Actions pagination had already been hardened against duplicate/membership drift.

The correction adds `.github/scripts/stale_green_bootstrap_pr_snapshot.py`, a narrow executable adapter that:

- invokes the existing validated core readers twice;
- rejects malformed/non-positive/duplicate PR numbers;
- compares normalized authority fingerprints independent of record ordering;
- open fingerprint: `number`, `state`, head repository/ref/SHA, `created_at`;
- closed fingerprint: the same plus `closed_at` and `updated_at`;
- fails closed when the two complete authority snapshots disagree;
- installs the stabilized open and closed readers before `core.main()` executes.

Both **live contract probe** and **trusted scheduled mutation path** now execute the adapter, not the unwrapped core script.

## Other hardening still in force

- canonical workflow ID `354465551` / `.github/workflows/governance.yml`;
- direct Checks API effective authority using exact head/name/GitHub-Actions app;
- filtered workflow-run searches partition into closed non-overlapping second windows below GitHub's 1,000-result ceiling;
- a saturated one-second filtered interval fails closed;
- Actions filtered windows require exact unique run IDs and two identical canonical snapshots;
- Actions `workflow_runs` and `jobs` pagination validates typed/stable authoritative `total_count`, exact identities and completeness;
- current-incarnation attribution uses PR/run creation time plus same-repository/same-branch overlap windows and does not trust a closed PR's final SHA as complete branch history;
- closed history is ordered by `updated desc` and bounded by the earliest stale-green active incarnation capable of overlap;
- exact positive non-Boolean typing for workflow_id, PR/run/job/check IDs and attempts where applicable;
- exact required-check cache per SHA and target-job cache per `(run_id, run_attempt)`;
- schedule every ten minutes with five-minute job timeout;
- only trusted scheduled default-branch code has `actions: write`;
- live contract probe uses read-only Actions/Checks/Contents/PullRequests;
- GraphQL reviewThreads pagination fails closed on malformed state/cursor metadata;
- workflow discovery covers `test_stale_green_bootstrap*.py`;
- TEST-0009 now lists **seven** bootstrap regression modules.

## Review lifecycle

- REVIEW-0031 through REVIEW-0039 are terminal `COMPLETE / CHANGES_REQUIRED` negative evidence and are never reopened.
- REVIEW-0039 independent Codex review `PRR_kwDOUUI5ts8AAAABNuOmoQ` on `402519d73d55a2b45507b23e319c8fb42ad440f1` raised the historical inline material-thread set to **42**.
- REVIEW-0040 is `CLOSED`: author-side P1 `PRR_kwDOUUI5ts8AAAABNuingg` invalidated its frozen head before independent Codex returned. It found rerun-target history was sampled before stale-green classification.
- REVIEW-0041 is `CLOSED`: author-side P1 `PRR_kwDOUUI5ts8AAAABNvBAIQ` invalidated frozen head `91ba0314392038862a278e93922fcecef80423b5` before independent Codex returned. It found Pull Requests offset pagination lacked unique stable authority snapshots.
- REVIEW-0042 is **`OPEN`** and is the next independent L2 target after its OPEN and IN_PROGRESS checkpoints are each exact-head proven.

All **42 historical inline material PR #5 threads remain unresolved**. REVIEW-0040 and REVIEW-0041 add author-side material negative evidence but are not extra inline PRRT threads.

## Exact recent proof chain

- `e594e88c1c635d3fd8a5180e37930719dc4c0103` — Bootstrap #87 / `35028626562`: 65/65 tests, 457/457 statements, 204/204 branches, 100% line+branch, live probe SUCCESS.
- REVIEW-0041 OPEN descendant `558dfdc7f6d34e2c38d0bda2245548add671d46c` — #89 / `35029137723`: same 65/457/204/100% proof + live probe SUCCESS.
- REVIEW-0041 IN_PROGRESS exact `91ba0314392038862a278e93922fcecef80423b5` — #90 / `35033497071`: same 65/457/204/100% proof + live probe SUCCESS; then invalidated by `PRR_kwDOUUI5ts8AAAABNvBAIQ`.
- Pull Requests snapshot corrective candidate `5d4e3a5578d4ccf26ca8b89d0717a150d6d6102b` — Bootstrap #91 / `35034183087`: **72/72 tests**, core **457/457 statements + 204/204 branches**, adapter **49/49 statements + 18/18 branches**, total **506 statements / 222 branches at 100% line+branch**, live adapter-based PR #2 probe SUCCESS with `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031..REVIEW-0039 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0040 (CLOSED) + REVIEW-0041 (CLOSED) + REVIEW-0042 (OPEN)`

REQ-0026 remains `PROPOSED`; TEST-0009 remains `PLANNED`. Prior successful executions are not retroactively promoted into acceptance/PASS evidence.

## WORK-0002 / PR #2 relationship

Live PR #2 was re-queried during REVIEW-0041 and remains open/mergeable at head **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`**. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

Known current facts:

- 73 material PR #2 review threads remain unresolved from the last branch-local closure state;
- Gate #228 / run `34997568781` remains the known exact-head proof; its current exact `MONDE / Merge Gate` check is failure, so PR #2 is not stale-green now;
- T12 correction code is proven branch-locally but trusted predecessor integration and durable-poller parity remain pending;
- final closure still requires fresh exact-head L2 plus eligible non-author exact-head `APPROVED` collaborator evidence.

After PR #5 eventually merges, PR #2 must explicitly integrate the new `main` through a two-parent merge and port/reuse the final bootstrap behavior directly into `tools/governance/thread_state_poll.py`, including:

- direct exact Checks authority;
- stable unique open/closed PR authority snapshots;
- stale-green-first classification;
- current-incarnation rerun-target discovery only after classification;
- filtered-search cap partitioning + stable unique Actions snapshots;
- bounded branch-reset-safe closed-history overlap detection;
- strict identifiers/attempts;
- exact target protected-job authority;
- `success|neutral|skipped` merge semantics;
- per-poll caches / request-budget controls;
- malformed-record fail-closed behavior.

T12 cannot close merely because PR #5 exists or merges.

## Repository visibility

MONDE intentionally remains public. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data.

## Current next action

1. Keep all 42 historical inline PR #5 material threads unresolved.
2. Publish synchronized `REVIEW-0041 CLOSED / REVIEW-0042 OPEN / WORK-0002 / PROJECT_STATE` checkpoint on top of corrective `5d4e3a5...`.
3. Prove that exact REVIEW-0042 OPEN descendant with the 72-test / 506-statement / 222-branch suite plus live adapter-based probe.
4. If green, atomically move REVIEW-0042 to `IN_PROGRESS` with WORK/PROJECT and prove that exact descendant.
5. Freeze the proven IN_PROGRESS SHA and invoke fresh-context independent Codex REVIEW-0042.
6. REVIEW-0042 must re-check all 42 historical inline findings plus both author-side findings, especially PR snapshot adapter installation, unique/stable open/closed authority, request-budget impact, remaining Checks/GraphQL/Actions TOCTOU, shared-head PRs, current-incarnation attribution, filtered snapshots, closed-history bounds, strict typing and least privilege.
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
8. `registry/reviews/REVIEW-0040.yaml`
9. `registry/reviews/REVIEW-0041.yaml`
10. `registry/reviews/REVIEW-0042.yaml`
11. live PR #5 exact HEAD/checks/reviews/threads
12. live PR #2 exact HEAD/checks/reviews/threads
13. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
