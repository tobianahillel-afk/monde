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

## Latest independent review

REVIEW-0026 durably represents the fresh-context Codex L2 of exact candidate `4f8cebeeca36d895cc17b1103d7689bcf27b5541`, source review `PRR_kwDOUUI5ts8AAAABNYK4AQ` submitted `2026-09-13T23:27:28Z`.

Outcome is **COMPLETE / CHANGES_REQUIRED**, not approval. Three findings remain OPEN:

1. REVIEW-0026/F-1 — R2/SECURITY: REVIEW-0001/F-3 accepted-finding authority evidence was self-referential instead of independently resolvable.
2. REVIEW-0026/F-2 — R3/VERIFICATION_VALIDATION: REQUIREMENT_NORMATIVE_V1 did not define byte-exact JSON string serialization across implementations.
3. REVIEW-0026/F-3 — R3/DOCUMENTATION_TRACEABILITY: the previous handover routed a cold-resuming agent through already-completed TEST-0006 administration instead of directly to the fresh L2 result.

The source review supplied no qualifying TEST-0008 evidence: `qualification_provided=false` and `explicit_outcomes_provided=false`. TEST-0008 therefore remains independent-only and unqualified.

### REVIEW-0026 provenance

- authorization `018ae267f2b6c63636fdb5f7833f64b1fd68f11b`
- first materialization/import `6075c1d87853f8c0c144e7d95bfa767ba476aa72`
- review-record import binding `02968f1babd5015a1549efbac46f6ba182d3d910`
- authorization consumption `d2b6d4a9b4db340d5934e5ee05b1a2d8d64e783c`

Git compare proves authorization → import is `ahead_by=1`; the sole added file is `registry/reviews/REVIEW-0026.yaml`. The one-shot authorization is consumed exactly by the first-materialization commit and cannot be reused.

## REVIEW-0026 corrections now present

Author corrections are present but do not independently resolve findings:

- F-1: REVIEW-0001/F-3 now uses `GITHUB_REPOSITORY_OWNER_PERMISSION` and durable `authority_evidence_ref: https://api.github.com/repos/tobianahillel-afk/monde`; live GitHub metadata identifies `owner.login=tobianahillel-afk` and collaborator permission `admin`.
- F-2: `registry/content-identity.yaml` version 2 binds REQUIREMENT_NORMATIVE_V1 to exact RFC 8785/JCS UTF-8 bytes, including deterministic key/string/number serialization and fail-closed non-conformant serializers.
- F-3: this handover begins from REVIEW-0026/current proof instead of replaying pre-review administration.

## Active requirement state

REQ-0020/0021/0022 remain `SUPERSEDED` premature-acceptance history. REQ-0023/0024/0025 remain **PROPOSED**.

Current REQUIREMENT_NORMATIVE_V1 / RFC 8785 JCS identities remain:

- REQ-0023: `sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b`
- REQ-0024: `sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4`
- REQ-0025: `sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67`

Requirement acceptance still requires both an exact-digest approval-capable independent review and separately qualified TEST-0008 cold-read evidence. Neither half is currently satisfied.

## Current revision-bound correction proof

These are historical exact-SHA proof summaries, not mutable TEST state. Always read the TEST record first for current lifecycle/result identity.

- TEST-0005 / content identity v2: `27c4d591d165689e26d399b303722744919b3372` → PASS `786a759a767ea8457d99eb8f528dc676964ca481` → binding `f6caaf77a2361f2f0724b6d91b1ce43da8c685f2`.
- TEST-0007 / REVIEW-0026 provenance + authority: `b0d4b4f68f457a8f9e5bfbf689a9275c203a0715` → PASS `592b88eb250f92a6e809c76f8646f85a894929b1` → binding `8e5edd80a634f552bbf92cd7da7088f9d6b06a2e`.
- Prior TEST-0006 / REVIEW-0025 handover: `70d9a8a12cf0727fddb377d6c8a45a7ad47f6583` → PASS `673d8f4891f713bf9d230ea908f9c1fc8acba090` → binding `4f8cebeeca36d895cc17b1103d7689bcf27b5541`; REVIEW-0026 later made that proof historical.
- First REVIEW-0026 handover attempt: `d3997dd1c377b220e26eb7eeb3fc0a5c80f8b698` → FAIL `09c43f5f130a3baa71df4c2654b005380283f2ef` → binding `8e8e54a3dc2f2c083831a230cbc5344694a79de5`. It correctly failed because the previous Next Action text would still order the TEST-0006 rerun after PASS.

That FAIL is preserved as evidence; the correction is transition-stable conditional routing, not replacing one hardcoded TEST state with another.

## Transition-stable TEST-0006 routing

`registry/tests/TEST-0006.yaml` is the **only** source of current TEST-0006 lifecycle/execution/result truth. PROJECT_STATE and WORK-0001 must not copy its current status or latest execution SHA as mutable state.

At every cold resume:

- read TEST-0006 first;
- if no valid current PASS covers the synchronized REVIEW-0026 handover, continue TEST-0006 legally through the minimum lifecycle needed to obtain exactly one qualifying execution;
- preserve any FAIL rather than hiding it;
- once a qualifying current PASS exists, **skip all further TEST-0006 reruns** and proceed directly to freezing that candidate and requesting the next fresh-context L2 + TEST-0008 cold read.

This rule is intentionally valid while TEST-0006 is FAIL, READY, RUNNING or PASS. Do not rerun merely to manufacture a newer SHA.

## Canonical acceptance contract

`registry/status-machines.yaml` version 9 remains canonical. `registry/content-identity.yaml` version 2 defines current byte-level REQUIREMENT_NORMATIVE_V1; `registry/acceptance-authority.yaml` version 1 is the authority matrix.

TEST-0008 remains the dedicated acceptance cold-read artifact. Never self-fill source, executor, outcomes, status or PASS result. Only a real fresh-context L2/L3 execution separated from authoring context and carrying every required explicit PASS outcome for the exact current digests may qualify it.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency mirror while WORK-0001 closes. Before editing or validating WORK-0002 implementation:

1. query live PR #2;
2. checkout `feat/work-0002-governance-ci` or its integrated successor;
3. re-read that branch's own WORK-0002;
4. only then traverse branch-local schemas, REVIEW-0002, TEST-0002/0003 and implementation docs.

Do not canonize volatile PR #2 HEAD/check/thread state here.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles protection/check/security hardening, not privatization.

## Next action

1. Keep WORK-0001/RUN-3 `IN_REVIEW`, REVIEW-0026/F-1/F-2/F-3 `OPEN`, REQ-0023/24/25 `PROPOSED`, and TEST-0008 unqualified.
2. Read `registry/tests/TEST-0006.yaml` for current lifecycle/result identity. Apply the transition-stable rule above: continue it only if no qualifying current REVIEW-0026 handover PASS exists; if one exists, skip directly to step 4.
3. For the qualifying TEST-0006 execution, verify REVIEW-0026 provenance + OPEN findings, PROJECT_STATE/WORK-0001 routing, content-identity v2/JCS, current TEST-0005/0007 chains, REQ-0023/24/25 exact PROPOSED/digest/TEST-0008 mappings, TEST-0008 non-qualification, independently resolvable owner authority, WORK-0002 branch boundary, live PR #2 after that boundary, and REQ-0010/TEST-0004 historical boundary. Independent YAML parsing of current WORK-0001 remains a required fresh-L2 check if it cannot be executed in the current runtime.
4. Freeze the resulting PR #3 candidate and request another fresh-context L2 on that exact SHA. The reviewer must independently parse WORK-0001, verify REVIEW-0026/F-1/F-2/F-3 corrections, recompute the three JCS digests, verify owner-authority evidence, verify post-PASS handover routing, inspect the full accumulated PR for P0/P1/P2, and separately record all five TEST-0008 cold-read outcomes.
5. Do not mutate the frozen candidate while review runs. If any material defect or cold-read outcome fails, import it truthfully and correct/re-prove. If clean/approval-capable and every TEST-0008 outcome is explicit PASS, preserve the new REVIEW provenance and materialize TEST-0008 from that external source before considering any requirement acceptance.
6. Resolve historical findings only when independently verified. Finalize WORK-0001/progress/completion and merge PR #3 only when every hard gate genuinely passes.
7. After PR #3 merge, integrate new main into PR #2, rerun its complete gate/fresh L2 and finish WORK-0002 before WORK-0003 and WORK-0004.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/tests/TEST-0006.yaml`
6. `registry/work-items/WORK-0001.yaml`
7. `registry/reviews/REVIEW-0026.yaml`
8. `registry/status-machines.yaml`
9. `registry/content-identity.yaml`
10. `registry/acceptance-authority.yaml`
11. `registry/requirements/REQ-0023.yaml` through `REQ-0025.yaml`
12. `registry/tests/TEST-0005.yaml`, `TEST-0007.yaml`, `TEST-0008.yaml`
13. `registry/work-items/WORK-0002.yaml` and `registry/progress/matrix.yaml`
14. live PR #3 reviews/threads and live PR #2 state

No prior chat history is required.
