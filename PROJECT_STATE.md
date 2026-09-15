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
- validates every canonical PR-family run's required metadata, including `created_at`, **before** current-PR identity filtering, so the effective shared-SHA pass and current-target pass use one fail-closed trust envelope;
- validates server-reported open-PR `head.repo.full_name`, `head.ref`, `head.sha`, `created_at` and positive PR number;
- fails closed when two simultaneously open PRs have indistinguishable full `(head repository, branch, SHA)` identity;
- validates canonical run head repo/ref/SHA, event, id/run-number, supported terminal conclusion, timezone-aware `created_at` and `updated_at`;
- never treats `workflow_run.pull_requests` association cardinality as authoritative triggering-PR identity;
- queries **closed PR history scoped by server-reported head owner + branch** and reconstructs lifetime-overlap windows without trusting the closed PR final `head.sha` as the complete history of that branch;
- excludes target runs created before the current PR and runs created inside any same-repository/same-branch overlap window, including branch reset/force-push history;
- preserves legitimate current runs created before a later duplicate PR opens rather than using a coarse cutoff;
- still computes effective commit-scoped MONDE Gate state across historical validated runs, so a shared-SHA re-green can trigger re-invalidation of the unresolved target PR;
- rejects malformed open/closed PR metadata, invalid lifetimes, malformed workflow metadata, unknown terminal conclusions, and Boolean-as-int IDs;
- accepts GraphQL `errors` only when absent or exactly `[]`; falsey malformed `{}`, `""`, `0`, or `null` fail closed;
- bounds canonical Actions pagination and GraphQL review-thread pagination, including repeated/missing cursor failure;
- grants `actions: write` only to the trusted scheduled poll job; the PR contract probe remains read-only and non-destructive.

The bridge is temporary. After PR #2 merges, its canonical poller becomes durable; WORK-0003 may then rationalize/remove redundant bootstrap machinery.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0032 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0033 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0034 (OPEN)`

- **REVIEW-0031** is terminal `CHANGES_REQUIRED` on exact reviewed head `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c`.
- **REVIEW-0032** is terminal `CHANGES_REQUIRED` on exact reviewed head `717777da79edca7a671c1754f32f3442da721a72`.
- **REVIEW-0033** is terminal `CHANGES_REQUIRED` on exact reviewed head `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff` after fresh review exposed run-`created_at` validation order.
- **REVIEW-0034** is the fresh successor review and is `OPEN`; it must not transition to `IN_PROGRESS` until this synchronized lifecycle descendant has exact-head bootstrap proof.
- REVIEW-0031/0032/0033 are durable negative evidence and are never reopened or rewritten.

The bootstrap workflow includes `registry/reviews/REVIEW-*.yaml` in its PR path triggers so review lifecycle descendants receive exact-head self-test and live contract proof.

## REVIEW-0033 finding and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNr8aMQ` of `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff` raised the PR #5 material set from 20 to **21 P1 findings**:

- `PRRT_kwDOUUI5ts6in_r4` — `created_at` was validated only after a canonical run matched `current_prs`. A malformed run from another branch sharing the same SHA could therefore influence the unfiltered effective shared-SHA state while the filtered pass silently skipped it, bypassing unresolved-thread invalidation.

The correction validates `_run_created_at(run)` for **every PR-family canonical run before identity filtering** and reuses that already-validated timestamp in current-incarnation filtering. New regressions cover malformed, missing and timezone-naive `created_at` on a nonmatching same-SHA branch and require both filtered and unfiltered selection to fail closed.

Author-side correction is not closure evidence. All **21** material threads remain unresolved pending a clean fresh review.

## Exact bootstrap proof

The latest substantive executable candidate is **`1c0093b84504e23cb47e5b1b7730d34e141c8fb5`**.

`MONDE Stale-Green Bootstrap` run **`35000892195` / #48** is fully green on that exact head:

- Bootstrap self-test: **SUCCESS**;
- **35/35 tests**;
- **269/269 statements**;
- **104/104 branches**;
- **100% line + branch coverage** over `.github/scripts/stale_green_bootstrap.py`;
- Bootstrap GitHub contract probe: **SUCCESS** against live WORK-0002 PR #2.

Earlier lifecycle/executable proofs remain historical:
- `23bf9372...` / run #44 `34999284396` proved branch-reset correction;
- `de5cf707...` / run #45 `34999773505` proved REVIEW-0032-terminal / REVIEW-0033-OPEN synchronization;
- `55d471ac...` / run #46 `35000090466` proved the exact REVIEW-0033-IN_PROGRESS candidate subsequently reviewed by Codex.

The synchronized REVIEW-0033-terminal / REVIEW-0034-OPEN / WORK / PROJECT_STATE descendant created after run #48 must receive its own exact-head bootstrap proof before REVIEW-0034 starts.

## PR #5 material thread set

All **21** material PR #5 review threads remain unresolved:

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
- `PRRT_kwDOUUI5ts6inm7v`
- `PRRT_kwDOUUI5ts6in_r4`

Review history:
- `PRR_kwDOUUI5ts8AAAABNpylnA`
- `PRR_kwDOUUI5ts8AAAABNqb2xg`
- `PRR_kwDOUUI5ts8AAAABNqnqWQ`
- `PRR_kwDOUUI5ts8AAAABNqx3YA`
- `PRR_kwDOUUI5ts8AAAABNq6L4g`
- `PRR_kwDOUUI5ts8AAAABNrJroQ`
- `PRR_kwDOUUI5ts8AAAABNraMwQ` -> REVIEW-0031 `CHANGES_REQUIRED`
- `PRR_kwDOUUI5ts8AAAABNrvZLg` -> REVIEW-0032 `CHANGES_REQUIRED`
- `PRR_kwDOUUI5ts8AAAABNr8aMQ` -> REVIEW-0033 `CHANGES_REQUIRED`

## WORK-0002 / PR #2 relationship

PR #2 remains open at **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** while PR #5 is independently hardened. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #228 / run `34997568781` proves its current core after PR-numbered run-name hardening: Governance Core, CodeQL and Dependency Review are green; its live closure fails only on the 73 unresolved threads, six T12 durable identities not yet integrated, and missing trusted independent exact-head approval.

After PR #5 squash-merges to `main`, PR #2 must integrate the new main through an explicit two-parent merge that preserves richer branch-local state, imports the trusted bootstrap files and records, synchronizes the six T12 PRRT identities for exact **73/73** durable/live equality, and proves the bootstrap trust surface is **base-preexisting**, not candidate-created.

Only then does PR #2 receive another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the synchronized REVIEW-0033 `COMPLETE/CHANGES_REQUIRED` + REVIEW-0034 `OPEN` + WORK-0002 + PROJECT_STATE checkpoint with exact-head bootstrap self-test and live PR #2 contract probe.
2. If green, transition REVIEW-0034 `OPEN -> IN_PROGRESS` and synchronize WORK/PROJECT_STATE in one Git-tree checkpoint.
3. Prove that exact REVIEW-0034-IN_PROGRESS descendant, freeze the HEAD, update PR #5 body, and invoke a fresh-context Codex review.
4. Keep all **21** material PR #5 threads unresolved while REVIEW-0034 runs.
5. If REVIEW-0034 finds another material issue, record it truthfully, correct/re-prove, and create a successor review rather than reopening a terminal review.
6. Only a clean independent exact-head review permits truthful approval-capable review completion, independent verification/resolution of the 21 threads, and an exact-head guarded squash merge of PR #5 into `main`.
7. Then integrate new `main` into PR #2 and continue T12/WORK-0002 closure.
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
10. `registry/reviews/REVIEW-0033.yaml`
11. `registry/reviews/REVIEW-0034.yaml`
12. live PR #5 exact HEAD/checks/reviews/threads
13. live PR #2 exact HEAD/checks/reviews/threads
14. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
