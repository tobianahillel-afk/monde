# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- PHASE-0 and LOT-0 remain `IN_PROGRESS`.
- WORK-0001 is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- WORK-0002 remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain blocked until WORK-0002 independently closes.

## PR #5 purpose

PR #5 (`chore/work-0002-stale-green-bootstrap`) is the narrow trusted-default-branch T12 predecessor required because scheduled workflows execute trusted default-branch code. PR #2 cannot self-prove this pre-merge invariant.

## Current bootstrap contract

The trusted bootstrap now executes through `.github/scripts/stale_green_bootstrap_pr_snapshot.py` and follows:

1. Read open Pull Requests twice; require exact unique positive PR numbers and identical canonical authority fingerprints.
2. Read the exact latest GitHub Actions-owned `MONDE / Merge Gate` check for each exact head SHA.
3. For merge-acceptable exact checks (`success`, `neutral`, `skipped`), read GraphQL review-thread state.
4. Build only the positively stale-green PR set.
5. For stale-green branch identities only, read bounded closed Pull Requests history twice; require exact unique PR numbers and identical canonical authority fingerprints.
6. Discover current-incarnation canonical Actions rerun targets only for that stale-green set.
7. Validate exactly one protected current-attempt `MONDE / Merge Gate` job on the selected run.
8. Rerun that canonical run.

Pull Requests authority fingerprints bind `number/state/head repository/ref/SHA/created_at`; closed history also binds `closed_at/updated_at`. Record ordering is normalized. Duplicate identity or membership/state drift fails closed.

Actions workflow history remains rerun-capability evidence only, never merge-state authority. Filtered workflow-run history remains partitioned into closed non-overlapping second windows under GitHub's 1,000-result ceiling, with exact unique IDs and two identical snapshots; saturated one-second windows fail closed.

Current-incarnation attribution remains branch-reset safe through PR/run creation times plus same-repository/same-branch closed-lifetime overlap windows. Identifiers/attempts use exact positive non-Boolean integer semantics. Only the trusted scheduled job has `actions: write`; live probe is read-only. Schedule remains every ten minutes.

## Review lifecycle

- REVIEW-0031 through REVIEW-0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- Historical inline material PR #5 set: **42 threads**, all still unresolved.
- REVIEW-0040: `CLOSED`; author-side P1 `PRR_kwDOUUI5ts8AAAABNuingg` found target-history-before-stale-classification race before independent review returned.
- REVIEW-0041: `CLOSED`; author-side P1 `PRR_kwDOUUI5ts8AAAABNvBAIQ` found open/closed Pull Requests offset pagination lacked unique stable authority snapshots before independent review returned.
- REVIEW-0042: **`IN_PROGRESS`** in the same Git-tree checkpoint as matching WORK-0002 and PROJECT_STATE. Its exact descendant must pass before fresh independent Codex invocation.

REVIEW-0040 and REVIEW-0041 findings are additional author-side negative evidence, not extra inline PRRT threads.

## Recent exact proof chain

- `e594e88c1c635d3fd8a5180e37930719dc4c0103` — #87 / `35028626562`: 65 tests, 457 statements, 204 branches, 100% + live probe.
- REVIEW-0041 OPEN `558dfdc7f6d34e2c38d0bda2245548add671d46c` — #89 / `35029137723`: same 65/457/204/100% + live probe.
- REVIEW-0041 IN_PROGRESS `91ba0314392038862a278e93922fcecef80423b5` — #90 / `35033497071`: same proof; later invalidated by `PRR_kwDOUUI5ts8AAAABNvBAIQ`.
- PR-snapshot correction `5d4e3a5578d4ccf26ca8b89d0717a150d6d6102b` — #91 / `35034183087`: **72/72 tests**, core 457 statements/204 branches and adapter 49 statements/18 branches, total **506 statements / 222 branches at 100%**, live adapter-based PR #2 probe SUCCESS: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`.
- REVIEW-0042 OPEN checkpoint `e629ca97ed608f523802375f184c72580b0c7e3a` — #92 / `35034454790`: self-test SUCCESS and live adapter probe SUCCESS.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031..0039 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0040 (CLOSED) + REVIEW-0041 (CLOSED) + REVIEW-0042 (IN_PROGRESS)`

TEST-0009 now lists seven bootstrap regression modules, including stale-first ordering and stable Pull Requests authority snapshots. REQ-0026 remains PROPOSED and TEST-0009 remains PLANNED; old successful runs are not retroactively promoted into acceptance/PASS evidence.

## PR #2 relationship

PR #2 was re-queried during this cycle and remains open/mergeable at `4046e03b1e00a2051d29ccd6dcf5f0af7426259a`. Its current exact `MONDE / Merge Gate` check is failure, so PR #2 is not currently stale-green. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 history.

Known closure state remains:

- 73 unresolved material PR #2 threads from last branch-local review state;
- known Gate #228 / run `34997568781` proof;
- trusted predecessor integration + durable-poller parity still pending;
- final fresh exact-head L2 and eligible non-author exact-head APPROVED collaborator evidence still required.

After PR #5 eventually merges, PR #2 must explicitly two-parent merge new `main` and directly port/reuse the final bootstrap contract into `tools/governance/thread_state_poll.py`: exact Checks authority, stable unique PR snapshots, stale-green-first classification, current-incarnation target discovery, partitioned stable Actions snapshots, bounded branch-reset-safe closed history, strict IDs/attempts, target-job authority, GitHub merge semantics, caches/request-budget controls and malformed-state fail-closed behavior.

T12 cannot close merely because PR #5 exists or merges.

## Current next action

1. Keep all 42 historical inline PR #5 threads unresolved.
2. Prove the exact synchronized REVIEW-0042 `IN_PROGRESS` + WORK-0002 + PROJECT_STATE descendant.
3. If green, freeze that exact HEAD and invoke fresh-context independent Codex REVIEW-0042.
4. REVIEW-0042 must re-check the 42 inline findings plus both author-side findings, with emphasis on adapter installation, stable/unique open+closed PR authority, remaining Checks/GraphQL/Actions TOCTOU, current-incarnation attribution, request budget after snapshot doubling, filtered snapshots, closed-history bounds, strict typing and least privilege.
5. Any new material finding requires correction/re-proof and another successor review; do not mechanically resolve historical threads.
6. Only a clean exact-head independent successor review permits controlled verification/resolution and a guarded PR #5 merge decision.
7. After PR #5 merge, integrate main into PR #2, port durable parity, prove T12, run fresh PR #2 L2, obtain eligible non-author exact-head APPROVED review, then consider WORK-0002 closure.
8. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0040.yaml
9. registry/reviews/REVIEW-0041.yaml
10. registry/reviews/REVIEW-0042.yaml
11. live PR #5 exact HEAD/checks/reviews/threads
12. live PR #2 exact HEAD/checks/reviews/threads
13. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

MONDE remains public. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data.
