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
- validates every PR-family run record before identity filtering: positive IDs, exact `status=completed`, supported terminal conclusion, structured `owner/repo` identity, timezone-aware `created_at`/`updated_at`, and `updated_at >= created_at`;
- treats GitHub merge-acceptable required-check conclusions **`success`, `neutral`, and `skipped`** as stale-green states that require review-thread revalidation;
- validates every item from the open-PR endpoint has positive PR number, complete head identity, valid `created_at`, and exact `state=open`;
- fails closed when two simultaneously open PRs have indistinguishable `(head repository, branch, SHA)` identity;
- never treats `workflow_run.pull_requests` association cardinality as authoritative triggering-PR identity;
- queries closed PR history by head owner + branch and reconstructs lifetime-overlap windows without trusting the closed PR final SHA as complete branch history;
- excludes pre-current and overlap-window target runs, including force-push/reset history, while preserving legitimate runs created before a later overlap;
- computes effective commit-scoped gate state across fully validated historical runs so shared-SHA re-greens can re-invalidate an unresolved target PR;
- validates GraphQL reviewThreads nodes/pageInfo fail-closed, including `endCursor` presence/type on terminal pages, nonempty continuation cursors, repeated cursors and bounded pagination;
- grants `actions: write` only to the trusted scheduled poll job; the exact-head GitHub contract probe remains read-only and non-destructive;
- runs exact-head self-tests when any `test_stale_green_bootstrap*.py` regression module changes;
- keeps TEST-0009's canonical `test_path` aligned with all **four** bootstrap regression modules.

The bridge is temporary. After PR #2 merges, its canonical poller becomes durable; WORK-0003 may then rationalize/remove redundant bootstrap machinery.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031/0032/0033/0034/0035 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0036 (IN_PROGRESS)`

- REVIEW-0031 is terminal on `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c`.
- REVIEW-0032 is terminal on `717777da79edca7a671c1754f32f3442da721a72`.
- REVIEW-0033 is terminal on `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff`.
- REVIEW-0034 is terminal on `45ab08c0ef4f6c4ee0ff84b8e29c74f2ab617c83` after seven new findings.
- REVIEW-0035 is terminal on `fa41ae51cf5685db02be343818fceb4946f909bf` after one new P1 finding.
- REVIEW-0036 is the fresh successor and is now `IN_PROGRESS`; WORK-0002, PROJECT_STATE and REVIEW-0036 enter this lifecycle checkpoint in one Git tree before any new Codex invocation.
- Terminal negative reviews are never reopened or rewritten.

## REVIEW-0035 finding and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNskIgg` raised the PR #5 material set from 28 to **29 findings**:

- `PRRT_kwDOUUI5ts6ipPZM` — GitHub treats required-check conclusions `success`, `neutral` and `skipped` as merge-acceptable, but the bootstrap revalidated only literal `success`.

The correction introduces one explicit `MERGE_ACCEPTABLE_CONCLUSIONS = {"success", "neutral", "skipped"}` contract and uses it for stale-green thread inspection. TEST-0009 now routes the dedicated `test_stale_green_bootstrap_merge_acceptable.py` regression module. The finding is corrected author-side on `7ab6a3458544a4f27be217e16ecdbff1933f61d1`; author-side correction is not closure evidence. All **29** material threads remain unresolved.

## Exact bootstrap proof

Latest substantive executable candidate: **`7ab6a3458544a4f27be217e16ecdbff1933f61d1`**.

`MONDE Stale-Green Bootstrap` run **`35007168427` / #54** is fully green on that exact head:

- Bootstrap self-test: **SUCCESS**;
- **40/40 tests**;
- **280/280 statements**;
- **112/112 branches**;
- **100% line + branch coverage**;
- Bootstrap GitHub contract probe: **SUCCESS** against live WORK-0002 PR #2.

The preceding atomic REVIEW-0035-IN_PROGRESS / WORK / PROJECT_STATE candidate **`fa41ae51cf5685db02be343818fceb4946f909bf`** passed run **`35006183807` / #53** before REVIEW-0035 found the merge-acceptable-conclusion gap.

The synchronized REVIEW-0035-terminal / REVIEW-0036-OPEN / WORK / PROJECT_STATE descendant **`08cd94e9e1507ddb15468b41928d876257535846`** passed `MONDE Stale-Green Bootstrap` run **`35007667970` / #55** with self-test and live GitHub contract probe **SUCCESS**.

The atomic REVIEW-0036-IN_PROGRESS / WORK / PROJECT_STATE descendant created after run #55 must receive its own exact-head proof before Codex is invoked. The HEAD must then remain frozen during the review.

## PR #5 material thread set

All **29** material PR #5 review threads remain unresolved:

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
- `PRRT_kwDOUUI5ts6iofZr`
- `PRRT_kwDOUUI5ts6iofZu`
- `PRRT_kwDOUUI5ts6iofZ1`
- `PRRT_kwDOUUI5ts6iofZ_`
- `PRRT_kwDOUUI5ts6iofaG`
- `PRRT_kwDOUUI5ts6iofaK`
- `PRRT_kwDOUUI5ts6iofaP`
- `PRRT_kwDOUUI5ts6ipPZM`

Review history includes `PRR_kwDOUUI5ts8AAAABNpylnA`, `Nqb2xg`, `NqnqWQ`, `Nqx3YA`, `Nq6L4g`, `NrJroQ`, `NraMwQ`, `NrvZLg`, `Nr8aMQ`, `NsMHTw`, and `PRR_kwDOUUI5ts8AAAABNskIgg`.

## WORK-0002 / PR #2 relationship

PR #2 remains open at **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** while PR #5 is independently hardened. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #228 / run `34997568781` proves its current core after PR-numbered run-name hardening: Governance Core, CodeQL and Dependency Review are green; its live closure fails only on the 73 unresolved threads, six T12 durable identities not yet integrated, and missing trusted independent exact-head approval.

After PR #5 squash-merges to `main`, PR #2 must integrate the new main through an explicit two-parent merge that preserves richer branch-local state, imports the trusted bootstrap files and records, synchronizes the six T12 PRRT identities for exact **73/73** durable/live equality, and proves the bootstrap trust surface is **base-preexisting**, not candidate-created. Then it receives another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the atomic REVIEW-0036 `IN_PROGRESS` + WORK-0002 + PROJECT_STATE checkpoint exact-head.
2. If green, freeze the HEAD, update PR #5 and PR #2 handover metadata and invoke a fresh-context Codex review under REVIEW-0036.
3. Keep all **29** material PR #5 threads unresolved while REVIEW-0036 runs.
4. If REVIEW-0036 finds another material issue, record it truthfully, correct/re-prove, and create a successor review.
5. Only a clean independent exact-head review permits approval-capable review completion and independent verification/resolution of the 29 historical threads; do not mechanically resolve them.
6. Only after those conditions may PR #5 squash-merge to `main`, followed by PR #2 integration and WORK-0002 closure.
7. WORK-0003 and WORK-0004 remain blocked.

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
12. `registry/reviews/REVIEW-0035.yaml`
13. `registry/reviews/REVIEW-0036.yaml`
14. live PR #5 exact HEAD/checks/reviews/threads
15. live PR #2 exact HEAD/checks/reviews/threads
16. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
