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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`. Its volatile HEAD/check/thread state and branch-local review/test proof graph are deliberately not duplicated here; query GitHub and checkout that branch before traversing WORK-0002 implementation evidence.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is now `REVIEW-0003` through `REVIEW-0020`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- REVIEW-0007/0008 forced coherent global lifecycle and explicit cross-branch prerequisite boundaries.
- REVIEW-0009..0013 established reviewed progress reopening, exact historical TEST migration, current lifecycle traceability and transition-stable handover/work-level proof declarations.
- REVIEW-0014/0015 established exact historical import/replay boundaries and the v7 one-shot preauthorized external-review import mechanism.
- REVIEW-0016 removed stale completed actions from the cold-resume handover.
- REVIEW-0017 on `06dbb76c68287130169d41f50b2464bc4f878bb5` found stale duplicated TEST-0006 currentness plus compound REQ-0005; those defects were structurally corrected and re-proven.
- REVIEW-0018 on `8f0aea5b9c1cd9387b59da40ff2d08a8a975d1a1` found premature acceptance of REQ-0020/0021/0022 before approval-capable independent review; those records were preserved as superseded history and replacement REQ-0023/0024/0025 remain PROPOSED.
- REVIEW-0019 on exact frozen head `13f6b315df8d3734e90b212748f730e0d921c33c` found malformed WORK-0001 YAML and a truncated copied TEST-0005 result SHA; both were corrected and re-proven.
- REVIEW-0020 on exact frozen head `13b977bf5e821bbd32464a90c0bee9539b3afefe` found one P2/R3 cross-branch proof-graph defect: the PR #3 mirror of WORK-0002 exposed `REVIEW-0002`, `TEST-0002` and `TEST-0003` as locally traversable structured proof IDs although those records exist only on the WORK-0002 implementation branch.

## REVIEW-0020 provenance and correction

REVIEW-0020 is truthfully imported under v7:

- one-shot authorization `53d2b3861b35ad3b17ea9718794c99a594ca4557` existed before materialization;
- initial import `f7955c10d4c932df86c3238c8e91322c24ce6929` records the externally completed `CHANGES_REQUIRED` review;
- review binding is `0c0ff92c75f80e53640c62b86c283d230382a510`;
- authorization consumption is `d3a17e7049ff264b22107585bff4145f46fddac3` and binds `consumed_by_commit` to the exact import `f7955c10d4c932df86c3238c8e91322c24ce6929`.

REVIEW-0020/F-1 is corrected structurally in PR #3's WORK-0002 mirror by commit `db1735c2a857ab111bb4ee9c42d522690c16e1d8`:

- `review_plan.completed_reviews` contains no branch-local `REVIEW-0002` ID;
- `required_tests` contains no branch-local `TEST-0002` / `TEST-0003` IDs;
- branch-local validation remains described as historical/live branch evidence rather than locally resolvable registry references;
- the explicit checkout boundary now covers both branch-only documents and the WORK-0002 review/test proof graph.

The real WORK-0002 implementation branch is not weakened or rewritten by this mirror correction. After checkout of `feat/work-0002-governance-ci`, its own WORK record and branch-local evidence become authoritative again.

## REVIEW-0019 correction remains active

REVIEW-0019 is truthfully imported under v7:

- authorization `c916d505f190a27d36e5d8fd4e595e970969e269`;
- import `40050f6fda6787feb42769cb6fa66547d5a1f7fb`;
- review binding `fd7459fd12ab245f37072a9126777f98a066fc0b`;
- authorization consumption `4e7e103b7b4dc6567b4bf7f80164e97646bb3e5f`.

REVIEW-0019/F-1 repaired WORK-0001's malformed RUN-3 flow mapping. REVIEW-0019/F-2 corrected copied TEST-0005 proof to the exact resolvable PASS result `ce962ec2ad199dd914ee4e4e8a66ec4e110fbfbe`.

Neither REVIEW-0019 nor REVIEW-0020 findings are considered resolved by author correction alone; exact-SHA cold-resume proof plus another independent L2 remain required.

## Pre-acceptance requirement correction remains active

The acceptance-order error found by REVIEW-0018 remains preserved rather than rewritten:

- REQ-0020/0021/0022 are inspectable as prematurely accepted atomic records and transitioned legally `ACCEPTED → SUPERSEDED` together in `9ca6b975e7abef9eadf86573f2c9e1cb07b89e3d`.
- Replacement REQ-0023 (DoR), REQ-0024 (DoD) and REQ-0025 (verification strategy) first materialized together as **PROPOSED** in `772616269581f622605416b2e34f6d4e270241df`.
- WORK-0001 active ownership routes to REQ-0023/0024/0025, not to superseded REQ-0005 or prematurely accepted REQ-0020/0021/0022.
- REQ-0023/0024/0025 remain PROPOSED pending an approval-capable independent review; no author-produced test can transition them to ACCEPTED.

## Current lifecycle contract — v7

`registry/status-machines.yaml` version 7 remains canonical. Generic semantics are unchanged:

- review initial `OPEN`, normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial `PROPOSED`, normal `PROPOSED → ACCEPTED`;
- requirement `ACCEPTED → SUPERSEDED` preserves immutable prior mistakes without rollback;
- progress `DONE → IN_REVIEW` only as reviewed reopening after new adverse evidence;
- generic TEST `PLANNED → READY → RUNNING → PASS`, with PASS reusable only through legal reopen;
- external completed reviews require one-shot authorization in a parent commit before materialization and exact later import-consumption binding.

TEST-0007 remains the generic v7 lifecycle proof on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`, result `87668f4e64453dca4c987252a8cb46e73793950c`, history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`. REVIEW-0020 did not modify generic lifecycle semantics.

## Pre-acceptance TEST-0005 proof

TEST-0005 supplied exact-SHA pre-acceptance evidence while REQ-0023/0024/0025 remained PROPOSED:

- exact tested tree `efd48467352c0ce4ec344ebe410fd9e98d938721`;
- exact PASS result commit `ce962ec2ad199dd914ee4e4e8a66ec4e110fbfbe`;
- history binding `79a95e7cda3b62b68208e333ddc1593c510167f7`.

That execution is evidence for independent review, not approval authority.

## TEST-0006 cold-resume proof routing

The latest pre-REVIEW-0020 TEST-0006 execution passed on exact REVIEW-0019-corrected tree `45a8dae7fa9f199c63651f15306dcfa6f880b248`; result `9bb81e07b7f119bc874bfcf689a5b84dcb769d71`; history binding `13b977bf5e821bbd32464a90c0bee9539b3afefe`.

That PASS remains valid for its exact tree, but REVIEW-0020 materially changed cross-branch proof-graph handover semantics. Therefore one fresh TEST-0006 execution must cover the synchronized REVIEW-0020/WORK-0001/PROJECT_STATE state before another fresh L2.

**Transition-stable rule:** the canonical current execution of each TEST lives in its TEST record. At resume, inspect TEST-0006's current lifecycle state and continue legally until a PASS exists that covers the current synchronized handover. Do not hardcode an intermediate READY/RUNNING step here and do not manufacture extra reruns after qualifying proof already exists.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency handover mirror while WORK-0001 closes. Every locally traversable path or registry ID exposed by that mirror must resolve in the PR #3 tree.

Before editing or validating WORK-0002 implementation:

1. query live PR #2 state;
2. checkout `feat/work-0002-governance-ci` (or its successor after integration);
3. re-read that branch's own `registry/work-items/WORK-0002.yaml`;
4. only then traverse its branch-local `REVIEW-0002`, `TEST-0002`, `TEST-0003`, `docs/03_ARCHITECTURE/github-control-plane.md`, and `docs/13_QUALITY/ai-context-routing.md` evidence/prerequisites.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private or personal datasets, or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles branch/ruleset/required-check/merge/security hardening while preserving public visibility.

## Review/completion semantics

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to exact artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain durable negative outcomes.

No finding is closed because the author produced a test PASS. REVIEW-0018/F-1, REVIEW-0019/F-1/F-2 and REVIEW-0020/F-1 remain open pending a later fresh-context approval-capable L2.

## Next action

1. Inspect TEST-0006's current lifecycle state and continue it legally until one exact-SHA PASS covers the synchronized REVIEW-0020/WORK-0001/PROJECT_STATE state, including machine-readable WORK-0001, exact TEST-0005 SHA integrity and the corrected WORK-0002 cross-branch proof boundary.
2. Once that qualifying PASS exists, reply to REVIEW-0020/F-1 and the still-relevant REVIEW-0018/0019 threads with exact evidence; leave them unresolved, freeze the resulting PR #3 HEAD and request fresh-context L2 explicitly on that exact SHA.
3. The reviewer must parse/load `registry/work-items/WORK-0001.yaml`, verify exact TEST-0005 SHA integrity, inspect REQ-0023/0024/0025 while they remain PROPOSED, verify the WORK-0002 mirror exposes no unresolved branch-local proof IDs, and inspect the accumulated PR for any material P0/P1/P2 defect.
4. If the L2 finds a defect, record/correct/re-prove it. If clean/approval-capable, record its v7 provenance first, then transition REQ-0023/0024/0025 to ACCEPTED as reviewed administrative state changes with no substantive text mutation, resolve only independently verified findings, finalize WORK-0001/progress/completion and merge PR #3.
5. After PR #3 merge, query live PR #2, integrate new main, rerun its full gate, obtain its own fresh L2, and merge only if all gates genuinely pass.
6. Continue with WORK-0003 and then WORK-0004 in roadmap order.

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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0020.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
