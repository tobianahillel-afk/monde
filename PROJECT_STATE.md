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
- scopes canonical workflow-run discovery to each currently open head SHA and the earliest active PR-incarnation `created_at` bound for that SHA rather than traversing the workflow's lifetime history;
- accepts PR-family events `pull_request`, `pull_request_review`, and `pull_request_review_comment`;
- validates every PR-family run record before identity filtering: positive IDs, exact `status=completed`, supported terminal conclusion, structured `owner/repo` identity, timezone-aware `created_at`/`updated_at`, and `updated_at >= created_at`;
- validates Actions `workflow_runs` and `jobs` envelope `total_count` as a non-negative exact integer, requires it to stay stable across pages, rejects over-count and short/incomplete collections, and returns only when the observed cardinality equals the authoritative total;
- queries the selected run's **actual protected `MONDE / Merge Gate` job/check** through the GitHub Actions Jobs API instead of treating the aggregate workflow conclusion as branch-protection authority;
- requires exactly one protected job and validates positive exact-integer job ID, positive exact-integer `run_id`, exact `run_id` equality, positive non-Boolean `run_attempt`, exact equality with the workflow run's current positive `run_attempt`, nonempty name, `status=completed`, supported terminal conclusion, and exact `head_sha`;
- validates the current-incarnation target run's own protected `MONDE / Merge Gate` job before rerun **even when effective and target records report the same run ID**;
- treats protected-check conclusions **`success`, `neutral`, and `skipped`** as merge-acceptable stale-green states that require review-thread revalidation even when the overall workflow conclusion differs;
- validates every item from the open-PR endpoint has positive PR number, complete head identity, valid `created_at`, and exact `state=open`;
- fails closed when two simultaneously open PRs have indistinguishable `(head repository, branch, SHA)` identity;
- never treats `workflow_run.pull_requests` association cardinality as authoritative triggering-PR identity;
- queries closed PR history by head owner + branch and reconstructs lifetime-overlap windows without trusting the closed PR final SHA as complete branch history;
- excludes pre-current and overlap-window target runs, including force-push/reset history, while preserving legitimate runs created before a later overlap;
- computes effective commit-scoped gate state across fully validated **active-head-scoped** runs so shared-SHA re-greens can re-invalidate an unresolved target PR;
- validates GraphQL reviewThreads nodes/pageInfo fail-closed, including `endCursor` presence/type on terminal pages, nonempty continuation cursors, repeated cursors and bounded pagination;
- grants `actions: write` only to the trusted scheduled poll job; the exact-head GitHub contract probe remains read-only and non-destructive;
- runs exact-head self-tests when any `test_stale_green_bootstrap*.py` regression module changes;
- keeps TEST-0009's canonical `test_path` aligned with all four bootstrap regression modules.

The bridge is temporary. After PR #5 merges, PR #2's canonical `tools/governance/thread_state_poll.py` must **port/reuse this hardened active-head/run/job/run-attempt/target-job/incarnation/pagination contract** before T12 can close; the older permissive implementation on PR #2 is not made safe merely because the predecessor exists on `main`. WORK-0003 may later rationalize/remove redundant bootstrap machinery after the durable poller is independently proven.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031/0032/0033/0034/0035/0036/0037/0038 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0039 (IN_PROGRESS)`

- REVIEW-0031 is terminal on `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c`.
- REVIEW-0032 is terminal on `717777da79edca7a671c1754f32f3442da721a72`.
- REVIEW-0033 is terminal on `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff`.
- REVIEW-0034 is terminal on `45ab08c0ef4f6c4ee0ff84b8e29c74f2ab617c83` after seven new findings.
- REVIEW-0035 is terminal on `fa41ae51cf5685db02be343818fceb4946f909bf` after one new P1 finding.
- REVIEW-0036 is terminal on `2caacaea2f3e079495910fc9a91555123dfee23c` after one new P1 finding.
- REVIEW-0037 is terminal on `9a2921bce4d0fd0649f89b88854f761f18f906fe` after two new P1 findings.
- REVIEW-0038 is terminal on `af55a3f9336bcbcad4b5daf597302848233056da` after four new P1 findings.
- REVIEW-0039 is now `IN_PROGRESS`; WORK-0002, PROJECT_STATE and REVIEW-0039 enter this lifecycle checkpoint in one Git tree before any fresh Codex invocation.
- Terminal negative reviews are never reopened or rewritten.

## REVIEW-0038 findings and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNtismA` raised the PR #5 material set from 32 to **36 findings**:

- `PRRT_kwDOUUI5ts6irVvT` — canonical-workflow scoping still traversed the workflow's complete completed-run history, so the fixed twenty-page ceiling would eventually fail as history exceeded 2,000 runs;
- `PRRT_kwDOUUI5ts6irVvZ` — Actions envelope `total_count` was ignored, allowing an incomplete short page to masquerade as a complete collection and falsely prove uniqueness/absence;
- `PRRT_kwDOUUI5ts6irVvh` — target protected-job validation was skipped when independently selected effective/target records shared only the same run ID, even though attempts or other metadata could differ;
- `PRRT_kwDOUUI5ts6irVvl` — Python equality allowed coercible non-integer `job.run_id` values such as `4.0` to compare equal to integer `4`.

The correction scopes canonical workflow queries to active head SHAs plus the earliest active incarnation creation time for each SHA, verifies `total_count` cardinality on sensitive Actions collections, requires positive exact-integer `job.run_id`, and always validates the independently selected target run's protected job regardless of run-ID equality. Regressions exercise malformed/inconsistent/incomplete `total_count`, active-head query parameters, float run IDs, and same-ID/different-attempt target records.

Intermediate Bootstrap #64 / `35017533555` on `03bc96407e6a463035d588914ea1ed4ee7b7bb2d` had **48/48 functional tests and a successful real GitHub probe**, but correctly remained failed because new coverage was only 99%. Test-only descendant `5f60c915c7e1801684f13ad2421c07ff0d0f21b0` then closed the uncovered pagination branches without altering runtime behavior.

Author-side correction is not closure evidence. All **36** material threads remain unresolved.

## Exact bootstrap proof

Latest corrective executable/test candidate: **`5f60c915c7e1801684f13ad2421c07ff0d0f21b0`**.

`MONDE Stale-Green Bootstrap` run **`35017749244` / #65** is fully green on that exact head with **48/48 tests, 340/340 statements, 148/148 branches, 100% line+branch**, plus a successful real GitHub contract probe against PR #2 (`BOOTSTRAP_VALIDATE_PR=2`, `target_pr=2`, `unresolved_threads=true`).

The synchronized REVIEW-0038-terminal / REVIEW-0039-OPEN state was first published atomically at `edff2684cc77f340e50a3aa6666ec8fadcefef25`. Because that pure state-only synchronize event produced no Actions check suite, an empty same-tree commit was also insufficient under the workflow `paths` filter. A comment-only workflow diff then produced proof candidate **`e1c8dda09839bc07d691cf075b9f83ca069840d1`** without changing executable semantics.

`MONDE Stale-Green Bootstrap` run **`35018806553` / #68** is fully green on exact `e1c8dda0...`:

- Bootstrap self-test: **SUCCESS**;
- **48/48 tests**;
- **340/340 statements**;
- **148/148 branches**;
- **100% line + branch coverage**;
- Bootstrap GitHub contract probe: **SUCCESS** against live WORK-0002 PR #2;
- real probe result: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`.

The atomic REVIEW-0039-IN_PROGRESS / WORK / PROJECT_STATE descendant created after #68 must receive its own exact-head proof. The HEAD must then remain frozen throughout REVIEW-0039.

## PR #5 material thread set

All **36** material PR #5 review threads remain unresolved:

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
- `PRRT_kwDOUUI5ts6irVvT`
- `PRRT_kwDOUUI5ts6irVvZ`
- `PRRT_kwDOUUI5ts6irVvh`
- `PRRT_kwDOUUI5ts6irVvl`

Review history includes `PRR_kwDOUUI5ts8AAAABNpylnA`, `Nqb2xg`, `NqnqWQ`, `Nqx3YA`, `Nq6L4g`, `NrJroQ`, `NraMwQ`, `NrvZLg`, `Nr8aMQ`, `NsMHTw`, `NskIgg`, `NswcWg`, `NtRRtg`, and `PRR_kwDOUUI5ts8AAAABNtismA`.

## WORK-0002 / PR #2 relationship

PR #2 remains open at **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** while PR #5 is independently hardened. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #228 / run `34997568781` proves its current core after PR-numbered run-name hardening: Governance Core, CodeQL and Dependency Review are green; its live closure fails only on the 73 unresolved threads, six T12 durable identities not yet integrated, and missing trusted independent exact-head approval.

After PR #5 squash-merges to `main`, PR #2 must integrate new main through an explicit two-parent merge and port/reuse the hardened bootstrap contract into its older permissive `tools/governance/thread_state_poll.py`. Parity includes canonical workflow identity, active-head/incarnation-scoped run discovery, authoritative Actions `total_count` cardinality, complete fail-closed run/job metadata, protected-job authority, `success|neutral|skipped` merge semantics, strict integer IDs, positive/exact workflow/job `run_attempt`, target protected-job validation regardless run-ID equality, current-incarnation/overlap windows, bounded REST/GraphQL pagination and malformed-record rejection.

That integration must also synchronize the missing T12 PRRT identities for exact durable/live equality and prove the trust surface is base-preexisting, not candidate-created. Then it receives another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the atomic REVIEW-0039 `IN_PROGRESS` + WORK-0002 + PROJECT_STATE descendant exact-head.
2. If green, freeze the HEAD, update PR #5 and PR #2 handover metadata and invoke a fresh-context Codex review under REVIEW-0039.
3. Keep all **36** material PR #5 threads unresolved while REVIEW-0039 runs.
4. REVIEW-0039 must re-check all 36 prior findings and actively search active-head scoping, filtered-history limits, `total_count` snapshot/cardinality, strict identifier typing, same-ID target validation, run-attempt and shared-incarnation surfaces for bypasses.
5. A new material finding requires correction/re-proof and a successor review; do not mechanically resolve threads.
6. Only a clean independent exact-head successor review permits independent verification/resolution of historical threads and an exact-head guarded squash merge of PR #5.
7. After PR #5 merge: integrate main into PR #2, port durable-poller parity, prove T12, run fresh PR #2 L2, obtain eligible non-author exact-head APPROVED review, then consider WORK-0002 closure.
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
16. `registry/reviews/REVIEW-0039.yaml`
17. live PR #5 exact HEAD/checks/reviews/threads
18. live PR #2 exact HEAD/checks/reviews/threads
19. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
