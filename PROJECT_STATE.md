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
- `WORK-0002` — governance automation on open **PR #2** / branch `feat/work-0002-governance-ci`, last rechecked live at HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`, lifecycle `IN_REVIEW`.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 assurance history

The durable review chain is `REVIEW-0003` through `REVIEW-0016`. Corrective test evidence is `TEST-0004`, `TEST-0005`, `TEST-0006`, and `TEST-0007`; superseded `TEST-0001` remains historical/non-gating evidence.

Key narrowing:

- `REVIEW-0007` invalidated the first TEST-0006 PASS because PROJECT_STATE, WORK-0002 and the progress matrix disagreed on the global WORK-0002 lifecycle.
- `REVIEW-0008` invalidated the second TEST-0006 PASS because the PR #3 WORK-0002 mirror referenced branch-only `read_before` files absent from the tested tree.
- `REVIEW-0009` through `REVIEW-0013` established reviewed progress reopening, the exact TEST-0004 historical migration, REQ-0006 ↔ TEST-0007 traceability, current handover alignment and WORK-level TEST-0007 declaration.
- `REVIEW-0014`, on `c9b75f677f5b79f66189f90a730cb8efbeb8af0c`, found post-contract direct materialization of REVIEW-0004..REVIEW-0013 as `COMPLETE` and REQ-0015..REQ-0019 as `ACCEPTED`.
- `REVIEW-0015`, from fresh Codex review of exact head `a27d01a9c0add10d0de220b9443a7f7d113152d9`, proved that REVIEW-0014 itself had already completed externally before its apparent `OPEN → IN_PROGRESS → COMPLETE` commits; v7 now preserves that sequence only as historical replay and requires truthful preauthorized import for future externally completed reviews.
- `REVIEW-0016`, from fresh Codex review of exact head `7c9cc98fefc45eab2e500925dca846f23bd2936e`, found one P2/R3 handover defect: that frozen HEAD itself already synchronized WORK-0001 with the TEST-0006 PASS, while PROJECT_STATE still listed that completed synchronization as its first next action.

## Current lifecycle correction — v7

`registry/status-machines.yaml` version 7 keeps normal repository-native lifecycle semantics strict:

- review initial state remains `OPEN` with normal `OPEN → IN_PROGRESS → COMPLETE`;
- requirement initial state remains `PROPOSED` with normal `PROPOSED → ACCEPTED`;
- no generic `OPEN → COMPLETE` shortcut and no alternate `ACCEPTED` initial state exist;
- progress `DONE → IN_REVIEW` remains a reviewed reopening only after new adverse evidence;
- generic TEST execution remains `PLANNED → READY → RUNNING → PASS`;
- exact immutable pre-v7 review/requirement/test exceptions remain record/commit-bound and non-reusable.

v7 additionally distinguishes **repository-native review execution** from **a review that already completed externally before registry materialization**:

1. A lifecycle checkpoint is evidence only if that state actually existed while the governed activity was occurring.
2. REVIEW-0014's immutable replay is preserved by one exact `historical_replay_exception` bound to external source review `PRR_kwDOUUI5ts8AAAABNFU66A` and commits `ec69110468c7e1cd79984dedb835504de8c0b561 → 2926a070de8371e7ad3aaebeca0d9e424700d43f → b03880759f7dde54b6f59f3ecaf4f2d5889e1eb7`; it is `historical_only` and `future_reuse_forbidden`.
3. Externally completed reviews use a one-shot **preauthorized import** rather than replaying OPEN/IN_PROGRESS after completion.
4. The authorization must already exist in a parent commit before the REVIEW file first appears, bind record/result/reviewed SHA/source review/context, and later be consumed by the exact first-materialization commit.

REVIEW-0015 demonstrates the first v7 import path: authorization `2b26ed4384e2098e04c10f5e5d2db3da949b6718` → import `877d5bce12c7854701843747783891558ab05d37` → bindings `f46307b88633d362ccfe59309097c8a574e1407f` / `ecf2619b5194257dbc254bd141ef56bcb0010b36`.

REVIEW-0016 follows the same truthful path: authorization `f19d261032b29ae4180b98a99dff494964b612b7` existed before import `83b98e1b2a06ca0312614b44c8b8e8ccc6468c44`; review binding is `bf37979755020e0633df0f4966cd5bf3707da94e`, and authorization consumption is `820b32588ec053b2fcfe130fd84d4fd4d9720d22`.

## Exact-SHA proof

TEST-0007 current v7 execution is **PASS** on exact tree `669dcf7638746e07cc034cd69fa2cb08da133937`; result commit `87668f4e64453dca4c987252a8cb46e73793950c`; history pointer `87ec209eec614a0ff3be7a00a7565102042cad3f`.

That run proved from Git history rather than prose that REVIEW-0014 is an exact historical replay, REVIEW-0015 authorization predates materialization and is one-shot/bound, pre-v7 REVIEW/REQ imports remain exact, TEST-0004 migration remains isolated, progress reopening remains reviewed, and REQ-0006 ↔ TEST-0007 traceability remains intact.

Under v7, two cold-resume runs correctly returned FAIL instead of manufacturing a PASS:

- exact tree `11cca4bccb318d29c422917d544a470870b2cf65`: PROJECT_STATE still instructed already-completed WORK-0001 synchronization and TEST-0006 reopen actions; result commit `35e3c4c892f8c9bc6e5424fbe792c2fc8043eaf8`;
- exact tree `75d3df4486d05ab95d9d65daee2fd7ac77072a47`: the handover still started by recording the prior FAIL and reopening TEST-0006 even though both were already complete at that READY tree; result commit `49a772c224cb3dd4811f48f4bc0431c155b01e74`.

The handover was made transition-stable and TEST-0006 then **PASS**ed on exact tree `d6f012abe31263f0fa83003646405c039b23611e`; result `788a2948054cdd90130c72b17910d745fd36d927`; history pointer `11615248d3cafd3577a2920b5a323daa51040f12`.

REVIEW-0016 does not invalidate that historical execution on its tested tree; it shows that a later administrative PROJECT_STATE/WORK-0001 synchronization reintroduced stale next-action wording at `7c9cc98f`. Therefore TEST-0006 must be reopened and rerun after this handover correction before another fresh L2 can close WORK-0001.

All prior review findings remain durable evidence. REVIEW-0014/F-1, REVIEW-0014/F-2, REVIEW-0015/F-1 and REVIEW-0016/F-1 remain unresolved until a later fresh-context L2 independently verifies the corrected current head. No finding is closed merely because the author produced a PASS.

## WORK-0002 cross-branch boundary

The WORK-0002 record stored on PR #3 is only the globally readable handover mirror needed while WORK-0001 closes. Every path in its PR #3 `read_before` list must exist in the PR #3 tree.

To resume WORK-0002 implementation after WORK-0001/PR #3 completes:

1. checkout `feat/work-0002-governance-ci` (or its successor after PR #3 merge);
2. integrate the new `main`/WORK-0001 v7 contract before claiming new WORK-0002 proof;
3. re-read that branch's `registry/work-items/WORK-0002.yaml`;
4. then read branch-local prerequisites, including `docs/03_ARCHITECTURE/github-control-plane.md` and `docs/13_QUALITY/ai-context-routing.md`;
5. recheck live PR #2 HEAD/checks/threads before editing.

WORK-0002 cannot become DONE while WORK-0001 remains IN_REVIEW.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle state

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. A later independent review can invalidate or re-question current-gate applicability of a SHA-bound PASS without erasing the execution on its tested tree.

Only a `COMPLETE` review whose outcome is `APPROVE` or `APPROVE_WITH_FOLLOWUP` may provide approval evidence, subject to artifact binding, required roles/independence and blocking-finding rules. `CHANGES_REQUIRED` and `BLOCKED` remain negative outcomes.

A blocking R1/R2 finding may become non-blocking through `ACCEPTED` only with explicit accepting actor, authority role, authority evidence, rationale, date and review condition appropriate to assurance level.

Historical import/replay exceptions preserve immutable history only when their exact record/status/commit/source tuples are explicitly bounded. They never create alternate initial states, generic transitions, or reusable future shortcuts. Post-v7 external reviews use preauthorized one-shot import provenance rather than post-hoc lifecycle replay.

## Next action

1. Continue the **current fresh-review gate from repository and live GitHub state**. REVIEW-0016/F-1 is the latest material finding and this file now contains its handover correction; do not repeat prior WORK-0001 synchronization or evidence-recording steps already present in Git history.
2. Synchronize WORK-0001 with REVIEW-0016 while keeping WORK-0001, T6, RUN-3 and all completion/review gates non-terminal.
3. Reopen TEST-0006 from its current PASS to READY, use the resulting corrected/synchronized tree as the exact rerun target, then execute READY → RUNNING and recheck cold-resume/currentness, WORK-0002/matrix state, all current-tree read_before paths, PR #2 branch handoff/live state, v7 import/replay provenance, positive-only review approval and TEST-0001 replacement scope.
4. Record PASS only if every assertion is true; bind the result and synchronize the current PASS into WORK-0001/PROJECT_STATE without reintroducing an already-completed first action.
5. Reply to REVIEW-0016/F-1 with exact evidence but leave relevant threads unresolved pending independent verification. Freeze the resulting PR #3 HEAD and request another fresh-context L2 on that exact SHA.
6. If the next fresh L2 reports a material defect, record/correct/re-prove it. If it reports no material defect, record truthful approval-capable L2 evidence, resolve only findings independently verified as corrected, finalize WORK-0001/progress/completion and merge PR #3.
7. After PR #3 merge, integrate new main into PR #2, correct/re-prove its six outstanding fresh-L2 findings under the v7 contract, obtain its own fresh L2, and merge only if its gate genuinely passes.
8. Continue with WORK-0003 and then WORK-0004 in roadmap order.

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
9. `registry/requirements/REQ-0001.yaml` through `REQ-0019.yaml`
10. `registry/reviews/REVIEW-0003.yaml` through `REVIEW-0016.yaml`
11. `registry/tests/TEST-0004.yaml` through `TEST-0007.yaml`, plus superseded historical `TEST-0001.yaml`
12. live PR #3 reviews/threads
13. live PR #2 HEAD/checks/unresolved threads

No prior chat history is required.
