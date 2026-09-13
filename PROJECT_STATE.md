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

The source review did **not** supply qualifying TEST-0008 evidence: `qualification_provided=false` and `explicit_outcomes_provided=false`. TEST-0008 therefore remains independent-only and unqualified.

### REVIEW-0026 provenance

- one-shot authorization: `018ae267f2b6c63636fdb5f7833f64b1fd68f11b`
- first materialization/import: `6075c1d87853f8c0c144e7d95bfa767ba476aa72`
- review-record import binding: `02968f1babd5015a1549efbac46f6ba182d3d910`
- authorization consumption: `d2b6d4a9b4db340d5934e5ee05b1a2d8d64e783c`

Git compare proves authorization → import is `ahead_by=1`; the sole added file is `registry/reviews/REVIEW-0026.yaml`. The authorization is consumed exactly by the first-materialization commit and cannot be reused.

## REVIEW-0026 corrections now present

Author corrections are present but do not resolve the findings without another independent review:

- F-1 correction: `REVIEW-0001/F-3` now uses `authority_evidence_type: GITHUB_REPOSITORY_OWNER_PERMISSION` and durable `authority_evidence_ref: https://api.github.com/repos/tobianahillel-afk/monde`. Live GitHub metadata independently identifies `owner.login=tobianahillel-afk`; collaborator permission is `admin`.
- F-2 correction: `registry/content-identity.yaml` version 2 binds REQUIREMENT_NORMATIVE_V1 to exact RFC 8785/JCS UTF-8 bytes, including deterministic string/key/number serialization, zero whitespace and fail-closed non-conformant serializers.
- F-3 correction: this handover begins with REVIEW-0026 and its current proof obligations; it no longer orders already-completed pre-REVIEW-0026 administration.

## Active requirement state

REQ-0020/0021/0022 remain `SUPERSEDED` premature-acceptance history. Active REQ-0023, REQ-0024 and REQ-0025 remain **PROPOSED**.

Current normative identities under REQUIREMENT_NORMATIVE_V1 / RFC 8785 JCS are unchanged:

- REQ-0023: `sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b`
- REQ-0024: `sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4`
- REQ-0025: `sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67`

Direct recomputation was repeated after content-identity v2. Git compare from the requirement-reading tree to the exact TEST-0005 test tree changed only TEST-0005, so the requirements did not move before verdict.

Requirement acceptance still requires both an exact-digest approval-capable independent review and separately qualified TEST-0008 cold-read evidence. No current review satisfies the approval half and TEST-0008 does not satisfy the cold-read half.

## Current revision-bound correction proof

The chains below are historical exact-SHA proof summaries, not mutable TEST state. Always read the TEST record first for current lifecycle/result identity.

- **TEST-0005 / content identity v2:** tree `27c4d591d165689e26d399b303722744919b3372` → PASS result `786a759a767ea8457d99eb8f528dc676964ca481` → binding `f6caaf77a2361f2f0724b6d91b1ce43da8c685f2`. It verifies RFC 8785/JCS byte-exact serialization, unchanged exact REQ-0023/24/25 digests, continued PROPOSED state, and that TEST-0008 remains the only acceptance cold-read path.
- **TEST-0007 / provenance + authority:** tree `b0d4b4f68f457a8f9e5bfbf689a9275c203a0715` → PASS result `592b88eb250f92a6e809c76f8646f85a894929b1` → binding `8e5edd80a634f552bbf92cd7da7088f9d6b06a2e`. It verifies REVIEW-0026 one-shot provenance, REQ-0006↔TEST-0007 traceability, matrix rules, and independently-resolvable GitHub owner/admin evidence for REVIEW-0001/F-3.
- The prior TEST-0006 chain `70d9a8a1… → 673d8f48… → 4f8cebee…` is historical for the pre-REVIEW-0026 handover. REVIEW-0026/F-3 proved that handover stale, so one new synchronized TEST-0006 execution is required after the current PROJECT_STATE + WORK-0001 + TEST-0005/0007 state is complete.

## Canonical acceptance contract

`registry/status-machines.yaml` version 9 remains canonical. `registry/content-identity.yaml` version 2 defines the current byte-level implementation of REQUIREMENT_NORMATIVE_V1; `registry/acceptance-authority.yaml` version 1 is the authority matrix.

TEST-0008 remains the dedicated acceptance cold-read artifact. Do not self-fill source, executor, outcomes, status or PASS result. Only a real fresh-context L2/L3 execution, separated from authoring context and carrying every required explicit PASS outcome for the exact current digests, may qualify it.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 remains only the globally readable lifecycle/dependency mirror while WORK-0001 closes. Before editing or validating WORK-0002 implementation:

1. query live PR #2;
2. checkout `feat/work-0002-governance-ci` or its integrated successor;
3. re-read that branch's own WORK-0002;
4. only then traverse its branch-local schemas, REVIEW-0002, TEST-0002/0003 and implementation docs.

Do not canonize volatile PR #2 HEAD/check/thread state here.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles protection/check/security hardening, not privatization.

## Next action

1. Keep WORK-0001/RUN-3 `IN_REVIEW`, REVIEW-0026/F-1/F-2/F-3 `OPEN`, REQ-0023/24/25 `PROPOSED`, and TEST-0008 unqualified.
2. Synchronize WORK-0001 with the completed current TEST-0005 and TEST-0007 chains without copying mutable TEST status/result fields.
3. Read `registry/tests/TEST-0006.yaml`. Because REVIEW-0026 materially changed the handover contract after its prior PASS, legally reopen and execute TEST-0006 **once** against the synchronized REVIEW-0026 PROJECT_STATE + WORK-0001 + current TEST-0005/0007 proof.
4. The TEST-0006 drill must verify at minimum: current WORK-0001 structure/lifecycle/completion state; this PROJECT_STATE's transition-stable routing; REVIEW-0026 exact provenance + three OPEN findings; content-identity v2/JCS; current TEST-0005/0007 chains; REQ-0023/24/25 still PROPOSED with exact digests and TEST-0008-only acceptance cold-read link; TEST-0008 still unqualified; PR #3 WORK-0002 mirror boundary; live PR #2 after explicit checkout boundary; current REQ-0010/TEST-0004 historical semantic boundary.
5. After exactly one qualifying current TEST-0006 PASS exists, freeze the resulting PR #3 candidate. Do not rerun merely to manufacture a newer SHA.
6. Request another fresh-context L2 on that exact frozen SHA. It must independently verify REVIEW-0026/F-1/F-2/F-3 corrections and separately record all five TEST-0008 cold-read outcomes against exact current digests.
7. Do not mutate the frozen candidate while that review is running. If any material defect/outcome fails, import it truthfully and repeat correction/proof. If the review is clean/approval-capable and all TEST-0008 outcomes are explicit PASS, preserve the new REVIEW provenance and materialize TEST-0008 from that external evidence before considering any REQ acceptance.
8. Resolve historical findings only when independently verified. Finalize WORK-0001/progress/completion and merge PR #3 only when every hard gate genuinely passes.
9. After PR #3 merge, integrate new main into PR #2, rerun its complete gate/fresh L2 and finish WORK-0002 before WORK-0003 and WORK-0004.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/reviews/REVIEW-0026.yaml`
7. `registry/status-machines.yaml`
8. `registry/content-identity.yaml`
9. `registry/acceptance-authority.yaml`
10. `registry/requirements/REQ-0023.yaml` through `REQ-0025.yaml`
11. `registry/tests/TEST-0005.yaml` through `TEST-0008.yaml`
12. `registry/work-items/WORK-0002.yaml` and `registry/progress/matrix.yaml`
13. live PR #3 reviews/threads
14. live PR #2 state

No prior chat history is required.
