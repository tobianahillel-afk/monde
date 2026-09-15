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

The temporary trusted poll now follows a positive-authority split:

- effective merge state is read directly from the exact latest GitHub Actions-owned **`MONDE / Merge Gate`** check for the exact head SHA through the Checks API; workflow-run history is no longer reconstructed as merge-state authority;
- canonical Actions workflow history is used only to discover the rerun target that MONDE is explicitly allowed to rerun for the current PR incarnation;
- target discovery queries only canonical MONDE Gate workflow ID `354465551` and verifies `.github/workflows/governance.yml`;
- `workflow_id`, PR/run/job/check identifiers and attempts used as trust bindings must be exact positive non-Boolean integers where applicable;
- filtered workflow-run searches are partitioned into closed, non-overlapping second ranges when GitHub's filtered-search ceiling is reached; one saturated timestamp second fails closed;
- accepted filtered windows require exact unique run IDs and two identical snapshots before use, so stable cardinality alone cannot hide duplicate/omitted membership;
- every PR-family run record used for rerun-target selection validates exact `status=completed`, supported terminal conclusion, structured `owner/repo` identity, timezone-aware `created_at`/`updated_at`, and `updated_at >= created_at`;
- PR-family events remain `pull_request`, `pull_request_review`, and `pull_request_review_comment`;
- the current-incarnation target run's own protected `MONDE / Merge Gate` job is validated before rerun, including exact run/head/current-attempt binding;
- required-job collections use typed authoritative `total_count`, exact unique record identities and fail closed on malformed, inconsistent, over-count, incomplete or duplicate pagination;
- protected-check conclusions **`success`, `neutral`, and `skipped`** are merge-acceptable stale-green states requiring review-thread revalidation;
- every open-PR result validates positive PR number, complete head identity, valid `created_at`, and exact `state=open`; indistinguishable simultaneously-open `(repo, branch, SHA)` identities fail closed;
- `workflow_run.pull_requests` association cardinality remains non-authoritative triggering-PR metadata;
- closed PR history is queried by owner+branch in `updated desc` order and is bounded to lifetimes capable of overlapping the earliest active incarnation instead of traversing unbounded branch history;
- lifetime-overlap windows do not trust a closed PR's final SHA snapshot, exclude ambiguous prior/overlapping-incarnation target runs, and preserve legitimate current runs created before a later overlap;
- check state is cached once per SHA and target job validation is cached by exact run/attempt inside one poll;
- the schedule is every **10 minutes**, reducing API pressure while retaining the five-minute job timeout;
- GraphQL reviewThreads nodes/pageInfo fail closed, including terminal/continuing `endCursor`, repeated cursors and bounded pagination;
- the live contract probe has least-privilege read permissions including `checks: read`; only the trusted scheduled poll receives `actions: write`;
- exact-head self-tests run for the complete `test_stale_green_bootstrap*.py` regression family; TEST-0009 lists all five current modules.

The bridge is temporary. After PR #5 merges, PR #2's canonical `tools/governance/thread_state_poll.py` must **port/reuse this hardened positive-authority Checks + current-incarnation rerun-target contract** before T12 can close; predecessor existence alone does not make PR #2's older permissive implementation safe. WORK-0003 may later rationalize/remove redundant bootstrap machinery after the durable poller is independently proven.

## Stable bootstrap traceability

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031/0032/0033/0034/0035/0036/0037/0038/0039 (COMPLETE/CHANGES_REQUIRED) + REVIEW-0040 (OPEN)`

- REVIEW-0031 is terminal on `702d5ee33e8184e5d3186e8d0cb2911e0d79ef9c`.
- REVIEW-0032 is terminal on `717777da79edca7a671c1754f32f3442da721a72`.
- REVIEW-0033 is terminal on `55d471ac5d9b09f37aa93c6fce342a6a60a2b6ff`.
- REVIEW-0034 is terminal on `45ab08c0ef4f6c4ee0ff84b8e29c74f2ab617c83` after seven new findings.
- REVIEW-0035 is terminal on `fa41ae51cf5685db02be343818fceb4946f909bf` after one new P1 finding.
- REVIEW-0036 is terminal on `2caacaea2f3e079495910fc9a91555123dfee23c` after one new P1 finding.
- REVIEW-0037 is terminal on `9a2921bce4d0fd0649f89b88854f761f18f906fe` after two new P1 findings.
- REVIEW-0038 is terminal on `af55a3f9336bcbcad4b5daf597302848233056da` after four new P1 findings.
- REVIEW-0039 is terminal on `402519d73d55a2b45507b23e319c8fb42ad440f1`; independent review `PRR_kwDOUUI5ts8AAAABNuOmoQ` added six new P1 findings.
- REVIEW-0040 is `OPEN`; it must not be moved to `IN_PROGRESS` until this synchronized OPEN checkpoint has an exact-head bootstrap proof.
- Terminal negative reviews are never reopened or rewritten.

## REVIEW-0038 findings and correction

Fresh exact-head review `PRR_kwDOUUI5ts8AAAABNtismA` raised the PR #5 material set from 32 to **36 findings**:

- `PRRT_kwDOUUI5ts6irVvT` — canonical-workflow scoping still traversed complete workflow history and would eventually hit the local page ceiling;
- `PRRT_kwDOUUI5ts6irVvZ` — Actions envelope `total_count` was ignored, allowing incomplete collections to masquerade as complete;
- `PRRT_kwDOUUI5ts6irVvh` — target protected-job validation was skipped when independently selected records shared only the same run ID;
- `PRRT_kwDOUUI5ts6irVvl` — coercible non-integer `job.run_id` values could compare equal to the integer run ID.

The REVIEW-0038 correction introduced active-head/incarnation scoping, typed authoritative `total_count`, strict `job.run_id`, and unconditional target-job validation. Corrective candidate `5f60c915c7e1801684f13ad2421c07ff0d0f21b0` passed Bootstrap #65 / `35017749244` with **48/48 tests, 340/340 statements, 148/148 branches, 100% line+branch** and a successful live PR #2 probe. The REVIEW-0039 lifecycle descendant `402519d...` later passed Bootstrap #69 / `35019243044` with the same proof before independent REVIEW-0039.

## REVIEW-0039 findings and correction

Independent REVIEW-0039 `PRR_kwDOUUI5ts8AAAABNuOmoQ` on exact `402519d73d55a2b45507b23e319c8fb42ad440f1` raised the material PR #5 set from 36 to **42 findings**:

- `PRRT_kwDOUUI5ts6is6A-` — pre-incarnation runs rerun later could be omitted by the created-time filter even though their newest check became effective merge state;
- `PRRT_kwDOUUI5ts6is6BA` — duplicate rows across offset-pagination pages could satisfy stable `total_count` while omitting another record;
- `PRRT_kwDOUUI5ts6is6BF` — GitHub filtered workflow-run searches cap results at 1,000 per search;
- `PRRT_kwDOUUI5ts6is6BL` — `workflow_id` accepted coercible non-integer values such as `354465551.0`;
- `PRRT_kwDOUUI5ts6is6BR` — closed-PR history was unbounded and could eventually exhaust local pagination before active PR inspection;
- `PRRT_kwDOUUI5ts6is6BX` — the five-minute per-head/per-PR request pattern could exhaust the repository `GITHUB_TOKEN` budget under moderate concurrency.

The correction deliberately avoids another blacklist layer. Effective merge state now comes from the exact required Checks record GitHub evaluates; canonical Actions history is only a positively-bound rerun-target source. Filtered history partitions below the server ceiling and requires stable unique snapshots, closed history stops once it is older than the active-incarnation lower bound, `workflow_id` uses strict integer typing, one-poll caches remove duplicate check/job lookups, and schedule cadence is ten minutes.

## Exact bootstrap proof

Latest corrective executable/test candidate: **`9f2fccc254937ca1b1e28be26bcbad60f85308e0`**.

`MONDE Stale-Green Bootstrap` run **`35026563188` / #80** is fully green on that exact head:

- Bootstrap self-test: **SUCCESS**;
- **63/63 tests**;
- **450/450 statements**;
- **200/200 branches**;
- **100% line + branch coverage**;
- Bootstrap GitHub contract probe: **SUCCESS** against live WORK-0002 PR #2;
- probe token permissions include `Actions: read`, `Checks: read`, `Contents: read`, `PullRequests: read`;
- real probe result: `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`.

This proof establishes the corrected executable/test candidate only. The synchronized REVIEW-0039-terminal / REVIEW-0040-OPEN / WORK / PROJECT_STATE checkpoint created after #80 must receive its own exact-head proof before REVIEW-0040 can move to `IN_PROGRESS`.

## PR #5 material thread set

All **42** material PR #5 review threads remain unresolved:

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
- `PRRT_kwDOUUI5ts6is6A-`
- `PRRT_kwDOUUI5ts6is6BA`
- `PRRT_kwDOUUI5ts6is6BF`
- `PRRT_kwDOUUI5ts6is6BL`
- `PRRT_kwDOUUI5ts6is6BR`
- `PRRT_kwDOUUI5ts6is6BX`

Review history includes `PRR_kwDOUUI5ts8AAAABNpylnA`, `Nqb2xg`, `NqnqWQ`, `Nqx3YA`, `Nq6L4g`, `NrJroQ`, `NraMwQ`, `NrvZLg`, `Nr8aMQ`, `NsMHTw`, `NskIgg`, `NswcWg`, `NtRRtg`, `NtismA`, and `NuOmoQ`.

## WORK-0002 / PR #2 relationship

PR #2 remains open at **`4046e03b1e00a2051d29ccd6dcf5f0af7426259a`** while PR #5 is independently hardened. Its richer branch-local WORK-0002 state remains authoritative for T7-T12 implementation history.

PR #2 still has **73 unresolved material threads**. Gate #228 / run `34997568781` proves its current core after PR-numbered run-name hardening: Governance Core, CodeQL and Dependency Review are green; its live closure fails on unresolved threads, T12 durable identities/integration, and missing trusted independent exact-head approval.

After PR #5 squash-merges to `main`, PR #2 must integrate new main through an explicit two-parent merge and port/reuse the positive-authority contract into its older permissive `tools/governance/thread_state_poll.py`: exact GitHub Actions-owned required check state, canonical/current-incarnation rerun-target discovery, filtered-window server-cap handling and snapshot identity/stability, bounded closed-history overlap detection, strict IDs/attempts, target protected-job validation, merge-acceptable `success|neutral|skipped`, one-poll caches, bounded API cost and malformed-record rejection.

That integration must synchronize the missing T12 PRRT identities for exact durable/live equality and prove the trust surface is base-preexisting, not candidate-created. Then it receives another full MONDE Gate, fresh-context L2, trusted exact-head non-author APPROVED review, independent thread closure and merge decision.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the synchronized REVIEW-0039 `COMPLETE/CHANGES_REQUIRED` + REVIEW-0040 `OPEN` + WORK-0002 + PROJECT_STATE checkpoint exact-head.
2. Keep all **42** material PR #5 threads unresolved.
3. If the OPEN checkpoint is green, atomically transition REVIEW-0040 / WORK-0002 / PROJECT_STATE to `IN_PROGRESS`, then prove that exact descendant too.
4. Only after the `IN_PROGRESS` descendant is green, invoke fresh-context Codex REVIEW-0040 on that exact frozen HEAD.
5. REVIEW-0040 must re-check all 42 prior findings and actively red-team direct Checks authority, filtered-search partitions/snapshots, current-incarnation target binding, bounded closed history, strict identifiers, caching/rate budget, permissions and traceability.
6. Any new material finding requires correction/re-proof and a successor review; do not mechanically resolve threads.
7. Only a clean independent exact-head successor review permits independent verification/resolution of historical threads and an exact-head guarded squash merge of PR #5.
8. After PR #5 merge: integrate main into PR #2, port durable-poller parity, prove T12, run fresh PR #2 L2, obtain eligible non-author exact-head APPROVED review, then consider WORK-0002 closure.
9. WORK-0003 and WORK-0004 remain blocked.

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
17. `registry/reviews/REVIEW-0040.yaml`
18. live PR #5 exact HEAD/checks/reviews/threads
19. live PR #2 exact HEAD/checks/reviews/threads
20. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
