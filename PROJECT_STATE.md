# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **SUBLOT-0.1 / WORK-0001** is `DONE / A3` and was squash-merged to `main` as `29086643387ff46ab6636dd2fa3014efccc10165`.
- **SUBLOT-0.2 / WORK-0002** remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain planned downstream work. Do not start them before WORK-0002 is independently closed.

## Latest fully proven author-side implementation candidate

The latest fully proven author-side implementation candidate before this handover synchronization is
`965d484e7063d5c11c9964faa89bd7cf8d5aa75c`.

MONDE Gate run `34897096930` / run number **142** proved that exact PR HEAD against
`main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **219/219 tests PASS**;
- **2530/2530 statements** and **1282/1282 branches** covered, for **100.00% line + branch coverage**;
- project-owned `.github/scripts/governance_l2_followup.py`, `governance_l2_gate.py` and `governance_l2_hardening.py` are included in the enforced coverage source and each reports 100%;
- baseline mutation smoke: **37/37 killed**;
- fresh-L2 mutation smoke: **18/18 killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance: **0 errors**;
- path-safety validation: **0 errors**;
- graph-aware base-to-head change guard: **0 errors**;
- fresh-L2 hardening gate: **0 errors**;
- independent-review closure gate: **0 errors**;
- context manifest generated successfully with **19 MUST_READ files**;
- CodeQL: **success**;
- Dependency Review lane: **success**, with Dependency Graph availability still a bounded WORK-0003 administration concern.

The stable `MONDE / Merge Gate` verified all three lanes as green and then failed closed for exactly one live condition:

`ERROR UNRESOLVED_THREADS: 38 unresolved review thread(s)`

That red final check is intentional. It is not a deterministic implementation failure and must remain red until independent review closure.

This `PROJECT_STATE.md` update is a transition-stable handover synchronization descendant of the proven candidate above. Before any review or merge decision, re-query the live PR HEAD, exact-head checks, reviews and threads; do not treat this prose as live GitHub truth.

## WORK-0002 execution state

- T1, T2 and T3 are DONE.
- T5 — REVIEW-0030 correction, duplicate-key parser hardening and integration-provenance regression/mutation protection — is DONE.
- T6 — correction of the nine findings from GitHub Codex review `PRR_kwDOUUI5ts8AAAABNfhWLQ` plus exact-head/provenance/progress/DONE hardening — is DONE.
- The five findings from GitHub Codex review `PRR_kwDOUUI5ts8AAAABNgjLtg` and the six findings from review `PRR_kwDOUUI5ts8AAAABNgxnRw` have deterministic author-side corrections and regression coverage on Gate #142.
- T4 — exact final-candidate proof plus fresh independent L2 closure — remains IN_PROGRESS.
- WORK-0002 itself remains `IN_REVIEW`; AC-6 and completion remain open until an approval-capable independent review covers the final exact candidate.

## Independent-review closure set

PR #2 currently has **38 unresolved material review threads/findings**. None may be author-resolved before independent verification.

### Original six

1. A3/A4 assurance imposes minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. COMPLETE review evidence binds an exact immutable `artifact.commit_sha`.
3. PASS TEST records carry substantive protected-contract/case/execution evidence.
4. Every `NOT_APPLICABLE` progress dimension carries a non-empty justification.
5. Context routing seeds dependency closure from changed non-WORK registry records.
6. Handover state remains current and transition-stable.

### REVIEW-0029 — six

1. Canonical initial-state materialization plus exact historical/import exceptions.
2. Requirement `PROPOSED → ACCEPTED` content-bound independent-review and cold-read preconditions.
3. Concrete revision-bound execution evidence for PASS TEST completion evidence.
4. Canonical authority-matrix validation for accepted blocking findings.
5. Full immutable existing review commit IDs plus ancestry/freshness safety.
6. Required TEST contract freshness and PR merge-base endpoint semantics.

### REVIEW-0030 — six `R2_MAJOR`

1. Complete canonical `RISK → ACCEPTED` preconditions and authority resolution.
2. RFC 8785/JCS recomputation of `REQUIREMENT_NORMATIVE_V1` before acceptance.
3. Repository-owner authority evidence bound to the governed MONDE repository and established actor.
4. Finalized import binding plus one-shot authorization consumption before imported COMPLETE review evidence is eligible.
5. PASS TEST execution commit existence and relevant ancestry.
6. Exclusion of CLOSED reviews from completion evidence.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNfhWLQ` — nine

Reviewed exact candidate `5e4dd33995d17587be1452265b830f2b32e0f89b` and required:

1. deterministic governance checkout of the exact PR head, never the synthetic merge ref;
2. COMPLETE review approval-bearing semantics to remain freshness-relevant/immutable;
3. accepted-finding authority evidence to resolve the claimed actor, role and governed scope;
4. external review import binding to equal the real first COMPLETE materialization commit;
5. requirement acceptance to reject unfinalized externally imported review evidence;
6. requirement cold-read evidence to use a real reachable execution revision;
7. progress matrix transitions/reopenings to obey the canonical lifecycle after an exact adoption boundary;
8. squash provenance to be historical-only, future-non-reusable and explicitly ID-scoped;
9. DONE work to contain no unfinished implementation task or planned run.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNgjLtg` — five

Reviewed stale exact candidate `6e6f7a68ed63262e7ff9af56521695d79f6d015b` and added:

1. requirement-acceptance reviews must bind a real reviewed revision, not only a shaped SHA;
2. risk delegation evidence must establish actor, exact role and governed scope;
3. one-shot external TEST authorization must apply to the actual existing-record transition rather than an alternate initial state;
4. externally imported PASS TEST evidence must be fully bound/consumed before satisfying DONE;
5. context-manifest changes must be computed from the PR merge base.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNgxnRw` — six

The later fresh-context pass on the same stale candidate added:

1. L2/L3 completion evidence must contain substantive reviewer/context identity, checks, completion time and durable source provenance rather than trusting a declared independence level alone;
2. requirement-acceptance review independence must derive from the owning WORK assurance/review floor, including A4 → L3;
3. requirement cold reads must carry durable source/executor provenance;
4. historical non-initial import exceptions must pre-exist the materialization, be exact and non-reusable rather than retroactively blessing an invalid edge;
5. progress reopening evidence must be scoped to the affected progress/work surface rather than any unrelated finding/change;
6. the three project-owned L2 decision scripts must be inside the enforced 100% line+branch coverage source.

All 38 findings remain live review debt. Author-side tests, mutation proof and green deterministic gates are not independent approval.

## Latest closure hardening

The final author-side hardening adds `tools/governance/review_closure.py` and a fail-closed `review_closure_gate.py` covering the six latest review findings. The gate checks substantive L2/L3 review identity/provenance, requirement review floors derived from owning WORK assurance, cold-read source/executor provenance, pre-existing/non-reusable historical-import exceptions, and progress reopening evidence scoped to the affected surface.

True coverage was expanded to the project-owned L2 scripts. The initial measurement exposed real undercoverage (followup 56%, gate 42%, hardening 70%); targeted adversarial tests then raised all three to 100% line + branch without suppressing or excluding decision logic. Only `governance_l2_mutation_smoke.py` remains excluded because it is itself the mutation-test harness rather than production decision logic.

`PROGRESS_REOPENING_EVIDENCE_V1` has an exact adoption boundary at `cf1a7a7e62d76acb21450d0e5ad3211352ec9f98`, the first commit that activated `review_closure` in the deterministic workflow. This prevents a rule introduced later from fabricating invalidity in immutable pre-adoption history while enforcing every applicable post-adoption edge. The boundary is Git/path/activation-bound, `historical_only`, `future_reuse_forbidden`, and fails closed if moved, duplicated, missing or mismatched.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance surface and records only exact immutable history bridges. It does not weaken current-state validation.

It covers:

- WORK-0001 PR #3 squash: source HEAD `2292b00fe04cbaf47cdd00df1578e1dab670d0cc`, integrated commit `29086643387ff46ab6636dd2fa3014efccc10165`, exact common tree `b89689ca631c0d64791904e74bf6672908b855c0`, explicitly eligible historical TEST IDs and `REVIEW-0027`;
- exact adoption of progress lifecycle-edge enforcement at `cfa15015839acd34743318ffebbbe37185f46e10`;
- exact adoption of progress reopening-evidence enforcement at `cf1a7a7e62d76acb21450d0e5ad3211352ec9f98`;
- the historical malformed WORK-0004 blob introduced at `b63fc190a0fa3e02ad1b3e03d0d01b16617c9b49` and repaired at `94a6d2601179ccfde6eca7ed6b7e192dd640f2ca`;
- the historical malformed WORK-0002 YAML blob at `cab03c2b27e544212afe4fe52f38668d5fa0529d`, repaired immediately by `12105d7537cb0742b428c39929a3d79ad67edbac`.

Every exception/adoption bridge is exact, `historical_only`, `future_reuse_forbidden`, and fail-closed on any path/commit/blob/tree/ID/activation mismatch. Canonical current YAML and all post-adoption progress transitions remain fully enforced.

## REVIEW-0030 provenance

REVIEW-0030 reviewed exact substantive candidate `cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc` and returned `CHANGES_REQUIRED`.
Its v10 one-shot import sequence is historical evidence only:

1. authorization commit `1c7693b4a6ee7b003947599b0bf5ffefd444bcbd`;
2. review materialization/import commit `630604416bdccd3b07f57c011152e7fe14e0f2b4`;
3. metadata binding commit `788ade473e8c8c58604c019db7f0072322eb4074`;
4. authorization-consumption commit `0d4569b47e7e57f9141b95558bc4ae2c55124051`.

That imported review does not approve the corrected candidate.

## Current WORK-0002 gate

Required sequence from this state:

1. Re-query PR #2 and identify the exact live HEAD after this handover synchronization.
2. Require a complete MONDE Gate on that exact HEAD. Governance Core, Dependency Review and CodeQL must remain green; before independent closure the stable final gate is expected to fail only on the **38 unresolved review threads**.
3. Request a **fresh-context independent L2** on that exact final candidate. The reviewer must recheck all 38 findings, not only the latest six, and actively search for new bypasses.
4. The independent pass must specifically re-attack exact-head checkout, lifecycle/import/authority rules, substantive reviewer identity, requirement/cold-read provenance and assurance floors, RFC 8785/JCS identity, review/test materialization/finalization and Git ancestry, progress lifecycle/reopening adoption boundaries, squash/malformed-history provenance, DONE task/run terminality, enforced L2-script coverage, GitHub live-gate semantics, supply chain, security, SRE and traceability.
5. Keep every existing thread unresolved during the independent pass. Author-side proof is not approval.
6. If the L2 reports any new blocking/material finding, reopen implementation and correct it with exact regression/mutation proof.
7. Only an approval-capable independent result with no new blocking/material finding may become durable completion evidence and justify thread/finding closure.
8. After independent closure, synchronize WORK-0002 completion, run the final exact-head merge candidate gate, and merge only with an exact-head guard.
9. Continue with WORK-0003, then WORK-0004.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public visibility.

## Product/UI/UX owner gate

Product specification and product identity remain owner-gated decisions. Agents must not silently canonize product experience, UI/UX, visual identity, brand, color system, interface density, interaction language, emotional/psychovisual tone or other strong design choices. Major product-function decisions require explicit owner co-design rather than irreversible invention.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/progress/matrix.yaml`
7. `registry/status-machines.yaml`
8. `registry/acceptance-authority.yaml`
9. `registry/content-identity.yaml`
10. `registry/integration-provenance.yaml`
11. `registry/reviews/REVIEW-0029.yaml`
12. `registry/reviews/REVIEW-0030.yaml`
13. `registry/tests/TEST-0002.yaml`, `TEST-0003.yaml`, `TEST-0007.yaml`, `TEST-0008.yaml`
14. live PR #2 exact HEAD, checks, reviews and all 38 unresolved review threads
15. `tools/governance/`, `.github/scripts/` and `tests/governance/`

No prior chat history is required.
