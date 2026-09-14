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

The latest exact candidate with a complete author-side deterministic proof is
`09e4c89c31d6db7343b22d1e0b3badb7b9db7706`.

MONDE Gate run `34897431793` / run number **143** proved that exact PR HEAD against
`main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **219/219 tests PASS**;
- **2530/2530 statements** and **1282/1282 branches** covered, for **100.00% line + branch coverage**;
- project-owned `.github/scripts/governance_l2_followup.py`, `governance_l2_gate.py` and `governance_l2_hardening.py` were inside the enforced coverage source and each reported 100%;
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

The stable `MONDE / Merge Gate` verified all deterministic lanes and then failed closed on the then-live condition:

`ERROR UNRESOLVED_THREADS: 38 unresolved review thread(s)`

That candidate was then independently reviewed by GitHub Codex review `PRR_kwDOUUI5ts8AAAABNiFSzA`, which opened **8 new material findings**. Therefore Gate #143 is historical author-side proof of the pre-T7 implementation, not completion evidence for the new closure set.

The first handover-repair commit after that review is `a444a0ff5e98f242b236b2973c89947bed64a3e9`, which updates WORK-0002 with T7 and the complete 46-finding durable closure set. This PROJECT_STATE update is a metadata descendant of that handover repair. Re-query the live PR HEAD and checks before any implementation/review decision.

## WORK-0002 execution state

- T1, T2 and T3 are DONE.
- T5 — REVIEW-0030 correction, duplicate-key parser hardening and integration-provenance regression/mutation protection — is DONE.
- T6 — correction of the nine findings from GitHub Codex review `PRR_kwDOUUI5ts8AAAABNfhWLQ` plus subsequent five/six-finding hardening rounds — is DONE author-side.
- T7 — correction of the eight fresh findings from `PRR_kwDOUUI5ts8AAAABNiFSzA` — is `IN_PROGRESS`.
- T4 — exact final-candidate proof plus approval-capable fresh independent L2 closure — is `BLOCKED` on T7.
- WORK-0002 itself remains `IN_REVIEW`; AC-6 and completion remain open.

## Independent-review closure set

PR #2 currently has **46 unresolved material review threads/findings**. None may be author-resolved before independent verification.

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

Reviewed exact candidate `6e6f7a68ed63262e7ff9af56521695d79f6d015b` and added:

1. requirement-acceptance reviews must bind a real reviewed revision, not only a shaped SHA;
2. risk delegation evidence must establish actor, exact role and governed scope;
3. one-shot external TEST authorization must apply to the actual existing-record transition rather than an alternate initial state;
4. externally imported PASS TEST evidence must be fully bound/consumed before satisfying DONE;
5. context-manifest changes must be computed from the PR merge base.

### GitHub Codex `PRR_kwDOUUI5ts8AAAABNgxnRw` — six

The later pass on the same candidate added:

1. L2/L3 completion evidence requires substantive reviewer/context identity, checks, completion time and durable source provenance;
2. requirement-acceptance review independence derives from the owning WORK assurance/review floor, including A4 → L3;
3. requirement cold reads carry durable source/executor provenance;
4. historical non-initial import exceptions pre-exist materialization and remain exact/non-reusable;
5. progress reopening evidence is scoped to the affected progress/work surface;
6. project-owned L2 decision scripts are inside enforced 100% line+branch coverage.

### Fresh GitHub Codex `PRR_kwDOUUI5ts8AAAABNiFSzA` — eight

Reviewed exact candidate `09e4c89c31d6db7343b22d1e0b3badb7b9db7706` and added:

1. `registry/status-machines.yaml`, `registry/acceptance-authority.yaml` and `registry/content-identity.yaml` are canonical policy trust anchors and must be protected as meta-governance; candidate policy must not self-authorize its own weakening (`PRRT_kwDOUUI5ts6iSi_N`).
2. Progress lifecycle/reopening adoption boundaries must be pinned to immutable predecessor history rather than trusting a mutable marker from the candidate tree (`PRRT_kwDOUUI5ts6iSi_R`).
3. The **same review** must satisfy requirement scope, digest, reviewed revision, provenance/import rules and the owning-WORK independence floor (`PRRT_kwDOUUI5ts6iSi_V`).
4. The **same cold-read TEST** must satisfy independence floor, PASS/result provenance, exact requirement revision, qualification and all required outcomes (`PRRT_kwDOUUI5ts6iSi_a`).
5. Requirement acceptance evidence must bind the exact `content-identity` policy revision and become stale when that policy changes even if the digest string remains equal (`PRRT_kwDOUUI5ts6iSi_b`).
6. Repository-owner proof must be anchored to the actual workflow repository and real permission artifact/execution evidence, not agreement among mutable policy fields (`PRRT_kwDOUUI5ts6iSi_h`).
7. The live merge gate must require an eligible independent approval on the **exact HEAD**, including reviewer identity/independence, rather than treating resolved threads as approval (`PRRT_kwDOUUI5ts6iSi_k`).
8. WORK-0002 must durably record the complete per-finding closure set; its previous `open_findings` stopped at 27 despite PROJECT_STATE reporting 38 (`PRRT_kwDOUUI5ts6iSi_r`). WORK-0002 now records all 46 live findings.

All 46 findings remain live review debt. Author-side tests, mutation proof and green deterministic gates are not independent approval.

## T7 correction target

T7 must correct the eight `NiFSzA` findings without weakening earlier contracts. In particular:

- protect the three canonical policy registries using predecessor-bound meta-governance semantics rather than simply adding them to a mutable candidate allowlist;
- make both progress-adoption boundaries immutable/pre-existing relative to the edge they govern;
- unify review acceptance so one qualifying review satisfies all semantic + independence + provenance checks;
- unify cold-read acceptance so one qualifying TEST satisfies all semantic + provenance + independence checks;
- bind acceptance evidence to the exact content-identity policy revision;
- anchor repository-owner authority to actual GitHub repository/permission evidence;
- extend the live merge gate so an approval-capable independent exact-HEAD review is mandatory in addition to resolved threads;
- preserve the complete 46-finding durable closure set.

Every new property requires adversarial regression and mutation protection before T7 can become DONE.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance surface and records only exact immutable history bridges. It does not weaken current-state validation.

Existing historical bridges cover:

- WORK-0001 PR #3 squash: source HEAD `2292b00fe04cbaf47cdd00df1578e1dab670d0cc`, integrated commit `29086643387ff46ab6636dd2fa3014efccc10165`, exact common tree `b89689ca631c0d64791904e74bf6672908b855c0`, explicitly eligible historical TEST IDs and `REVIEW-0027`;
- progress lifecycle-edge enforcement adoption at `cfa15015839acd34743318ffebbbe37185f46e10`;
- progress reopening-evidence enforcement adoption at `cf1a7a7e62d76acb21450d0e5ad3211352ec9f98`;
- historical malformed WORK-0004 and WORK-0002 YAML episodes with exact blob/repair commitments.

Fresh L2 `NiFSzA` established that merely reading an adoption SHA from candidate HEAD is insufficient. T7 must validate those adoption points against immutable predecessor history, not simply preserve the existing fields.

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

1. Re-query PR #2 and identify the exact live HEAD after this handover synchronization.
2. Correct T7's eight findings at the smallest responsible layers; do not resolve any review thread.
3. Add adversarial regressions and mutation targets for all eight properties, including candidate-self-authorization attacks and split-evidence attacks.
4. Obtain a complete exact-HEAD MONDE Gate: 100% project-owned line+branch coverage, all mutation targets killed, repository/strict/path/change/L2-hardening/review-closure gates at zero, context manifest success, CodeQL success and Dependency Review success.
5. Synchronize TEST/WORK/PROJECT_STATE/PR metadata only after that exact candidate is proven.
6. Request a new fresh-context independent L2 on the exact final candidate. The reviewer must recheck **all 46 findings** and actively search for new bypasses.
7. Keep every existing thread unresolved during the independent pass. Author-side proof is not approval.
8. Only an approval-capable independent result with no new blocking/material finding may become durable completion evidence and justify thread/finding closure.
9. After independent closure, synchronize WORK-0002 completion, run the final exact-head merge candidate gate, and merge only with an exact-head guard.
10. Continue with WORK-0003, then WORK-0004.

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
