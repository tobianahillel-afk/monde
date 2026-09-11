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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`. Its volatile HEAD/check/thread state is deliberately not duplicated here; query GitHub live before resume/merge decisions.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is now `REVIEW-0003` through `REVIEW-0018`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- REVIEW-0007/0008 forced coherent global lifecycle and explicit cross-branch prerequisite boundaries.
- REVIEW-0009..0013 established reviewed progress reopening, exact historical TEST migration, current lifecycle traceability and transition-stable handover/work-level proof declarations.
- REVIEW-0014/0015 established exact historical import/replay boundaries and the v7 one-shot preauthorized external-review import mechanism.
- REVIEW-0016 removed stale completed actions from the cold-resume handover.
- REVIEW-0017 on `06dbb76c68287130169d41f50b2464bc4f878bb5` found stale duplicated TEST-0006 currentness plus compound REQ-0005; those defects were structurally corrected and re-proven.
- REVIEW-0018 on exact frozen head `8f0aea5b9c1cd9387b59da40ff2d08a8a975d1a1` found one P1/R2 defect: REQ-0020/0021/0022 had been transitioned to `ACCEPTED` before an approval-capable independent review and cold-read could inspect those new records.

## REVIEW-0018 provenance and correction

REVIEW-0018 is truthfully imported under v7:

- one-shot authorization `c90756dd28ad5c0029768a1de41e87194a956ab5` existed before materialization;
- initial import `85c3b09507d0a4dce48f992eaeee142f82bd768f` records the externally completed `CHANGES_REQUIRED` review;
- review binding is `b56d0661d343de358844b817e2fec02b4ea39d52`;
- authorization consumption is `8c10f6fa599dbff29285f02f3363778e0e36b319`.

The acceptance error is preserved, not rewritten:

- REQ-0020/0021/0022 remain inspectable as the prematurely accepted atomic records and transitioned legally `ACCEPTED → SUPERSEDED` together in `9ca6b975e7abef9eadf86573f2c9e1cb07b89e3d`.
- Replacement REQ-0023 (DoR), REQ-0024 (DoD) and REQ-0025 (verification strategy) first materialized together as **PROPOSED** in `772616269581f622605416b2e34f6d4e270241df`.
- WORK-0001 active ownership routes to REQ-0023/0024/0025, not to superseded REQ-0005 or prematurely accepted REQ-0020/0021/0022.
- REQ-0023/0024/0025 remain PROPOSED pending independent acceptance review; no author-produced test can transition them to ACCEPTED.

This explicitly separates two gates that are both required: a lifecycle-valid `PROPOSED → ACCEPTED` transition and the substantive Review Council/cold-read evidence required **before** that transition.

## Current lifecycle contract — v7

`registry/status-machines.yaml` version 7 remains canonical. Generic semantics are unchanged:

- review initial `OPEN`, normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial `PROPOSED`, normal `PROPOSED → ACCEPTED`;
- requirement `ACCEPTED → SUPERSEDED` preserves immutable prior mistakes without rollback;
- progress `DONE → IN_REVIEW` only as reviewed reopening after new adverse evidence;
- generic TEST `PLANNED → READY → RUNNING → PASS`, with PASS reusable only through legal reopen;
- external completed reviews require one-shot authorization in a parent commit before materialization and exact later import-consumption binding.

TEST-0007 remains the current generic v7 lifecycle proof on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`, result `87668f4e64453dca4c987252a8cb46e73793950c`, history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`. REVIEW-0018 did not modify generic lifecycle semantics.

## Pre-acceptance proof — complete

TEST-0005 supplied the required exact-SHA pre-acceptance cold-read while REQ-0023/0024/0025 remained PROPOSED:

- exact tested tree `efd48467352c0ce4ec344ebe410fd9e98d938721`;
- PASS result commit `ce962ec2ad199dd914ee4e4a66ec4e110fbfbe`;
- history binding `79a95e7cda3b62b68208e333ddc1593c510167f7`.

That execution verifies atomic ownership, replacement/supersession traceability, proposal status, Review Council/cold-read sequencing and the prohibition on pre-review acceptance. REVIEW-0018/F-1 remains OPEN and the proposed requirements remain non-Accepted; this author-produced PASS is evidence for the next independent review, not approval itself.

## TEST-0006 cold-resume proof routing

TEST-0006 has a REVIEW-0018-era PASS baseline on exact tree `19b1854f4438800637237a90a3e9e3e90b398548`, result `9e55ba41f2f057292d6da86f3fc3f9d2892be701`, history binding `60920aac4ed9f345e9e7e35d4398e6162f9a8a82`.

**Transition-stable rule:** the canonical current execution of each TEST lives in its TEST record. At resume, inspect TEST-0006's latest valid exact tested tree. If that execution covers the current synchronized REVIEW-0018 + pre-acceptance handover semantics, do not rerun it merely to obtain a newer SHA; proceed to the independent review gate. If a later substantive handover change makes the latest execution predate or no longer cover the current semantics, reopen/rerun legally once. WORK-0001 and PROJECT_STATE preserve reviewed baselines but do not become a second mutable TEST-result registry.

Likewise, live PR #2 HEAD/check/thread truth remains external and is queried from GitHub rather than copied into canonical handover prose.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is the globally readable handover mirror while WORK-0001 closes. Every path in its PR #3 `read_before` list must resolve in the PR #3 tree. Branch-only prerequisites become mandatory only after checkout of `feat/work-0002-governance-ci` (or its successor after integration).

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private or personal datasets, or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles branch/ruleset/required-check/merge/security hardening while preserving public visibility.

## Review/completion semantics

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to exact artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain durable negative outcomes.

No finding is closed because the author produced a test PASS. REVIEW-0018/F-1 remains open pending a later fresh-context approval-capable L2 that reviews the proposed replacement requirements and accumulated PR.

## Next action

1. Inspect TEST-0006's latest valid exact-SHA execution. If it covers this synchronized handover, do not repeat it; reply to REVIEW-0018/F-1 with the exact TEST-0005/TEST-0006 evidence and continue to fresh L2. If it does not cover this handover because substantive state changed after its tested tree, reopen/rerun it legally before review.
2. Leave REVIEW-0018/F-1 unresolved, freeze the qualifying PR #3 HEAD, and request fresh-context L2 explicitly on that exact SHA. The reviewer must inspect REQ-0023/0024/0025 while they are still PROPOSED, verify REVIEW-0018/F-1, and review the accumulated PR for any material P0/P1/P2 defect.
3. If the L2 finds a defect, record/correct/re-prove it. If clean/approval-capable, record its v7 provenance first, then transition REQ-0023/0024/0025 to ACCEPTED as a reviewed administrative state change with no substantive text mutation, close only independently verified findings, finalize WORK-0001/progress/completion and merge PR #3.
4. After PR #3 merge, query live PR #2, integrate new main, rerun its full gate, obtain its own fresh L2, and merge only if all gates genuinely pass.
5. Continue with WORK-0003 and then WORK-0004 in roadmap order.

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
9. active PROPOSED `REQ-0023.yaml` through `REQ-0025.yaml`, plus superseded `REQ-0005.yaml` and `REQ-0020.yaml` through `REQ-0022.yaml`
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0018.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
