# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git; live PR/check/thread truth lives in GitHub and must be rechecked before merge decisions.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

## Current blocking sublot

**SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**

PR #1 was squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`. `WORK-0001` remains `IN_REVIEW` while its post-merge A3 assurance debt is independently corrected and re-reviewed.

## Active work

- `WORK-0001` — corrective assurance work on **PR #3** / branch `chore/work-0001-assurance-closure`; it blocks truthful completion of WORK-0002.
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`. Its HEAD/check/thread state is deliberately **not duplicated here** because it is independently advancing; query GitHub live before any resume/merge decision.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is `REVIEW-0003` through `REVIEW-0017`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- `REVIEW-0007` invalidated the first TEST-0006 PASS because PROJECT_STATE, WORK-0002 and the progress matrix disagreed on the global WORK-0002 lifecycle.
- `REVIEW-0008` invalidated the second TEST-0006 PASS because the PR #3 WORK-0002 mirror referenced branch-only `read_before` files absent from the tested tree.
- `REVIEW-0009` through `REVIEW-0013` established reviewed progress reopening, the exact TEST-0004 historical migration, REQ-0006 ↔ TEST-0007 traceability, current handover alignment and WORK-level TEST-0007 declaration.
- `REVIEW-0014` found pre-v7 direct materialization of REVIEW-0004..REVIEW-0013 as `COMPLETE` and REQ-0015..REQ-0019 as `ACCEPTED`.
- `REVIEW-0015` proved REVIEW-0014's apparent lifecycle was a post-hoc replay after the external review had already completed; v7 preserves that immutable sequence only as an exact historical replay and requires truthful preauthorized import for future externally completed reviews.
- `REVIEW-0016` found a stale first handover action after TEST-0006 synchronization; the handover was corrected and made transition-stable.
- `REVIEW-0017`, fresh-context L2 on exact head `06dbb76c68287130169d41f50b2464bc4f878bb5`, found two P2/R3 defects: WORK-0001 still duplicated an older TEST-0006 execution as current, and compound REQ-0005 still combined independently fail-able DoR, DoD and verification-strategy obligations.

## REVIEW-0017 corrections

REVIEW-0017 is truthfully imported under v7:

- one-shot authorization `f6d1e84e79439d1ec2ae071171778063403c3374` existed before materialization;
- initial import commit `36b0a46e04843937b065feaf5e8e0c53c36b4664` records the externally completed `CHANGES_REQUIRED` review;
- review metadata binding is `8ba5be981c2cb45c72d02e83e8429cc091244270`;
- authorization consumption is `c9d46634409a7ad23da92ab6579fe1865a6a6986` and prevents reuse.

REQ-0005 retains its original compound statement but is now `SUPERSEDED`. Its three independently fail-able obligations are owned by:

- `REQ-0020` — Definition of Ready entry gate;
- `REQ-0021` — Definition of Done completion gate;
- `REQ-0022` — verification-strategy contract.

Git history proves all three first materialized as `PROPOSED` together in `7fb731cdf7bc745227bb062d08f385d954806f1c`, then transitioned normally to `ACCEPTED` in `246820d3bb40fa8a57eee95c70444e5729861f0b`. REQ-0005 then transitioned legally `ACCEPTED → SUPERSEDED` in `087d27adbcc42cc251bdfe186dae1bcb5f817d22` without rewriting its historical normative statement.

TEST-0005 was reopened `PASS → READY → RUNNING` and then passed on exact tree `d4202e0f21e18d9100234817b4ae56fbb38ca165`; result commit `568dde0f9fb806f82924ee67066f08039bef777a`; history binding `0359569f054e5eb1fbc00706f3d404e95929651f`. That execution proves the REQ-0005 supersession, the three atomic replacement owners, their normal lifecycle and WORK-0001 active traceability.

## Current lifecycle contract — v7

`registry/status-machines.yaml` version 7 is the canonical lifecycle source. It keeps normal repository-native semantics strict:

- review initial state `OPEN`, normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial state `PROPOSED`, normal `PROPOSED → ACCEPTED`;
- progress `DONE → IN_REVIEW` only as reviewed reopening after new adverse evidence;
- generic TEST `PLANNED → READY → RUNNING → PASS`;
- exact immutable pre-v7 review/requirement/test exceptions remain record/commit-bound and non-reusable;
- external completed reviews require one-shot authorization in a parent commit before materialization and exact later import-consumption binding.

TEST-0007 remains the current generic v7 lifecycle proof on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`, result `87668f4e64453dca4c987252a8cb46e73793950c`, history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`. REVIEW-0017 did not change the generic lifecycle contract; it exercised the same already-proven one-shot import mechanism with a new instance.

## TEST-0006 cold-resume proof

The last pre-REVIEW-0017 finalized-handover execution of TEST-0006 is PASS on exact tree `b8180dff075ea5c8328ee56d1683380576c984ba`, result `e9e41c96a826cfa8d6a1056f9795776c9d0431b4`, history binding `06dbb76c68287130169d41f50b2464bc4f878bb5`.

That execution remains valid for its exact tree but REVIEW-0017 materially changed current requirement/handover state, so one fresh TEST-0006 execution is required after this synchronized WORK/PROJECT_STATE content is finalized.

**Transition-stable rule:** the canonical current TEST-0006 execution is the latest valid execution recorded in `registry/tests/TEST-0006.yaml`; WORK-0001 and PROJECT_STATE may preserve reviewed historical baselines, but must not duplicate a volatile test-result SHA as a second source of truth. At resume, compare TEST-0006's latest exact tested tree to this synchronized handover state. If it predates the current handover semantics, rerun once; if it covers them, do not rerun merely to manufacture a newer SHA.

## WORK-0002 cross-branch boundary

The WORK-0002 record stored on PR #3 is only the globally readable handover mirror needed while WORK-0001 closes. Every path in its PR #3 `read_before` list must exist in the PR #3 tree.

To resume WORK-0002 after WORK-0001/PR #3 completes:

1. query live GitHub PR #2 state first; do not trust a duplicated historical HEAD in this document;
2. checkout `feat/work-0002-governance-ci` (or its successor after PR #3 merge);
3. integrate the new `main`/WORK-0001 v7 contract before claiming new WORK-0002 proof;
4. re-read that branch's `registry/work-items/WORK-0002.yaml` and branch-local prerequisites;
5. rerun the complete governance gate and obtain WORK-0002's own fresh independent L2.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory: never commit credentials/tokens/secrets, private or personal datasets, or user-identifying runtime data. Sensitive runtime material stays outside Git. WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Review/completion semantics

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain negative outcomes.

All prior findings remain durable evidence. No finding is closed merely because the author produced a PASS. REVIEW-0017/F-1 and F-2 remain open until a later fresh-context L2 independently verifies their correction.

## Next action

1. Finalize the synchronized WORK-0001/PROJECT_STATE state for REVIEW-0017 without marking any completion gate true.
2. Reopen TEST-0006 legally from PASS → READY, run the cold-resume/handover drill on the finalized synchronized tree, and bind any PASS to its exact tested SHA while preserving all prior executions.
3. Reply to REVIEW-0017/F-1 and F-2 with the exact requirement/test/handover evidence and leave the threads unresolved pending independent verification.
4. Freeze the resulting PR #3 head and request a new fresh-context L2 explicitly on that exact SHA.
5. If that L2 finds a material defect, record/correct/re-prove it. If it is clean, record truthful approval-capable L2 evidence, resolve only independently verified findings, finalize WORK-0001/progress/completion and merge PR #3.
6. After PR #3 merge, query live PR #2, integrate new main into it, rerun its full gate, obtain its own fresh L2, resolve only verified threads, and merge only if all gates genuinely pass.
7. Continue with WORK-0003 and then WORK-0004 in roadmap order.

## Resume instructions

Minimum manual sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/work-items/WORK-0002.yaml`
7. `registry/status-machines.yaml`
8. `registry/progress/matrix.yaml`
9. active requirement records plus superseded `REQ-0005.yaml`
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0017.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
