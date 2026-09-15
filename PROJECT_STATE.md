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

## WORK-0002 default-branch bootstrap predecessor

Fresh independent L2 review of PR #2 established that its stale-green review-thread poll cannot protect PR #2 before merge because GitHub scheduled workflows execute from trusted default-branch state. **PR #5 — `fix(governance): bootstrap stale-green thread polling`** is the narrow default-branch predecessor required by WORK-0002/T12.

The temporary trusted poll now:

- queries only canonical MONDE Gate workflow ID `354465551` and verifies `.github/workflows/governance.yml`;
- accepts PR-family events `pull_request`, `pull_request_review`, and `pull_request_review_comment`;
- validates server-reported open-PR `head.repo.full_name`, `head.ref`, `head.sha`, `created_at` and positive PR number;
- fails closed when two simultaneously open PRs have indistinguishable full `(head repository, branch, SHA)` identity;
- validates canonical run head repo/ref/SHA, event, id/run-number, supported terminal conclusion, `created_at`, and timezone-aware `updated_at`;
- never treats `workflow_run.pull_requests` association cardinality as authoritative triggering-PR identity;
- queries **closed PR history scoped by server-reported head owner + branch**, then filters exact repo/ref/SHA and reconstructs lifetime-overlap windows;
- excludes target runs created before the current PR and excludes runs created inside any lifetime window where another exact same-head PR overlapped the current PR, even when that other PR later closes;
- preserves legitimate current runs created before a later duplicate PR opens rather than using a single coarse cutoff;
- still computes effective commit-scoped MONDE Gate state across historical validated runs, so a shared-SHA re-green can trigger re-invalidation of the unresolved target PR;
- rejects malformed open/closed PR metadata, invalid lifetimes, malformed workflow metadata, unknown terminal conclusions, and Boolean-as-int IDs;
- accepts GraphQL `errors` only when absent or exactly `[]`; falsey malformed `{}`, `""`, `0`, or `null` fail closed;
- bounds canonical Actions pagination and GraphQL review-thread pagination, including repeated/missing cursor failure;
- grants `actions: write` only to the trusted scheduled poll job; the PR contract probe remains read-only and non-destructive.

The bridge is temporary. After PR #2 merges, its canonical poller becomes durable; WORK-0003 may then rationalize/remove redundant bootstrap machinery.

## Stable bootstrap traceability

The bootstrap has stable non-terminal normative/test ownership and explicit review history:

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0032 (OPEN)`

- **REQ-0026 — Trusted stale-green review-state invalidation** owns the atomic material behavior.
- **TEST-0009** protects REQ-0026 without retroactively materializing previous external runs as a canonical PASS.
- **REVIEW-0031** was started before the external review, then truthfully completed `CHANGES_REQUIRED` on exact reviewed head `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c` after Codex found two new material gaps.
- **REVIEW-0032** is the fresh successor review and is currently `OPEN`; REVIEW-0031 is terminal and will never be reopened or rewritten.
- REVIEW-0032 is collision-safe with PR #2, which already uses REVIEW-0029/0030 but has no REVIEW-0031/0032.

The bootstrap workflow now includes `registry/reviews/REVIEW-*.yaml` in its PR path triggers so review lifecycle descendants receive their own exact-head self-test and live contract proof.

## REVIEW-0031 findings and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNraMwQ` of `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c` raised the PR #5 material set from 17 to **19 P1 findings**:

- `PRRT_kwDOUUI5ts6im_Sc` — `PR.created_at` alone does not distinguish overlapping exact same-head PR lifetimes; a run for the other PR may be created after the current PR opens and survive after the other PR closes.
- `PRRT_kwDOUUI5ts6im_Sh` — WORK-0002 still described REVIEW-0031 as OPEN while REVIEW-0031 and PROJECT_STATE had already moved to IN_PROGRESS.

Both are corrected author-side:

- target attribution now excludes runs created in exact same-head closed-PR lifetime-overlap windows queried from live GitHub;
- WORK-0002 now records REVIEW-0031 as terminal `COMPLETE/CHANGES_REQUIRED`, all 19 PRRT identities, its two findings, the new proof, and REVIEW-0032 as the next review.

Author-side correction is not closure evidence. All 19 threads remain unresolved pending a clean fresh review.

## Exact bootstrap proof

Latest **substantive executable** proof is exact candidate **`18a295575b50bc617bf75cf4285d60378f4b5f4e`**.

`MONDE Stale-Green Bootstrap` run **`34996707476` / #37** is fully green on that exact head:

- Bootstrap self-test: **SUCCESS**;
- **32/32 tests**;
- **268/268 statements**;
- **104/104 branches**;
- **100% line + branch coverage** over `.github/scripts/stale_green_bootstrap.py`;
- Bootstrap GitHub contract probe: **SUCCESS** against PR #2, including the new read-only closed-PR history contract.

The test suite explicitly covers the adversarial overlap case: another exact same-head PR overlaps the current PR, produces a run during the overlap, later closes, and that run has a newer `updated_at`; it may remain effective commit-scoped state but is excluded as the current PR's rerun target. The suite also proves that a legitimate current run created before a later overlap remains eligible.

Subsequent commits materializing REVIEW-0032, adding review-lifecycle workflow triggers, and synchronizing WORK/PROJECT_STATE are administrative descendants. They must still receive their own exact-head bootstrap run before REVIEW-0032 starts.

## PR #5 material thread set

All **19** material PR #5 review threads remain unresolved:

- `PRRT_kwDOUUI5ts6ijmtc`
- `PRRT_kwDOUUI5ts6ijmtj`
- `PRRT_kwDOUUI5ts6ijmtr`
- `PRRT_kwDOUUI5ts6ilBFN`
- `PRRT_kwDOUUI5ts6ilBFV`
- `PRRT_kwDOUUI5ts6ilBFb`
- `PRRT_kwDOUUI5ts6ilBFl`
- `PRRT_kwDOUUI5ts6ilcBE`
- `PRRT_kwDOUUI5ts6ilcBL`
- `PRRT_kwDOUUI5ts6ilysF`
- `PRRT_kwDOUUI5ts6ilysW`
- `PRRT_kwDOUUI5ts6ilysm`
- `PRRT_kwDOUUI5ts6imDdU`
- `PRRT_kwDOUUI5ts6imDdZ`
- `PRRT_kwDOUUI5ts6imgom`
- `PRRT_kwDOUUI5ts6imgor`
- `PRRT_kwDOUUI5ts6imgoz`
- `PRRT_kwDOUUI5ts6im_Sc`
- `PRRT_kwDOUUI5ts6im_Sh`

Review history:

- `PRR_kwDOUUI5ts8AAAABNpylnA`
- `PRR_kwDOUUI5ts8AAAABNqb2xg`
- `PRR_kwDOUUI5ts8AAAABNqnqWQ`
- `PRR_kwDOUUI5ts8AAAABNqx3YA`
- `PRR_kwDOUUI5ts8AAAABNq6L4g`
- `PRR_kwDOUUI5ts8AAAABNrJroQ`
- `PRR_kwDOUUI5ts8AAAABNraMwQ` -> REVIEW-0031 `CHANGES_REQUIRED`

## WORK-0002 / PR #2 relationship

PR #2 remains open and intentionally unchanged at **`99c7a10e5faa99128d74a39ff6886c23110247bd`** until PR #5 is independently clean. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #226 / run `34989363043` proved its deterministic/security core: 355/355 tests, 100% line+branch, mutation suites, repository validators, CodeQL and Dependency Review green; live closure deliberately fails while review state is unresolved.

After PR #5 squash-merges to `main`, PR #2 must integrate the new main through an explicit two-parent merge that:

- preserves PR #2's richer WORK/PROJECT_STATE history rather than replacing it with the bootstrap mirror;
- imports the trusted bootstrap files and REQ-0026/TEST-0009/REVIEW records from the new base;
- synchronizes the six T12 PRRT identities for exact **73/73** durable/live equality;
- deterministically proves the bootstrap trust surface is **base-preexisting**, not candidate-created.

Only then does PR #2 receive another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Obtain an exact-head bootstrap run for the current synchronized PR #5 descendant containing REVIEW-0031 terminal evidence, REVIEW-0032 OPEN, review-lifecycle workflow triggers, WORK-0002 19/19 findings, and this PROJECT_STATE.
2. If that exact-head proof is green, transition REVIEW-0032 `OPEN -> IN_PROGRESS` and synchronize WORK/PROJECT_STATE in the same lifecycle checkpoint.
3. Prove that exact REVIEW-0032-IN_PROGRESS descendant, freeze the head, update PR #5 body, and invoke a new fresh-context Codex review under REVIEW-0032.
4. Keep all **19** material PR #5 threads unresolved while REVIEW-0032 runs.
5. If REVIEW-0032 finds another material issue, record it truthfully, correct/re-prove, and create a new successor review rather than reopening a terminal review.
6. Only a clean independent exact-head review permits truthful approval-capable review completion, independent verification/resolution of the 19 threads, and an exact-head guarded squash merge of PR #5 into `main`.
7. Then integrate new `main` into PR #2 and continue T12/WORK-0002 closure as described above.
8. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/requirements/REQ-0026.yaml`
7. `registry/tests/TEST-0009.yaml`
8. `registry/reviews/REVIEW-0031.yaml`
9. `registry/reviews/REVIEW-0032.yaml`
10. live PR #5 exact HEAD/checks/reviews/threads
11. live PR #2 exact HEAD/checks/reviews/threads
12. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
