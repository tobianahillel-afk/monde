# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions. Mutable TEST lifecycle/result truth lives only in each `registry/tests/TEST-*.yaml` record.

## Current phase / lot / blocker

- **PHASE-0 — Specification, repository governance and canonical documentation**
- **LOT-0 — AI-first repository operating system**
- **SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**
- `WORK-0001` remains `IN_REVIEW / A3` on PR #3 / `chore/work-0001-assurance-closure` and blocks truthful completion of WORK-0002.
- `WORK-0002` remains separate on PR #2 / `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`; query its live HEAD/check/thread state and checkout that branch before traversing branch-local implementation evidence.
- WORK-0003 and WORK-0004 have not started.

PR #1 remains historically squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`.

## Latest independent review — process this first

A fresh-context Codex L2 reviewed exact frozen PR #3 commit `4f8cebeeca36d895cc17b1103d7689bcf27b5541` and submitted source review `PRR_kwDOUUI5ts8AAAABNYK4AQ` at `2026-09-13T23:27:28Z`.

It is **negative evidence**, not approval: three new findings were emitted and no TEST-0008 cold-read qualification/outcomes were supplied.

1. `PRRT_kwDOUUI5ts6h8-Hz` — P1/R2-equivalent: `REVIEW-0001/F-3` used a self-referential prose authority reference instead of independently resolvable GitHub role proof.
2. `PRRT_kwDOUUI5ts6h8-H0` — P2: `REQUIREMENT_NORMATIVE_V1` did not define byte-exact JSON string serialization, so semantically equivalent JSON could hash differently across implementations.
3. `PRRT_kwDOUUI5ts6h8-H2` — P2: this handover still routed a cold-resuming agent through already-completed v9 TEST-0006 synchronization/rerun work instead of directly to the fresh L2 result.

The durable REVIEW-0026 registry record is **not yet materialized**. Before first materialization, create the exact one-shot external-import authorization required by `registry/status-machines.yaml`, binding source review `PRR_kwDOUUI5ts8AAAABNYK4AQ`, artifact `4f8cebee...`, submission time, reviewer context and expected `CHANGES_REQUIRED`; then materialize REVIEW-0026 and later bind `consumed_by_commit` to its exact first-materialization commit. Do not replay OPEN/IN_PROGRESS after the external review already completed.

## Corrections already made after the latest L2

Two of the three review defects have already been structurally corrected; these author corrections do not resolve the findings without another independent review.

- `02df7ed4595d33e5139bbda90136e41be8b9f69d` updates `registry/content-identity.yaml` to version 2 and makes `REQUIREMENT_NORMATIVE_V1` byte-exact through RFC 8785/JCS. The SHA-256 input is now explicitly the exact UTF-8 bytes emitted by an RFC-8785-conformant serializer; implementation-defined escaping/order/number/whitespace is fail-closed. Because the canonicalization contract changed, current acceptance proof must be rerun even if the existing requirements happen to recompute to the same digest bytes.
- `5a22bec07422905fa7550eb698cf4c453bdea154` updates `REVIEW-0001/F-3` to use `authority_evidence_type: GITHUB_REPOSITORY_OWNER_PERMISSION` and durable `authority_evidence_ref: https://api.github.com/repos/tobianahillel-afk/monde`. Live GitHub checks on 2026-09-14 confirm `owner.login=tobianahillel-afk` and collaborator permission `admin`.
- This PROJECT_STATE edit corrects the third finding by making the fresh L2 result, not already-completed TEST-0006 administration, the first resume action.

## Canonical acceptance contract

`registry/status-machines.yaml` version 9 remains canonical unless deliberately revised by a later reviewed change.

Requirement acceptance remains content-bound and requires both:

1. a COMPLETE approval-capable independent review whose scope binds the exact current requirement digest while the requirement is still PROPOSED; and
2. a PASS TEST referenced by `verification.acceptance_cold_read_test_ids` that explicitly qualifies as L2/L3 fresh-context, authoring-separated cold-read evidence for the same exact digest, with source/executor provenance and all required outcomes PASS.

`TEST-0008` remains the dedicated acceptance cold-read artifact for REQ-0023/24/25. It is still non-qualifying/unexecuted; do not fabricate source, executor, outcomes or PASS state from the negative Codex review.

Risk and accepted-finding authority remains resolved from `registry/acceptance-authority.yaml` version 1. Free-form role/evidence prose never grants authority.

## Active requirements

REQ-0020/0021/0022 remain `SUPERSEDED` premature-acceptance history. Active REQ-0023, REQ-0024 and REQ-0025 remain **PROPOSED**.

Their currently declared digests remain:

- REQ-0023: `sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b`
- REQ-0024: `sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4`
- REQ-0025: `sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67`

Because the canonicalization contract changed after the prior TEST-0005 PASS, these digests must be recomputed again under RFC 8785/JCS before current proof is considered sufficient.

No current review is approval-capable for these requirements. REVIEW-0018/0024/0025 and the new external Codex review of `4f8cebee...` are all negative evidence.

## Existing exact-SHA proof — historical/current-boundary reminder

Always read each TEST record for mutable current state. Historical exact proof remains useful but is not silently promoted after a contract change.

- TEST-0005 prior v9 corrected execution: tree `1562acdff730d832770befdbfe296615fac2a544` → PASS `7abdfbd0655e96239d8ddb511f3edfc0b19571f7` → binding `ae89cf9fd1252ec50e537f014983b3979c44a6ad`. It predates the RFC-8785 canonicalization clarification and must be rerun for current proof.
- TEST-0007 prior v9 execution: tree `278da4e4f14a9897fa746d29725c8f666b6add2c` → PASS `61c64a2c0920a28949377b75aa9df92637aeb371` → binding `8288143e2915498a06d0a18db8ffbaa607fac948`. It predates the new independently-resolvable REVIEW-0001/F-3 evidence and must be rerun for current authority proof.
- TEST-0006 latest completed v9 handover proof: tree `70d9a8a12cf0727fddb377d6c8a45a7ad47f6583` → PASS `673d8f4891f713bf9d230ea908f9c1fc8acba090` → binding `4f8cebeeca36d895cc17b1103d7689bcf27b5541`. The fresh L2 proved this handover itself was stale, so current handover proof must be rerun only after REVIEW-0026 is durably recorded and WORK/PROJECT_STATE are synchronized with the new findings.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 remains only the globally readable lifecycle/dependency mirror while WORK-0001 closes. Before editing/validating WORK-0002 implementation:

1. query live PR #2;
2. checkout `feat/work-0002-governance-ci` or its integrated successor;
3. re-read that branch's own WORK-0002;
4. only then traverse its branch-local schemas, REVIEW-0002, TEST-0002/0003 and implementation docs.

Do not canonize volatile PR #2 HEAD/check/thread state here.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles protection/check/security hardening, not privatization.

## Next action

1. Process the external L2 on `4f8cebee...` first: add a valid one-shot authorization for REVIEW-0026, then materialize REVIEW-0026 as COMPLETE/CHANGES_REQUIRED with the three findings above and bind/consume its exact import commit. Do not treat author corrections as resolution.
2. Synchronize WORK-0001 through REVIEW-0026 while keeping WORK-0001/RUN-3 `IN_REVIEW`, all completion gates non-terminal, and REQ-0023/24/25 PROPOSED.
3. Recompute all three requirement digests under RFC 8785/JCS. If any differs, update the declared digest and TEST-0008 target binding before proof; preserve the mismatch as FAIL evidence rather than hiding it.
4. Legally rerun TEST-0005 for the current canonicalization contract and TEST-0007 for current authority/import semantics.
5. After REVIEW-0026 + corrections + TEST-0005/0007 are synchronized, legally rerun TEST-0006 exactly once for the new transition-stable handover. Do not rerun merely to manufacture a newer SHA after a qualifying PASS exists.
6. Freeze the resulting candidate and request another fresh-context L2. That review must independently verify REVIEW-0026/F-1/F-2/F-3 corrections and separately answer all TEST-0008 cold-read outcomes. Do not mutate the candidate while that review is running.
7. Only if the next L2 is clean/approval-capable and supplies explicit PASS cold-read outcomes may TEST-0008 be materialized/bound from the external source and the exact review evidence be linked to REQ-0023/24/25 before any no-content-change PROPOSED → ACCEPTED transition.
8. Resolve historical findings only when independently verified; then finalize WORK-0001/progress/completion and merge PR #3 only if every gate genuinely passes.
9. After PR #3 merge, integrate new main into PR #2, rerun its complete gate/fresh L2 and finish WORK-0002 before WORK-0003 and WORK-0004.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. live PR #3 reviews/threads, especially source review `PRR_kwDOUUI5ts8AAAABNYK4AQ`
6. `registry/work-items/WORK-0001.yaml`
7. `registry/status-machines.yaml`
8. `registry/content-identity.yaml`
9. `registry/acceptance-authority.yaml`
10. `registry/requirements/REQ-0023.yaml` through `REQ-0025.yaml`
11. `registry/reviews/REVIEW-0025.yaml`, then REVIEW-0026 once materialized
12. `registry/tests/TEST-0005.yaml` through `TEST-0008.yaml`
13. `registry/work-items/WORK-0002.yaml` and `registry/progress/matrix.yaml`
14. live PR #2 state

No prior chat history is required.
