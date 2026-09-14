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

## Latest fully proven author-side candidate

The latest substantive T7-corrected candidate with a complete author-side deterministic proof is
`52e1dd3aad0ee625f824440f9c87b920c58edec2`.

MONDE Gate run `34902136446` / run number **156** proved that exact PR HEAD against
`main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **244/244 tests PASS**;
- **2801/2801 statements** and **1374/1374 branches** covered, for **100.00% line + branch coverage**;
- baseline mutation smoke: **37/37 critical mutations killed**;
- fresh-L2/T7 mutation smoke: **26/26 critical mutations killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance: **0 errors**;
- path-safety validation: **0 errors**;
- graph-aware base-to-head change guard: **0 errors**;
- fresh-L2 hardening gate: **0 errors**;
- independent-review closure gate: **0 errors**;
- **T7 closure gate: 0 errors**;
- context manifest generated successfully;
- CodeQL: **success**;
- Dependency Review lane: **success**, with Dependency Graph availability still a bounded WORK-0003 administration concern.

The stable `MONDE / Merge Gate` checked out exact HEAD `52e1dd3aad0ee625f824440f9c87b920c58edec2`, verified the actual repository-owner identity/admin permission and the durable 46-finding cardinality, then failed closed for exactly two expected live conditions:

- `ERROR UNRESOLVED_THREADS: 46 unresolved review thread(s)`
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL: no independent GitHub APPROVED review is bound to the exact current PR HEAD`

Those failures are intentional. They prove that author-side success cannot be confused with independent closure.

The current branch may contain only metadata/evidence synchronization commits after `52e1dd3a…`. Re-query the live PR HEAD and checks before any review or merge decision; do not silently transfer Gate #156 proof to a later substantive implementation revision.

## WORK-0002 execution state

- T1, T2 and T3 are DONE.
- T5 — REVIEW-0030 correction, duplicate-key parser hardening and integration-provenance regression/mutation protection — is DONE.
- T6 — correction of the nine findings from GitHub Codex review `PRR_kwDOUUI5ts8AAAABNfhWLQ` plus subsequent five/six-finding hardening rounds — is DONE.
- **T7 — correction of the eight fresh findings from `PRR_kwDOUUI5ts8AAAABNiFSzA` — is DONE author-side and proven on `52e1dd3a…`.**
- **T4 — exact final-candidate proof plus approval-capable fresh independent L2 closure — is `IN_PROGRESS`.**
- WORK-0002 itself remains `IN_REVIEW`; AC-6 and completion remain open.

## Independent-review closure set

PR #2 has **46 intentionally unresolved material review threads/findings** at the latest verified live state. None may be author-resolved before independent verification.

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

1. deterministic governance checkout of the exact PR head, never the synthetic merge ref;
2. COMPLETE review approval-bearing semantics remain freshness-relevant/immutable;
3. accepted-finding authority evidence resolves the claimed actor, role and governed scope;
4. external review import binding equals the real first COMPLETE materialization commit;
5. requirement acceptance rejects unfinalized externally imported review evidence;
6. requirement cold-read evidence uses a real reachable execution revision;
7. progress matrix transitions/reopenings obey the canonical lifecycle after an exact adoption boundary;
8. squash provenance is historical-only, future-non-reusable and explicitly ID-scoped;
9. DONE work contains no unfinished implementation task or planned run.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNgjLtg` — five

1. requirement-acceptance reviews bind a real reviewed revision;
2. risk delegation evidence establishes actor, exact role and governed scope;
3. one-shot external TEST authorization applies to the actual existing-record transition;
4. externally imported PASS TEST evidence is fully bound/consumed before satisfying DONE;
5. context-manifest changes are computed from the PR merge base.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNgxnRw` — six

1. L2/L3 completion evidence requires substantive reviewer/context identity, checks, completion time and durable source provenance;
2. requirement-acceptance review independence derives from the owning WORK assurance/review floor, including A4 → L3;
3. requirement cold reads carry durable source/executor provenance;
4. historical non-initial import exceptions pre-exist materialization and remain exact/non-reusable;
5. progress reopening evidence is scoped to the affected progress/work surface;
6. project-owned L2 decision scripts are inside enforced 100% line+branch coverage.

### Fresh GitHub Codex `PRR_kwDOUUI5ts8AAAABNiFSzA` — eight

Reviewed exact candidate `09e4c89c31d6db7343b22d1e0b3badb7b9db7706` and required:

1. protect `registry/status-machines.yaml`, `registry/acceptance-authority.yaml` and `registry/content-identity.yaml` as predecessor-bound meta-governance trust anchors (`PRRT_kwDOUUI5ts6iSi_N`);
2. pin progress lifecycle/reopening adoption boundaries to immutable Git history (`PRRT_kwDOUUI5ts6iSi_R`);
3. require the same review to co-satisfy requirement scope/digest/revision/provenance/import/independence (`PRRT_kwDOUUI5ts6iSi_V`);
4. require the same cold-read TEST to co-satisfy floor/PASS/revision/qualification/outcomes/provenance (`PRRT_kwDOUUI5ts6iSi_a`);
5. bind requirement acceptance evidence to the exact content-identity policy revision (`PRRT_kwDOUUI5ts6iSi_b`);
6. anchor repository-owner proof to the actual workflow repository and real permission evidence (`PRRT_kwDOUUI5ts6iSi_h`);
7. require independent exact-HEAD approval in the live merge gate (`PRRT_kwDOUUI5ts6iSi_k`);
8. durably record the complete live closure set in WORK-0002 (`PRRT_kwDOUUI5ts6iSi_r`).

Gate #156 plus the T7 regression/mutation set proves the author-side implementation of those eight properties. **They remain open review debt until an independent fresh-context reviewer re-verifies them and the complete earlier set.**

## T7 implementation/proof state

T7 now enforces all eight `NiFSzA` properties without weakening earlier contracts:

- protected canonical policy amendments are authorized only from predecessor state, so candidate policy cannot self-authorize;
- lifecycle/reopening adoption points are derived from immutable Git introduction/activation history and checked against the canonical markers;
- requirement acceptance uses one qualifying review and one qualifying cold-read TEST, each satisfying its complete contract;
- review/cold-read evidence is bound to the exact content-identity policy revision;
- repository-owner authority is anchored to the actual Git remote plus reachable PASS real-GitHub permission proof;
- the live gate verifies real repository-owner/admin permission, durable finding cardinality and independent exact-HEAD APPROVED review;
- all eight properties have dedicated adversarial regressions and mutation targets.

The first T7 historical run exposed one overly specific adoption derivation: it found the later `review_closure_gate` wrapper instead of the first effective CI activation of `review_closure`. The corrected implementation derives the actual first effective activation and preserves canonical boundary `cf1a7a7e62d76acb21450d0e5ad3211352ec9f98`; Gate #156 then passed T7 closure with zero errors. No historical registry marker was rewritten to fit the implementation.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance surface and records only exact immutable history bridges. It does not weaken current-state validation.

Existing historical bridges cover:

- WORK-0001 PR #3 squash: source HEAD `2292b00fe04cbaf47cdd00df1578e1dab670d0cc`, integrated commit `29086643387ff46ab6636dd2fa3014efccc10165`, exact common tree `b89689ca631c0d64791904e74bf6672908b855c0`, explicitly eligible historical TEST IDs and `REVIEW-0027`;
- progress lifecycle-edge enforcement adoption at `cfa15015839acd34743318ffebbbe37185f46e10`;
- progress reopening-evidence enforcement adoption at `cf1a7a7e62d76acb21450d0e5ad3211352ec9f98`;
- historical malformed WORK-0004 and WORK-0002 YAML episodes with exact blob/repair commitments.

T7 now verifies the adoption boundaries against immutable Git history rather than trusting candidate-tree marker values.

## REVIEW-0030 provenance

REVIEW-0030 reviewed exact substantive candidate `cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc` and returned `CHANGES_REQUIRED`.
Its v10 one-shot import sequence remains historical evidence only:

1. authorization commit `1c7693b4a6ee7b003947599b0bf5ffefd444bcbd`;
2. review materialization/import commit `630604416bdccd3b07f57c011152e7fe14e0f2b4`;
3. metadata binding commit `788ade473e8c8c58604c019db7f0072322eb4074`;
4. authorization-consumption commit `0d4569b47e7e57f9141b95558bc4ae2c55124051`.

That imported review does not approve any later corrected candidate.

## Current WORK-0002 gate

Required sequence from this state:

1. Finish the evidence/handover synchronization for Gate #156 without changing substantive T7 implementation.
2. Re-query PR #2 and prove the exact resulting metadata HEAD with the complete MONDE Gate. A metadata-only descendant still needs its own current check state; Gate #156 remains the substantive implementation proof.
3. Keep **all 46 existing review threads unresolved**. Author-side proof never closes review debt.
4. Request a **new fresh-context independent L2** on that exact final candidate. The reviewer must recheck all 46 findings and actively search for new bypasses across governance trust anchors, adoption history, requirement/risk/test/review lifecycles, authority/provenance, context routing, GitHub live state, security, SRE and traceability.
5. Require an approval-capable independent result with no new blocking/material finding and an eligible GitHub `APPROVED` review bound to the exact current HEAD.
6. Only after independent verification may the corresponding threads/findings be resolved/closed and durable completion evidence be recorded.
7. Synchronize WORK-0002 completion, run the final exact-head merge candidate gate, and merge only with an exact-head guard.
8. Continue with WORK-0003, then WORK-0004.

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
14. live PR #2 exact HEAD, checks, reviews and all **46 unresolved review threads**
15. `tools/governance/`, `.github/scripts/` and `tests/governance/`

No prior chat history is required.
