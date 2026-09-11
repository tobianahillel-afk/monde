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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`. Its volatile HEAD/check/thread state and branch-local documents/schemas/review/test proof graph are deliberately not duplicated here; query GitHub and checkout that branch before traversing WORK-0002 implementation evidence.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is now `REVIEW-0003` through `REVIEW-0023`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- REVIEW-0007/0008 forced coherent global lifecycle and explicit cross-branch prerequisite boundaries.
- REVIEW-0009..0013 established reviewed progress reopening, exact historical TEST migration, current lifecycle traceability and transition-stable handover/work-level proof declarations.
- REVIEW-0014/0015 established exact historical import/replay boundaries and the v7 one-shot preauthorized external-review import mechanism.
- REVIEW-0016 removed stale completed actions from the cold-resume handover.
- REVIEW-0017 found stale duplicated TEST-0006 currentness plus compound REQ-0005; those defects were structurally corrected and re-proven.
- REVIEW-0018 found premature acceptance of REQ-0020/0021/0022 before approval-capable independent review; those records remain superseded history and replacement REQ-0023/0024/0025 remain PROPOSED.
- REVIEW-0019 found malformed WORK-0001 YAML plus a truncated copied TEST-0005 result SHA; both were corrected and re-proven.
- REVIEW-0020 found PR #3's WORK-0002 mirror exposing branch-local `REVIEW-0002`, `TEST-0002`, and `TEST-0003` as locally traversable proof; the mirror now defers that proof behind explicit checkout.
- REVIEW-0021 found missing forward TEST-0006 mappings on REQ-0023/0024/0025; reciprocal requirement↔test traceability was restored while all three requirements remained PROPOSED.
- REVIEW-0022, fresh-context L2 on exact head `97be290c21840098f02b92aa26a195a6e1017fbb`, found branch-only `affected_schemas` still exposed by the PR #3 WORK-0002 mirror plus stale TEST-0004 reverse coverage of current REQ-0010; both were corrected and re-proven.
- REVIEW-0023, fresh-context L2 on exact head `3a05ec6f14ea71d15b1cc842ef634e00279217e6`, found that this handover still presented the already-completed REVIEW-0022 TEST-0006 rerun as future work. That handover-currentness defect is the current correction target.

## REVIEW-0023 provenance and current correction

REVIEW-0023 is truthfully imported under v7:

- one-shot authorization `bdc52847919696e72b13f63afcad622412739ef3` existed before materialization;
- initial import `026849083f8baf7a40a67ec6ac70e2b2e169abbe` records the externally completed `CHANGES_REQUIRED` review;
- review binding is `741a8662a61acdec56addca8492cb45341c93e7b`;
- authorization consumption is `be897be03267a44bf5167a18dca0ada384e42052` and binds `consumed_by_commit` to the exact import `026849083f8baf7a40a67ec6ac70e2b2e169abbe`.

REVIEW-0023/F-1 remains `OPEN` pending independent verification. Its correction is to keep this handover transition-stable: completed TEST-0006 proof is recorded as completed history, while current execution identity and whether another rerun is needed are determined only from `registry/tests/TEST-0006.yaml`.

## REVIEW-0022 provenance and corrections remain active

REVIEW-0022 provenance remains authorization `c2921a693a2a2b4350ef50c8f77fc69895f17305` → import `5e22bd5b63c723f29a2e20ad07c8d69c9881cae5` → review binding `aee461bfee70ade613bcb5a99154a0aeb3b660cb` → authorization consumption `ff3b6cd85b76cd11f78afd80c4040bb92d3fbad6`.

Its corrections remain present and findings intentionally remain open pending independent verification:

- REVIEW-0022/F-1: PR #3 WORK-0002 mirror has `affected_schemas: []`; branch-local schemas are deferred behind checkout of `feat/work-0002-governance-ci`. Correction commit: `1ccd23ac7d1ccefea7af065df66a0596b0368b02`.
- REVIEW-0022/F-2: TEST-0004 no longer lists current REQ-0010 in `protects.requirements`; REQ-0010 continues to use TEST-0005 as current verification proof. Correction commit: `2356271e2def66e490f10251753224b9876960cc`.

## Earlier current corrections remain active

REVIEW-0021 truthful provenance remains authorization `c059a18749426cae3c2c3429893f35ec6db8b0ff` → import `aca6010aaf59a923e59a8cc587cc9b8689ce8425` → review binding `4903934af7a263a8a16171329bf7bbb3a12df886` → authorization consumption `038b2d35e19d93fd6a665ca0ae6c8261f7a165fe`.

REQ-0023, REQ-0024 and REQ-0025 remain `PROPOSED` and each maps forward to `[TEST-0005, TEST-0006]`; TEST-0006 continues to protect all three.

REVIEW-0020 truthful provenance remains authorization `53d2b3861b35ad3b17ea9718794c99a594ca4557` → import `f7955c10d4c932df86c3238c8e91322c24ce6929` → review binding `0c0ff92c75f80e53640c62b86c283d230382a510` → authorization consumption `d3a17e7049ff264b22107585bff4145f46fddac3`.

PR #3's WORK-0002 mirror contains no branch-local `REVIEW-0002`, `TEST-0002`, `TEST-0003`, or branch-local schema paths in locally traversable structured fields. Those records/schemas, plus `docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`, become authoritative only after explicit checkout of `feat/work-0002-governance-ci`.

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

TEST-0007 remains the generic v7 lifecycle proof on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`, result `87668f4e64453dca4c987252a8cb46e73793950c`, history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`. REVIEW-0023 adds one consumed authorization but does not change generic lifecycle semantics.

## TEST-0006 cold-resume proof routing

The REVIEW-0022-synchronized TEST-0006 execution completed on exact tree `6e6e005fc81b0ea91427fc55ea1f09d818650d7b`; result `b0fde620d06e0b4e4e5d16ab39680ad468fbf260`; history binding `3a05ec6f14ea71d15b1cc842ef634e00279217e6`.

REVIEW-0023 subsequently established that this execution's handover-currentness assertion was false because this file still ordered that same completed rerun as future work. Preserve that PASS as historical evidence and record any invalidation in `registry/tests/TEST-0006.yaml`; do not rewrite the execution away.

**Transition-stable rule:** `registry/tests/TEST-0006.yaml` is the sole canonical source for current TEST-0006 lifecycle/execution identity. At resume:

- if its current valid execution already PASSes on a tree that includes the REVIEW-0023-corrected PROJECT_STATE/WORK-0001 handover, proceed directly to a fresh exact-SHA L2;
- if not, continue the existing TEST-0006 lifecycle legally until exactly one qualifying PASS exists;
- never reopen or rerun merely to manufacture a newer SHA after qualifying proof exists.

This rule remains correct both before and after the corrective rerun.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency handover mirror while WORK-0001 closes. Every locally traversable path, schema or registry ID exposed by that mirror must resolve in the PR #3 tree.

Before editing or validating WORK-0002 implementation:

1. query live PR #2 state;
2. checkout `feat/work-0002-governance-ci` (or its successor after integration);
3. re-read that branch's own `registry/work-items/WORK-0002.yaml`;
4. only then traverse branch-local schemas, `REVIEW-0002`, `TEST-0002`, `TEST-0003`, `docs/03_ARCHITECTURE/github-control-plane.md`, and `docs/13_QUALITY/ai-context-routing.md`.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private or personal datasets, or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles branch/ruleset/required-check/merge/security hardening while preserving public visibility.

## Review/completion semantics

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to exact artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain durable negative outcomes.

No finding is closed because the author produced a correction or test PASS. REVIEW-0018/F-1, REVIEW-0019/F-1/F-2, REVIEW-0020/F-1, REVIEW-0021/F-1, REVIEW-0022/F-1/F-2, and REVIEW-0023/F-1 remain open pending a later fresh-context approval-capable L2.

## Next action

1. Treat REVIEW-0023/F-1 as the current adverse finding and keep REQ-0023/0024/0025 PROPOSED and WORK-0001 IN_REVIEW.
2. Read `registry/tests/TEST-0006.yaml` for the current lifecycle/execution identity. If no valid PASS yet covers this REVIEW-0023-corrected PROJECT_STATE/WORK-0001 handover, continue that test legally through the minimum required lifecycle to obtain one; otherwise skip any extra rerun.
3. On the exact qualifying TEST-0006 tree, verify: WORK-0001 parses as YAML and remains IN_REVIEW; PROJECT_STATE routes directly from qualifying TEST proof to fresh L2 rather than completed work; REQ-0023/24/25 remain PROPOSED with reciprocal TEST-0006 mappings; exact TEST-0005 SHA integrity; PR #3 WORK-0002 mirror contains no branch-only read_before/review/test/schema references before checkout; TEST-0004 does not protect current REQ-0010 while REQ-0010 maps to TEST-0005; REVIEW-0022 and REVIEW-0023 provenance chains are exact; live PR #2 lifecycle remains coherent after explicit checkout boundary.
4. Once one qualifying PASS exists, freeze that resulting PR #3 HEAD and request a fresh-context L2 explicitly on that SHA. Do not mutate the candidate while that review is running.
5. If the L2 finds a defect, record/correct/re-prove it. If clean/approval-capable, record its v7 provenance first, then transition REQ-0023/0024/0025 to ACCEPTED as reviewed administrative state changes with no substantive text mutation, resolve only independently verified findings, finalize WORK-0001/progress/completion and merge PR #3.
6. After PR #3 merge, query live PR #2, integrate new main, rerun its full gate, obtain its own fresh L2, and merge only if all gates genuinely pass.
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
9. active PROPOSED `REQ-0023.yaml` through `REQ-0025.yaml`, plus current `REQ-0010.yaml`, superseded `REQ-0005.yaml` and `REQ-0020.yaml` through `REQ-0022.yaml`
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0023.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
