# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **SUBLOT-0.1 / WORK-0001** is `DONE / A3` and was squash-merged to `main` as `29086643387ff46ab6636dd2fa3014efccc10165`.
- **SUBLOT-0.2 / WORK-0002** remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain planned downstream work.

## Latest proven WORK-0002 author-side candidate

The latest fully proven substantive author-side candidate is `42e4e93c0e25294b26d2a00d958660c9124697d1`.
MONDE Gate run `34868556415` / run number 113 proved that exact SHA against
`main@29086643387ff46ab6636dd2fa3014efccc10165`:

- 147/147 governance tests PASS;
- 1578/1578 statements and 818/818 branches covered, for 100% line + branch coverage;
- 37/37 critical governance mutations killed;
- repository validator: 0 errors / 0 warnings across 67 records;
- strict governance: 0 errors;
- path-safety validation: 0 errors;
- base-to-head change guard: 0 errors;
- context manifest generated successfully with 19 MUST_READ files;
- CodeQL: success;
- Dependency Review lane: success, with Dependency Graph availability still a bounded WORK-0003 administration concern.

The stable `MONDE / Merge Gate` then failed closed for exactly one live condition:
`ERROR UNRESOLVED_THREADS: 18 unresolved review thread(s)`. Lane verification itself was green.

A later branch HEAD may be a metadata-only synchronization descendant of this proven implementation candidate. Before any review or merge decision,
re-query the live PR HEAD, checks, reviews and threads; do not treat this prose as live GitHub truth.

## WORK-0002 execution state

- T1, T2 and T3 are DONE.
- T5 — REVIEW-0030 correction, duplicate-key parser hardening and integration-provenance regression/mutation protection — is DONE by the exact proof above.
- T4 — exact final-candidate proof plus fresh independent L2 closure — is now IN_PROGRESS.
- WORK-0002 itself remains `IN_REVIEW`; AC-6 and completion remain open until independent review is approval-capable.

## Independent-review closure set

PR #2 has **18 unresolved material review threads/findings**. None may be author-resolved before independent verification.

The first six require:

1. A3/A4 assurance to impose minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. COMPLETE review evidence to bind an exact immutable `artifact.commit_sha`.
3. PASS TEST records to carry substantive protected-contract/case/execution evidence.
4. Every `NOT_APPLICABLE` progress dimension to carry a non-empty justification.
5. Context routing to seed dependency closure from changed non-WORK registry records.
6. Handover state to remain current and transition-stable.

REVIEW-0029 added six further findings requiring:

1. canonical initial-state materialization plus exact historical/import exceptions;
2. requirement `PROPOSED → ACCEPTED` content-bound independent-review and cold-read preconditions;
3. concrete revision-bound execution evidence for current PASS TEST completion evidence;
4. canonical authority-matrix validation for accepted blocking findings;
5. full immutable existing review commit IDs plus ancestry/freshness safety;
6. required TEST contract freshness and PR merge-base endpoint semantics.

REVIEW-0030 added six `R2_MAJOR` findings requiring:

1. complete canonical `RISK → ACCEPTED` preconditions and authority resolution;
2. RFC 8785/JCS recomputation of `REQUIREMENT_NORMATIVE_V1` before acceptance;
3. repository-owner authority evidence bound to the governed MONDE repository and established actor;
4. finalized import binding plus one-shot authorization consumption before imported COMPLETE review evidence is eligible;
5. PASS TEST execution commit existence and relevant ancestry;
6. exclusion of CLOSED reviews from completion evidence.

All 18 remain live review debt until a fresh independent L2 rechecks the final exact candidate.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance surface and records only exact immutable history bridges. It does not weaken current-state validation.

It currently covers:

- the WORK-0001 PR #3 squash boundary: source HEAD `2292b00fe04cbaf47cdd00df1578e1dab670d0cc`, integrated commit
  `29086643387ff46ab6636dd2fa3014efccc10165`, exact common tree `b89689ca631c0d64791904e74bf6672908b855c0`, limited to the explicitly eligible historical TEST IDs;
- the historical malformed WORK-0004 blob introduced at `b63fc190a0fa3e02ad1b3e03d0d01b16617c9b49` and repaired at
  `94a6d2601179ccfde6eca7ed6b7e192dd640f2ca`;
- the historical malformed WORK-0002 YAML blob at `cab03c2b27e544212afe4fe52f38668d5fa0529d`, repaired immediately by
  `12105d7537cb0742b428c39929a3d79ad67edbac`.

Every exception is path/commit/blob/tree-bound as applicable, `historical_only`, `future_reuse_forbidden`, and fail-closed on any mismatch.
Canonical current YAML still rejects duplicate mapping keys and malformed syntax.

## REVIEW-0030 provenance

REVIEW-0030 reviewed exact substantive candidate `cbc2dfc065e73b9086d13a483b8b693ddc2fa6cc` and returned `CHANGES_REQUIRED`.
Its v10 one-shot import sequence is historical evidence only:

1. authorization commit `1c7693b4a6ee7b003947599b0bf5ffefd444bcbd`;
2. review materialization/import commit `630604416bdccd3b07f57c011152e7fe14e0f2b4`;
3. metadata binding commit `788ade473e8c8c58604c019db7f0072322eb4074`;
4. authorization-consumption commit `0d4569b47e7e57f9141b95558bc4ae2c55124051`.

That imported review does not approve the corrected candidate. A new fresh-context L2 is required.

## Current WORK-0002 gate

Required sequence from this state:

1. Re-query PR #2 and verify the current metadata-synchronized HEAD is a descendant of the proven `42e4e93c...` implementation candidate.
2. Require a complete MONDE Gate on that exact live HEAD. Deterministic lanes must remain green; before independent closure the live final gate is expected to fail only on the same 18 unresolved review threads.
3. Request a **fresh-context independent L2** on that exact final candidate. The reviewer must recheck all 18 findings and independently inspect the integration-provenance hardening, parser behavior, lifecycle/authority rules, review freshness, GitHub trust boundaries, supply chain, security, SRE and traceability.
4. Keep every existing thread unresolved during the independent pass. Author-side proof is not approval.
5. If the L2 reports any new blocking/material finding, reopen implementation and correct it with exact regression/mutation proof.
6. Only an approval-capable independent result with no new blocking finding may be imported as durable completion evidence and justify thread/finding closure.
7. After independent closure, synchronize WORK-0002 completion, run the final exact-head merge candidate gate, and merge only with an exact-head guard.
8. Continue with WORK-0003, then WORK-0004.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data.
Sensitive runtime material remains outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public visibility.

## Product/UI/UX owner gate

Product specification and product identity remain owner-gated decisions. Agents must not silently canonize product experience, UI/UX, visual identity,
brand, color system, interface density, interaction language, emotional/psychovisual tone or other strong design choices. Major product-function decisions
require explicit owner co-design rather than irreversible invention.

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
13. `registry/tests/TEST-0002.yaml`, `TEST-0003.yaml`, and `TEST-0007.yaml`
14. live PR #2 HEAD, checks, reviews and all review threads
15. `tools/governance/` and `tests/governance/`

No prior chat history is required.
