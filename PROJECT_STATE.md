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
- queries the selected run's **actual protected `MONDE / Merge Gate` job/check** through the GitHub Actions Jobs API instead of treating the aggregate workflow conclusion as branch-protection authority;
- requires exactly one protected job and validates its positive job ID, exact `run_id`, positive non-Boolean `run_attempt`, exact equality with the workflow run's current positive `run_attempt`, nonempty name, `status=completed`, supported terminal conclusion, and exact `head_sha`;
- when the effective shared-SHA run differs from the current-incarnation rerun target, validates the target run's own protected `MONDE / Merge Gate` job before any rerun;
- treats protected-check conclusions **`success`, `neutral`, and `skipped`** as merge-acceptable stale-green states that require review-thread revalidation even when the overall workflow conclusion differs;
- validates every item from the open-PR endpoint has positive PR number, complete head identity, valid `created_at`, and exact `state=open`;
- fails closed when two simultaneously open PRs have indistinguishable `(head repository, branch, SHA)` identity;
- never treats `workflow_run.pull_requests` association cardinality as authoritative triggering-PR identity;
- queries closed PR history by head owner + branch and reconstructs lifetime-overlap windows without trusting the closed PR final SHA as complete branch history;
- excludes pre-current and overlap-window target runs, including force-push/reset history, while preserving legitimate runs created before a later overlap;
- computes effective commit-scoped gate state across fully validated historical runs so shared-SHA re-greens can re-invalidate an unresolved target PR;
- validates GraphQL reviewThreads nodes/pageInfo fail-closed, including `endCursor` presence/type on terminal pages, nonempty continuation cursors, repeated cursors and bounded pagination;
- grants `actions: write` only to the trusted scheduled poll job; the exact-head GitHub contract probe remains read-only and non-destructive;
- runs exact-head self-tests when any `test_stale_green_bootstrap*.py` regression module changes;
- keeps TEST-0009's canonical `test_path` aligned with all four bootstrap regression modules.

The bridge is temporary. After PR #5 merges, PR #2's canonical `tools/governance/thread_state_poll.py` must **port/reuse this hardened run/job/run-attempt/incarnation contract** before T12 can close; the older permissive implementation on PR #2 is not made safe merely because the predecessor exists on `main`. WORK-0003 may later rationalize/remove redundant bootstrap machinery after the durable poller is independently proven.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031/0032/0033/0034/0035/0036/0037 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0038 (IN_PROGRESS)`

- REVIEW-0031 is terminal on `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c`.
- REVIEW-0032 is terminal on `717777da79edca7a671c1754f32f3442da721a72`.
- REVIEW-0033 is terminal on `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff`.
- REVIEW-0034 is terminal on `45ab08c0ef4f6c4ee0ff84b8e29c74f2ab617c83` after seven new findings.
- REVIEW-0035 is terminal on `fa41ae51cf5685db02be343818fceb4946f909bf` after one new P1 finding.
- REVIEW-0036 is terminal on `2caacaea2f3e079495910fc9a91555123dfee23c` after one new P1 finding.
- REVIEW-0037 is terminal on `9a2921bce4d0fd0649f89b88854f761f18f906fe` after two new P1 findings.
- REVIEW-0038 is now `IN_PROGRESS`; WORK-0002, PROJECT_STATE and REVIEW-0038 enter this lifecycle checkpoint in one Git tree before any fresh Codex invocation.
- Terminal negative reviews are never reopened or rewritten.

## REVIEW-0037 findings and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNtRRtg` raised the PR #5 material set from 30 to **32 findings**:

- `PRRT_kwDOUUI5ts6iquVw` — when the effective shared-SHA run belongs to a different PR than the current-incarnation target run, the bootstrap validated only the effective run's protected job and could rerun a target that no longer exposes the protected `MONDE / Merge Gate` context;
- `PRRT_kwDOUUI5ts6iquV8` — `filter=latest` alone did not prove returned jobs belonged to the workflow run's current attempt, so stale prior-attempt job state could be accepted.

The correction binds workflow and job `run_attempt` with positive non-Boolean integer validation, rejects mismatched or Boolean job attempts, and validates a distinct target run's own protected job before unresolved-thread inspection/rerun. Dedicated regressions cover prior-attempt Jobs responses, malformed/Boolean attempts, shared-SHA distinct target validation and fail-closed invalid target jobs. Run #60 deliberately exposed Python's `True == 1` edge case; the code was corrected and run #61 proves the hardened behavior. Author-side correction is not closure evidence. All **32** material threads remain unresolved.

## Exact bootstrap proof

Latest substantive executable candidate: **`9739931afea9127d1b69690930a1e957bb8ed4a4`**.

`MONDE Stale-Green Bootstrap` run **`35014658444` / #61** is fully green on that exact substantive head:

- Bootstrap self-test: **SUCCESS**;
- **45/45 tests**;
- **305/305 statements**;
- **126/126 branches**;
- **100% line + branch coverage**;
- Bootstrap GitHub contract probe: **SUCCESS** against live WORK-0002 PR #2, including the real workflow-runs, Actions Jobs, PR-history and review-thread contracts.

The atomic REVIEW-0037-IN_PROGRESS / WORK / PROJECT_STATE candidate **`9a2921bce4d0fd0649f89b88854f761f18f906fe`** passed run **`35012844593` / #59** before REVIEW-0037 opened the two new P1 findings.

The synchronized REVIEW-0037-terminal / REVIEW-0038-OPEN / WORK / PROJECT_STATE descendant **`09c94a2e9708cded60b0b7ec8f260a875d7b3a4f`** passed `MONDE Stale-Green Bootstrap` run **`35015451712` / #62** with **45/45 tests, 305/305 statements, 126/126 branches, 100% line+branch**, plus a successful live GitHub contract probe.

The atomic REVIEW-0038-IN_PROGRESS / WORK / PROJECT_STATE descendant created after #62 must receive its own exact-head proof. The HEAD must then remain frozen throughout REVIEW-0038.

## PR #5 material thread set

All **32** material PR #5 review threads remain unresolved:

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
- `PRRT_kwDOUUI5ts6ipocF`
- `PRRT_kwDOUUI5ts6iquVw`
- `PRRT_kwDOUUI5ts6iquV8`

Review history includes `PRR_kwDOUUI5ts8AAAABNpylnA`, `Nqb2xg`, `NqnqWQ`, `Nqx3YA`, `Nq6L4g`, `NrJroQ`, `NraMwQ`, `NrvZLg`, `Nr8aMQ`, `NsMHTw`, `NskIgg`, `NswcWg`, and `PRR_kwDOUUI5ts8AAAABNtRRtg`.

## WORK-0002 / PR #2 relationship

PR #2 remains open at **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** while PR #5 is independently hardened. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #228 / run `34997568781` proves its current core after PR-numbered run-name hardening: Governance Core, CodeQL and Dependency Review are green; its live closure fails only on the 73 unresolved threads, six T12 durable identities not yet integrated, and missing trusted independent exact-head approval.

Important integration finding: PR #2's current `tools/governance/thread_state_poll.py` is still the older permissive poller. It classifies only `conclusion == "success"`, silently filters malformed collection entries, does not carry the full current-incarnation/overlap contract, does not inspect the protected `MONDE / Merge Gate` job through Actions Jobs, does not bind jobs to the current `run_attempt`, and does not validate a distinct target run's protected job before rerun. After PR #5 squash-merges to `main`, PR #2 must integrate the new main through an explicit two-parent merge **and port/reuse the hardened bootstrap contract into the durable poller** while preserving richer branch-local state. That integration must also synchronize the missing T12 PRRT identities for exact durable/live equality and prove the trust surface is base-preexisting, not candidate-created. Then it receives another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the atomic REVIEW-0038 `IN_PROGRESS` + WORK-0002 + PROJECT_STATE checkpoint exact-head.
2. If green, freeze the HEAD, update PR #5 and PR #2 handover metadata and invoke a fresh-context Codex review under REVIEW-0038.
3. Keep all **32** material PR #5 threads unresolved while REVIEW-0038 runs.
4. REVIEW-0038 must re-check all 32 prior findings and actively search the run-attempt / effective-vs-target protected-job / Actions Jobs surface for new bypasses.
5. If REVIEW-0038 finds another material issue, record it truthfully, correct/re-prove, and create a successor review.
6. Only a clean independent exact-head review permits approval-capable review completion and independent verification/resolution of historical threads; do not mechanically resolve them.
7. Only after those conditions may PR #5 squash-merge to `main`, followed by PR #2 integration, durable-poller parity hardening, and WORK-0002 closure.
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
12. `registry/reviews/REVIEW-0035.yaml`
13. `registry/reviews/REVIEW-0036.yaml`
14. `registry/reviews/REVIEW-0037.yaml`
15. `registry/reviews/REVIEW-0038.yaml`
16. live PR #5 exact HEAD/checks/reviews/threads
17. live PR #2 exact HEAD/checks/reviews/threads
18. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
