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

The durable review chain is now `REVIEW-0003` through `REVIEW-0021`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- REVIEW-0007/0008 forced coherent global lifecycle and explicit cross-branch prerequisite boundaries.
- REVIEW-0009..0013 established reviewed progress reopening, exact historical TEST migration, current lifecycle traceability and transition-stable handover/work-level proof declarations.
- REVIEW-0014/0015 established exact historical import/replay boundaries and the v7 one-shot preauthorized external-review import mechanism.
- REVIEW-0016 removed stale completed actions from the cold-resume handover.
- REVIEW-0017 found stale duplicated TEST-0006 currentness plus compound REQ-0005; those defects were structurally corrected and re-proven.
- REVIEW-0018 found premature acceptance of REQ-0020/0021/0022 before approval-capable independent review; those records remain superseded history and replacement REQ-0023/0024/0025 remain PROPOSED.
- REVIEW-0019 found malformed WORK-0001 YAML plus a truncated copied TEST-0005 result SHA; both were corrected and re-proven.
- REVIEW-0020 found PR #3's WORK-0002 mirror exposing branch-local `REVIEW-0002`, `TEST-0002`, and `TEST-0003` as locally traversable proof; the mirror now defers that proof behind explicit checkout.
- REVIEW-0021, fresh-context L2 on exact head `f0d0410cd31df1b348fddf09528588e43e956945`, found one P2/R3 traceability defect: TEST-0006 protected REQ-0023/REQ-0024/REQ-0025 but the three requirements' forward `verification.test_ids` omitted TEST-0006.

## REVIEW-0021 provenance and correction

REVIEW-0021 is truthfully imported under v7:

- one-shot authorization `c059a18749426cae3c2c3429893f35ec6db8b0ff` existed before materialization;
- initial import `aca6010aaf59a923e59a8cc587cc9b8689ce8425` records the externally completed `CHANGES_REQUIRED` review;
- review binding is `4903934af7a263a8a16171329bf7bbb3a12df886`;
- authorization consumption is `038b2d35e19d93fd6a665ca0ae6c8261f7a165fe` and binds `consumed_by_commit` to the exact import `aca6010aaf59a923e59a8cc587cc9b8689ce8425`.

REVIEW-0021/F-1 is corrected without accepting the proposed requirements or changing their normative statements:

- REQ-0023 remains `PROPOSED` and now maps forward to `[TEST-0005, TEST-0006]` in commit `8bbb64bbf47e93e135f057cdd16961f6e09767ac`;
- REQ-0024 remains `PROPOSED` and now maps forward to `[TEST-0005, TEST-0006]` in commit `7a45c349ff3d9550e019100ae784fcbb14f1aaa8`;
- REQ-0025 remains `PROPOSED` and now maps forward to `[TEST-0005, TEST-0006]` in commit `ce0a6924bc7a3fcaa18a84ae14d73b957895f9b0`;
- TEST-0006 continues to protect all three requirements, restoring bidirectional current-proof traceability.

No author-produced test or metadata edit authorizes `PROPOSED → ACCEPTED`; that transition remains blocked until a clean approval-capable independent review inspects the proposed records.

## Earlier current corrections remain active

REVIEW-0020's truthful provenance remains authorization `53d2b3861b35ad3b17ea9718794c99a594ca4557` → import `f7955c10d4c932df86c3238c8e91322c24ce6929` → review binding `0c0ff92c75f80e53640c62b86c283d230382a510` → authorization consumption `d3a17e7049ff264b22107585bff4145f46fddac3`.

PR #3's WORK-0002 mirror contains no branch-local `REVIEW-0002`, `TEST-0002`, or `TEST-0003` in locally traversable structured proof fields. Those records, plus `docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`, become authoritative only after explicit checkout of `feat/work-0002-governance-ci`.

REVIEW-0019 corrected WORK-0001's malformed RUN-3 flow mapping and copied TEST-0005 proof. The exact pre-acceptance TEST-0005 chain remains:

- tested tree `efd48467352c0ce4ec344ebe410fd9e98d938721`;
- PASS result `ce962ec2ad199dd914ee4e4e8a66ec4e110fbfbe`;
- history binding `79a95e7cda3b62b68208e333ddc1593c510167f7`.

## Pre-acceptance requirement state

The acceptance-order error found by REVIEW-0018 remains preserved rather than rewritten:

- REQ-0020/0021/0022 are inspectable as prematurely accepted records and are now `SUPERSEDED`;
- replacement REQ-0023 (DoR), REQ-0024 (DoD), and REQ-0025 (verification strategy) first materialized together as `PROPOSED` in `772616269581f622605416b2e34f6d4e270241df`;
- all three remain `PROPOSED` now;
- each has bidirectional proof mapping with TEST-0006 plus pre-acceptance TEST-0005 evidence;
- they may transition to `ACCEPTED` only after a clean approval-capable independent L2 has inspected them while still proposed.

## Current lifecycle contract — v7

`registry/status-machines.yaml` version 7 remains canonical. Generic semantics are unchanged:

- review initial `OPEN`, normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial `PROPOSED`, normal `PROPOSED → ACCEPTED`;
- requirement `ACCEPTED → SUPERSEDED` preserves immutable prior mistakes without rollback;
- progress `DONE → IN_REVIEW` only as reviewed reopening after new adverse evidence;
- generic TEST `PLANNED → READY → RUNNING → PASS`, with PASS reusable only through legal reopen;
- external completed reviews require one-shot authorization in a parent commit before materialization and exact later import-consumption binding.

TEST-0007 remains the generic v7 lifecycle proof on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`, result `87668f4e64453dca4c987252a8cb46e73793950c`, history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`. REVIEW-0021 does not change generic lifecycle semantics.

## TEST-0006 cold-resume proof routing

The last pre-REVIEW-0021 TEST-0006 execution passed on exact REVIEW-0020-synchronized tree `d0c985933e66960a781513ad61bd3567c91e5344`; result `af4c50ba5a442a8bd06717c2802170bb4cbde54e`; history binding `f0d0410cd31df1b348fddf09528588e43e956945`.

That PASS remains valid for its exact tree, but REVIEW-0021 changed requirement↔test traceability and current review/handover state. Therefore one fresh TEST-0006 execution must cover this synchronized REVIEW-0021/WORK-0001/PROJECT_STATE state before another fresh L2.

**Transition-stable rule:** the canonical current execution of each TEST lives in its TEST record. At resume, inspect TEST-0006's current lifecycle state and continue legally until a PASS exists that covers the current synchronized handover. Do not hardcode an intermediate READY/RUNNING step here and do not manufacture extra reruns after qualifying proof already exists.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency handover mirror while WORK-0001 closes. Every locally traversable path or registry ID exposed by that mirror must resolve in the PR #3 tree.

Before editing or validating WORK-0002 implementation:

1. query live PR #2 state;
2. checkout `feat/work-0002-governance-ci` (or its successor after integration);
3. re-read that branch's own `registry/work-items/WORK-0002.yaml`;
4. only then traverse branch-local `REVIEW-0002`, `TEST-0002`, `TEST-0003`, `docs/03_ARCHITECTURE/github-control-plane.md`, and `docs/13_QUALITY/ai-context-routing.md`.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private or personal datasets, or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles branch/ruleset/required-check/merge/security hardening while preserving public visibility.

## Review/completion semantics

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to exact artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain durable negative outcomes.

No finding is closed because the author produced a test PASS. REVIEW-0018/F-1, REVIEW-0019/F-1/F-2, REVIEW-0020/F-1, and REVIEW-0021/F-1 remain open pending a later fresh-context approval-capable L2.

## Next action

1. Inspect TEST-0006's current lifecycle state and continue it legally until one exact-SHA PASS covers this synchronized REVIEW-0021/WORK-0001/PROJECT_STATE state, including bidirectional REQ-0023/0024/0025 ↔ TEST-0006 traceability, machine-readable WORK-0001, exact TEST-0005 SHA integrity, and the corrected WORK-0002 cross-branch proof boundary.
2. Once that qualifying PASS exists, reply to REVIEW-0021/F-1 and the still-relevant REVIEW-0018/0019/0020 threads with exact evidence; leave them unresolved, freeze the resulting PR #3 HEAD and request fresh-context L2 explicitly on that exact SHA.
3. The reviewer must parse/load `registry/work-items/WORK-0001.yaml`, verify exact TEST-0005 SHA integrity, inspect REQ-0023/0024/0025 while they remain PROPOSED with reciprocal TEST-0006 mappings, verify the WORK-0002 mirror exposes no unresolved branch-local proof IDs, and inspect the accumulated PR for any material P0/P1/P2 defect.
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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0021.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
