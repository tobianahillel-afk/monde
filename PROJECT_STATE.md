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

The reviewed candidate at `379b4e00aa973f74c9bb973a1e79381f43332f0b` used bounded head-group scheduling, at most seven selected heads and three reruns, per-sibling PR-bound target resolution, final thread-state reclassification and a 60-call hard guard. REVIEW-0044 proved that these controls are still insufficient.

Only the trusted scheduled default-branch path has `actions: write`; the live PR #2 probe remains read-only.

## Review lifecycle

- REVIEW-0031..0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0040 and REVIEW-0041: `CLOSED` administrative negative evidence.
- REVIEW-0042: `COMPLETE / CHANGES_REQUIRED` on `1120bbb9d1548bf0b20c6c1052731c0bf4154a00`.
- REVIEW-0043: `COMPLETE / CHANGES_REQUIRED` on `3bce7808d7d30b361559d54663bc0808ab4cdcf6`; independent review `PRR_kwDOUUI5ts8AAAABNyER4A` added `PRRT_kwDOUUI5ts6i1TEN` and `PRRT_kwDOUUI5ts6i1TES`.
- REVIEW-0044: **`COMPLETE / CHANGES_REQUIRED`** on exact head `379b4e00aa973f74c9bb973a1e79381f43332f0b`; independent review `PRR_kwDOUUI5ts8AAAABNytEOQ` added `PRRT_kwDOUUI5ts6i2qvx`, `PRRT_kwDOUUI5ts6i2qv4`, and `PRRT_kwDOUUI5ts6i2qwA`.
- Author-side exact-head review `PRR_kwDOUUI5ts8AAAABNyyfZA` records a fourth P1: recursive single-head Actions-history partitioning can exhaust the 60-call budget before that head's own mutation.
- PR #5 now has **49 inline material threads**, all still unresolved. The author-side P1 is additional negative evidence, not an inline PRRT.

## Exact proof chain after REVIEW-0043

- `9d66a80104e9f2fc98db362bd41f13f923313cf0` — REVIEW-0043 terminal-negative checkpoint; Bootstrap #100 / `35070576172` green.
- `38eceaab2da8320bad8a5b3929425bf1f14df54a` — first progress scheduler; #101 live probe green, self-test exposed one historical assertion mismatch.
- `bc1a665f2d38efaa313393565ad2c66f789f8a42` — per-PR sibling target resolution; #102 had 85 tests PASS and live probe green but one uncovered branch.
- `a1441f506fb1a0f42dbdf984d42e1f847e55db51` — coverage-only fallthrough regression; #103 / `35075010644`: **86/86 tests, 664 statements / 292 branches, 100%, live probe 7/60**.
- `71a1d0ff13ec25674f2d27201b261b7cbd149ae2` — REVIEW-0044 OPEN checkpoint; #104 / `35075414885`: **86/86, 664/292, 100%, live probe 7/60**.
- `379b4e00aa973f74c9bb973a1e79381f43332f0b` — REVIEW-0044 IN_PROGRESS exact head; Bootstrap #105 / `35075653630`: self-test SUCCESS and live PR #2 probe SUCCESS.
- Independent exact-head Codex review completed at `2026-09-16T08:52:16Z` and returned three new P1s.

The nominal fourteen-head regression still demonstrates early mutation at request counts **10, 18 and 26**, but REVIEW-0044 proves that nominal batching is not sufficient to establish durable starvation-free progress.

## REVIEW-0044 findings to correct

1. `PRRT_kwDOUUI5ts6i2qvx` — wall-clock modulo is not a durable scheduler cursor. Skipped/delayed/duplicated cron runs can repeatedly select the same prefix and starve another head indefinitely.
2. `PRRT_kwDOUUI5ts6i2qv4` — large but supported open-PR collections can consume the 60-call budget during global authority refresh before the first possible mutation.
3. `PRRT_kwDOUUI5ts6i2qwA` — one asynchronous shared-head rerun is not enough; the bridge must verify the resulting latest required check is non-merge-acceptable while unresolved siblings remain.
4. `PRR_kwDOUUI5ts8AAAABNyyfZA` — a single high-churn head can consume the budget inside recursive filtered Actions-history partitioning before target-job/final-thread/rerun execution.

The next correction must therefore provide schedule-independent durable progress, explicit mutation headroom before expensive reads, bounded current-incarnation target discovery, and a verified shared-head invalidation post-condition.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final behavior into `tools/governance/thread_state_poll.py`.

Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all **49** PR #5 inline material threads unresolved.
2. Correct REVIEW-0044's four P1 classes without weakening exact Checks merge-state authority, PR-bound target validation, fail-closed metadata validation, least privilege or the 60-call absolute safety guard.
3. Replace wall-clock-only rotation with schedule-independent progress semantics.
4. Avoid per-head full open-PR collection refresh or otherwise reserve enough request headroom for an actual invalidation.
5. Bound current-incarnation target discovery so one deep Actions history cannot consume the entire request budget before mutation.
6. After rerun, verify the latest shared-SHA required check becomes/remains non-merge-acceptable while an unresolved sibling exists.
7. Add adversarial regressions for skipped schedules, large open-PR collections, deep single-head history and shared-head post-rerun races.
8. Re-prove the substantive corrective head at 100% line+branch plus live read-only PR #2 contract probe.
9. Synchronize WORK-0002 / TEST-0009 / PROJECT_STATE and open a successor independent L2 review. No historical thread resolution before a clean successor.
10. WORK-0003 and WORK-0004 remain blocked.

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
10. live PR #5 exact HEAD/checks/reviews/49 threads
11. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
