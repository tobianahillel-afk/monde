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

The durable review chain is now `REVIEW-0003` through `REVIEW-0024`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- REVIEW-0007/0008 forced coherent global lifecycle and explicit cross-branch prerequisite boundaries.
- REVIEW-0009..0013 established reviewed progress reopening, exact historical TEST migration, current lifecycle traceability and transition-stable handover/work-level proof declarations.
- REVIEW-0014/0015 established exact historical import/replay boundaries and the one-shot preauthorized external-review import mechanism.
- REVIEW-0016 removed stale completed actions from the cold-resume handover.
- REVIEW-0017 found stale duplicated TEST-0006 currentness plus compound REQ-0005; those defects were structurally corrected and re-proven.
- REVIEW-0018 found premature acceptance of REQ-0020/0021/0022 before approval-capable independent review; those records remain superseded history and replacement REQ-0023/0024/0025 remain PROPOSED.
- REVIEW-0019 found malformed WORK-0001 YAML plus a truncated copied TEST-0005 result SHA; both were corrected and re-proven.
- REVIEW-0020 found PR #3's WORK-0002 mirror exposing branch-local proof IDs before checkout; the mirror now defers that proof behind the explicit branch boundary.
- REVIEW-0021 restored reciprocal REQ-0023/0024/0025 ↔ TEST-0006 traceability while all three requirements remained PROPOSED.
- REVIEW-0022 removed branch-only schemas from the PR #3 WORK-0002 mirror and removed stale TEST-0004 reverse coverage of current REQ-0010.
- REVIEW-0023 found stale handover routing after an already-completed TEST-0006 rerun; WORK/PROJECT_STATE were changed to transition-stable conditional routing.
- REVIEW-0024, fresh-context L2 on exact head `9551a78c7431d1b7ce3334d4a6529d92ba69ab5a`, found two R2/P1 defects: requirement `PROPOSED → ACCEPTED` was still only policy-gated rather than machine-gated, and risk `ACCEPTED` transitions lacked durable accepting-authority evidence.

## REVIEW-0024 provenance and corrections

REVIEW-0024 is truthfully imported through the one-shot external-review mechanism:

- authorization `44d465628e88d98f85414d565ef51e110fb1e891` existed before materialization;
- initial import `0b2ee6f13430d367c99dde55c6be726c13ab561a` records the externally completed `CHANGES_REQUIRED` review;
- review binding is `76671f8dd33796b6fe39d0bb7e6a35a3baeeba8b`;
- authorization consumption is `4f8f06722f936ae334c437363681abc171334ce1` and binds `consumed_by_commit` to the exact import `0b2ee6f13430d367c99dde55c6be726c13ab561a`.

Both REVIEW-0024 findings remain `OPEN` pending independent verification.

Corrections already present:

- F-1: `registry/status-machines.yaml` v8, introduced by `31ae52546688fe9a6534d6cebaeca89caebf4018`, makes `PROPOSED → ACCEPTED` necessary but insufficient. Acceptance now requires a resolvable `COMPLETE` approval-capable independent review from `verification.acceptance_evidence`, with applicable independence/scope and inspection while the requirement was still `PROPOSED`, plus an exact-revision `PASS` cold-read TEST from `verification.test_ids` that protects the requirement and ran while it was still `PROPOSED`.
- F-2: v8 also makes `RISK → ACCEPTED` authority-bearing. Commit `0434817be1c4c9f96e6d963cb4b9d231c0fa7923` updates the risk template with `accepted_by`, `authority_role`, `authority_evidence`, rationale, acceptance time and review condition; the status-machine rule requires evidence of authority appropriate to risk severity/category and owning-work assurance.

No author correction closes either finding.

## Current revision-bound v8 proofs

Current mutable TEST lifecycle/execution identity is authoritative **only in each TEST record**. The chains below are completed historical proof for the current v8 correction; if a TEST is later legally reopened, read its record rather than treating this section as a second execution registry.

- TEST-0005 v8 pre-acceptance cold-read/machine-guard proof: tree `dc52009ff2cb31f382544a812da937e686d63c8d` → PASS `f02bf1879180dc3ac80c659c327ea25d1ad72411` → binding `2cd504e4ea261ed29281777a355da7651c307463`. REQ-0023/24/25 were still `PROPOSED`; this proves the cold-read half and that negative reviews cannot satisfy v8 acceptance, but it does **not** supply independent approval.
- TEST-0007 v8 lifecycle/risk-authority proof: tree `dd21e4f3171669a5f7b47a89988a169f5d8f2e9b` → PASS `734bdbddf528100cb68f186a6f4e87a3c1606eb2` → binding `27c12c17071af395c1f3cc7cd74703b31864715e`. It verifies REVIEW-0024 authorization ancestry/import binding, v8 requirement/risk acceptance contracts, the risk-template fields, and REQ-0006↔TEST-0007 traceability.

## Pre-acceptance requirement state

The acceptance-order error found by REVIEW-0018 remains preserved rather than rewritten:

- REQ-0020/0021/0022 are inspectable as prematurely accepted records and are now `SUPERSEDED`;
- replacement REQ-0023 (DoR), REQ-0024 (DoD), and REQ-0025 (verification strategy) first materialized together as `PROPOSED` in `772616269581f622605416b2e34f6d4e270241df`;
- all three remain `PROPOSED` now;
- each maps to TEST-0005 and TEST-0006; TEST-0006 protects all three;
- TEST-0005 v8 provides the exact-revision pre-acceptance cold-read evidence;
- no current review is approval-capable for their acceptance: REVIEW-0018 and REVIEW-0024 are negative evidence;
- therefore v8 currently forbids their transition to `ACCEPTED` even though the raw status edge exists.

After a future clean independent review, its durable `REVIEW-*` record must be imported/bound first and referenced as qualifying acceptance evidence before the no-content-change acceptance transition can satisfy v8.

## Current lifecycle contract — v8

`registry/status-machines.yaml` version 8 is canonical.

Unchanged core semantics include:

- review initial `OPEN`, normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial `PROPOSED`; historical direct-ACCEPTED exceptions remain exact/non-reusable;
- requirement `ACCEPTED → SUPERSEDED` preserves immutable prior mistakes without rollback;
- progress `DONE → IN_REVIEW` only as reviewed reopening after new adverse evidence;
- generic TEST `PLANNED → READY → RUNNING → PASS`, with PASS reusable only through legal reopen;
- externally completed reviews require one-shot authorization in a parent commit before materialization and exact later import-consumption binding.

New v8 semantics:

- requirement acceptance is evidence-bearing: a legal `PROPOSED → ACCEPTED` edge alone cannot pass without qualifying independent approval plus exact-revision pre-acceptance cold-read proof;
- negative/out-of-scope/late review evidence cannot satisfy that requirement-acceptance gate;
- risk acceptance is authority-bearing: `ACCEPTED` requires a named actor, authority role/evidence, rationale, acceptance time and review condition, with authority appropriate to the risk and assurance policy.

## TEST-0006 cold-resume proof routing

`registry/tests/TEST-0006.yaml` is the **only** source of truth for the current TEST-0006 lifecycle state, current execution identity and current result. Do not copy its mutable status or latest-execution identity into this handover.

Historical evidence remains useful when explicitly labeled as historical:

- the valid PASS on tree `683c3493a2876b433e9b833e4d3ea3468dc9f1d3` proved the REVIEW-0023-corrected v7 handover on that exact tree, but predates REVIEW-0024/status-machine v8 and is not sufficient as the final current v8 proof;
- the first REVIEW-0024/v8 cold-resume attempt tested exact tree `ea8562ae2ff54e5ff9c73f4f09116c5f6aa82c21` and correctly recorded FAIL in `9212397d4e6af69b5b151e4f2f4dd5c242671083`, bound in `602428a9132a17c46a435c0521732bd27a3f0158`, because the previous version of this section duplicated stale mutable TEST state while the TEST itself was RUNNING.

That failure is preserved as evidence. The correction is to remove duplicated mutable TEST status entirely rather than replace one hardcoded state with another.

**Transition-stable rule:** at every resume, read `registry/tests/TEST-0006.yaml` first for current execution identity. Then:

- if no current valid PASS covers this synchronized REVIEW-0024/v8 WORK-0001 + PROJECT_STATE handover, continue TEST-0006 legally through the minimum required lifecycle until exactly one qualifying PASS exists;
- once such a PASS exists, proceed directly to a fresh exact-SHA L2;
- never reopen/rerun merely to manufacture a newer SHA after qualifying proof exists.

This wording is intended to remain true while TEST-0006 is FAIL, READY, RUNNING or PASS.

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

No finding is closed because the author produced a correction or test PASS. REVIEW-0018/F-1, REVIEW-0019/F-1/F-2, REVIEW-0020/F-1, REVIEW-0021/F-1, REVIEW-0022/F-1/F-2, REVIEW-0023/F-1, and REVIEW-0024/F-1/F-2 remain open pending a later fresh-context approval-capable L2.

## Next action

1. Keep WORK-0001 `IN_REVIEW`, REVIEW-0024/F-1/F-2 `OPEN`, and REQ-0023/0024/0025 `PROPOSED`.
2. Read `registry/tests/TEST-0006.yaml` for current execution identity. If no valid PASS covers this synchronized REVIEW-0024/v8 WORK-0001 + PROJECT_STATE handover, legally continue TEST-0006 and obtain exactly one qualifying PASS; once one exists, skip all further administrative reruns.
3. On the exact qualifying TEST-0006 tree, verify at minimum: WORK-0001 parses as YAML and remains IN_REVIEW; PROJECT_STATE contains no duplicated mutable TEST-0006 status and routes from qualifying proof directly to fresh L2; status-machine v8 and risk-template authority fields are present; REVIEW-0024 provenance is exact; TEST-0005 and TEST-0007 current v8 PASS chains resolve; REQ-0023/24/25 remain PROPOSED with reciprocal TEST-0006 mappings; WORK-0002 local/branch boundary remains resolvable; current REQ-0010/TEST-0004 revision boundary remains correct; live PR #2 lifecycle remains coherent after explicit checkout boundary.
4. Freeze the resulting PR #3 HEAD and request a fresh-context L2 explicitly on that exact SHA. Do not mutate the candidate while that review is running.
5. If the L2 finds a defect, record/correct/re-prove it. If clean/approval-capable, first preserve its one-shot external-review provenance and durable REVIEW record. Then add that qualifying review evidence to REQ-0023/24/25 and perform only the reviewed no-content-change `PROPOSED → ACCEPTED` transitions allowed by v8; resolve only independently verified findings; finalize WORK-0001/progress/completion and merge PR #3.
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
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0024.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
