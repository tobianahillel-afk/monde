# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions. Mutable TEST lifecycle/result truth lives only in each `registry/tests/TEST-*.yaml` record.

## Current phase / lot / blocker

- **PHASE-0 — Specification, repository governance and canonical documentation**
- **LOT-0 — AI-first repository operating system**
- **SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**
- `WORK-0001` remains `IN_REVIEW` on PR #3 / `chore/work-0001-assurance-closure` and blocks truthful completion of WORK-0002.
- `WORK-0002` remains a separate open PR #2 / `feat/work-0002-governance-ci`, lifecycle `IN_REVIEW`; query its live HEAD/check/thread state and checkout that branch before traversing branch-local implementation evidence.
- WORK-0003 and WORK-0004 have not started.

PR #1 remains historically squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`.

## Current assurance state

The durable corrective review chain now reaches **REVIEW-0025**. No negative review finding is closed by author assertion.

REVIEW-0025 is fresh-context L2 on exact prior candidate `e405c977f9de58cd4d88849784d425de6a61cd1d`, outcome `CHANGES_REQUIRED`, with three R2 findings still `OPEN`:

1. **F-1 — exact requirement-content binding:** review/cold-read proof must bind the exact normative requirement content eventually accepted; remaining `PROPOSED` is not enough if normative content changes.
2. **F-2 — real fresh-context cold read:** a generic or author-run PASS TEST must not satisfy the cold-read half of requirement acceptance.
3. **F-3 — machine-resolvable acceptance authority:** risk/finding acceptance authority cannot be arbitrary role/evidence prose; an exact authority matrix and typed evidence are required.

REVIEW-0025 one-shot provenance is fixed and consumed:

- authorization: `cf03475f68ea7c62dcd5852bffa92e80490af90b`;
- first materialization: `a44296d3e02cc74fa511a471e560e63e75a1cf30`;
- review import binding: `afd3c7514588b72fdb541a41b2b9bdfbba37932b`;
- authorization consumption: `cefad8c76bff96b7c903e602e708685313232323`.

Git ancestry has been rechecked: authorization → import is `ahead_by=1`, and that sole commit adds `registry/reviews/REVIEW-0025.yaml`.

## Canonical lifecycle contract — v9

`registry/status-machines.yaml` **version 9** is canonical.

v9 preserves all exact historical lifecycle/import/replay rules from earlier versions and adds three enforceable primitives:

### 1. Normative requirement identity

`registry/content-identity.yaml` defines `REQUIREMENT_NORMATIVE_V1`.

- SHA-256 is computed over a deterministic nested projection of the declared normative fields only.
- lifecycle/provenance/evidence-link fields are excluded.
- changing any included normative field changes the digest and invalidates review/cold-read proof bound to the old digest.
- missing paths, digest mismatch or implementation-defined projection fail closed.

Current active AC-5 owners remain `PROPOSED` with these normative identities:

- REQ-0023: `sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b`
- REQ-0024: `sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4`
- REQ-0025: `sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67`

Their normative statements were not changed by the v9 correction.

### 2. Qualified fresh-context cold read

Requirement acceptance now uses `verification.acceptance_cold_read_test_ids`, not any generic PASS in `verification.test_ids`.

`TEST-0008` is the dedicated acceptance cold-read artifact. It protects REQ-0023/24/25 and binds the three exact digests above, but it must remain non-qualifying until a real fresh-context L2/L3 execution supplies:

- durable source review identity + submission time;
- executor/context identity;
- `fresh_context=true` and `authoring_context_separated=true`;
- exact digest + `PROPOSED` status for each requirement;
- explicit PASS for every required cold-read outcome;
- exact execution SHA.

Do not fabricate or self-fill these fields before such an external execution exists.

### 3. Machine-resolvable acceptance authority

`registry/acceptance-authority.yaml` version 1 is the single authority policy for residual risks and accepted blocking findings.

- role names and evidence types use closed vocabularies;
- allowed roles resolve from assurance + impact/category for risks and assurance + finding severity for findings;
- category overrides, including SECURITY, take precedence over default rules;
- evidence type must be allowed for the role and the durable evidence reference must establish that actor's role/delegation;
- unknown role/evidence/matrix/rule fails closed.

The historical accepted REVIEW-0001/F-3 decision remains intact and is now typed as `REPOSITORY_OWNER` / `EXPLICIT_REPOSITORY_OWNER_DECISION` / matrix v1 / `FINDING:A3:R2_MAJOR`. GitHub repository metadata currently identifies `tobianahillel-afk` as repository owner and collaborator permission was reverified as `admin`.

## Current v9 proof already executed

These chains are **historical exact-SHA evidence**, not a second mutable TEST registry. Always read the TEST record for current lifecycle state.

### TEST-0005 — v9 requirement-content / acceptance guard

The first v9 execution intentionally failed closed because the initial declared digests did not recompute:

- tree `ed716f93116f1d121ed7aa54174b8bdbf1030513`
- FAIL `df5e766a32cdd5782fdd727e38d73c8b7e8e7355`
- binding `2b3338f500015f100e0a3ab477b95ae111e99c4e`

The projection contract and digests were corrected rather than rewriting that failure. Corrected execution:

- tree `1562acdff730d832770befdbfe296615fac2a544`
- PASS `7abdfbd0655e96239d8ddb511f3edfc0b19571f7`
- binding `ae89cf9fd1252ec50e537f014983b3979c44a6ad`

This proves deterministic digest recomputation, stale-proof rejection semantics and the TEST-0008 qualification boundary. **It is author-run machine-guard proof, not acceptance cold-read evidence.**

### TEST-0007 — v9 lifecycle / external-import / authority proof

- tree `278da4e4f14a9897fa746d29725c8f666b6add2c`
- PASS `61c64a2c0920a28949377b75aa9df92637aeb371`
- binding `8288143e2915498a06d0a18db8ffbaa607fac948`

It re-proves prior exact lifecycle/import/replay guarantees under v9, REVIEW-0025 one-shot provenance, REQ-0006↔TEST-0007 traceability, matrix rule resolution, SECURITY overrides and REVIEW-0001/F-3 typed owner authority.

## Requirement acceptance remains blocked

REQ-0020/0021/0022 remain `SUPERSEDED` premature-acceptance history. REQ-0023/0024/0025 remain the active AC-5 owners and **must remain `PROPOSED`**.

Each current requirement points to TEST-0008 through `verification.acceptance_cold_read_test_ids` and keeps general verification links to TEST-0005/0006/0008.

A future `PROPOSED → ACCEPTED` transition is valid only if, for the exact current normative digest:

1. a `COMPLETE` approval-capable independent review includes the requirement and binds that exact digest in `scope.requirement_revisions`; and
2. a PASS TEST referenced by `acceptance_cold_read_test_ids` explicitly qualifies as L2/L3 fresh-context authoring-separated cold-read evidence with the same digest and all required outcomes PASS.

REVIEW-0018, REVIEW-0024 and REVIEW-0025 are negative evidence and cannot satisfy the approval half. TEST-0005/0006 are not substitutes for TEST-0008.

## TEST-0006 handover routing

`registry/tests/TEST-0006.yaml` is the **only** source of current TEST-0006 lifecycle/execution/result truth. Do not duplicate its current status or latest execution SHA here or in WORK-0001.

REVIEW-0025/v9 changed the handover contract after the prior v8 TEST-0006 PASS. Therefore the current workflow is conditional:

- read TEST-0006 first;
- if no valid execution covers the synchronized REVIEW-0025/v9 WORK-0001 + PROJECT_STATE handover, legally reopen/execute it exactly once through the minimum required lifecycle;
- preserve any FAIL rather than hiding it;
- after one qualifying current PASS exists, do not rerun merely to manufacture a newer SHA.

The v9 TEST-0006 drill must verify at least:

- WORK-0001 parses as YAML, remains A3/IN_REVIEW and exposes REVIEW-0025/v9/TEST-0008 without duplicating mutable test state;
- this PROJECT_STATE routes the same current work and contains no mutable TEST state copy;
- status-machine v9, `content-identity.yaml` and `acceptance-authority.yaml` resolve;
- REVIEW-0025 provenance is exact and F-1/F-2/F-3 remain OPEN;
- TEST-0005 and TEST-0007 v9 proof chains resolve;
- REQ-0023/24/25 remain PROPOSED, their declared digests recompute, each points to TEST-0008 as its acceptance cold read, and TEST-0008 protects all three while remaining unqualified before independent execution;
- existing REQ-0023/24/25 ↔ TEST-0006 general traceability remains reciprocal;
- PR #3 WORK-0002 mirror remains locally resolvable without branch-only proof/schema leakage;
- after the explicit branch boundary, live PR #2 remains coherent;
- current REQ-0010/TEST-0004 historical semantic boundary remains correct.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency mirror while WORK-0001 closes. Before editing/validating WORK-0002 implementation:

1. query live PR #2;
2. checkout `feat/work-0002-governance-ci` or its integrated successor;
3. re-read that branch's own WORK-0002;
4. only then traverse its branch-local schemas, REVIEW-0002, TEST-0002/0003 and implementation docs.

Do not canonize volatile PR #2 HEAD/check/thread state in this handover.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 handles protection/check/security hardening, not privatization.

## Next action

1. Keep WORK-0001 `IN_REVIEW`, REVIEW-0025/F-1/F-2/F-3 `OPEN`, and REQ-0023/24/25 `PROPOSED`.
2. Synchronize WORK-0001 with this REVIEW-0025/v9 handover without copying mutable TEST status/result fields.
3. Read TEST-0006. Because v9 materially extends its proof obligations, legally reopen and run it once against the synchronized WORK/PROJECT_STATE tree unless its record already contains a valid v9 execution.
4. After one qualifying TEST-0006 PASS exists, freeze that exact PR #3 candidate.
5. Request a fresh-context L2 on that exact SHA. The request must independently inspect the full accumulated PR and also perform the TEST-0008 cold-read questions for REQ-0023/24/25 against their exact normative digests.
6. Do not mutate the frozen candidate while that external review/cold-read is running.
7. If the reviewer finds any defect, import it truthfully, correct and re-prove. If it is clean/approval-capable and the cold-read outcomes are explicitly PASS, first preserve one-shot REVIEW provenance, then materialize/bind the TEST-0008 execution from that external source. Only afterward may qualifying review evidence be added to the three requirements and their no-content-change `PROPOSED → ACCEPTED` transitions be considered.
8. Resolve historical findings only when the clean independent review actually verifies their corrections; then finalize WORK-0001/progress/completion and merge PR #3 if every gate is genuinely satisfied.
9. After PR #3 merge, integrate new `main` into PR #2, rerun its full gate/fresh L2 and finish WORK-0002 before WORK-0003 and WORK-0004.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/status-machines.yaml`
7. `registry/content-identity.yaml`
8. `registry/acceptance-authority.yaml`
9. `registry/requirements/REQ-0023.yaml` through `REQ-0025.yaml`
10. `registry/reviews/REVIEW-0025.yaml` plus earlier open-finding reviews as needed
11. `registry/tests/TEST-0005.yaml` through `TEST-0008.yaml`
12. `registry/work-items/WORK-0002.yaml` and `registry/progress/matrix.yaml`
13. live PR #3 reviews/threads and live PR #2 state

No prior chat history is required.
