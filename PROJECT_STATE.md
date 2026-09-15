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

## T10 closure state

Fresh-context GitHub Codex review `PRR_kwDOUUI5ts8AAAABNnPvYg` against exact candidate `9e4144d255590360f99652e59c38a02dbf95ccfa` opened four P1 findings covering review-state live-gate reruns, `registry/integration-provenance.yaml` trust-anchor protection, dependency-driven continuing ACCEPTED requirement revalidation, and dependency-driven continuing ACCEPTED risk revalidation.

T10 corrected all four and is now **DONE author-side**. The exact material review-thread closure set is **62 PRRT identities**, all still intentionally unresolved.

## Exact T10 proof chain

Substantive T10 SHA **`ef161b7e54c7f90433e1f303cdfd464827773870`** passed deterministic/security lanes in **MONDE Gate #190 / run `34962364980`**.

The synchronized descendant **`002926039c964e9e362b3c396a0d710323d9f1cf`** then passed deterministic/security lanes in **MONDE Gate #191 / run `34965242824`** with:

- **312/312 tests PASS**;
- **3482/3482 statements** and **1696/1696 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke **37/37**;
- fresh-L2/T7/T8/T9 mutation smoke **40/40**;
- dedicated T10 mutation smoke **5/5**;
- repository validator **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure, T7, T8, T9 and T10 closure validators **0 errors**;
- context manifest **19 MUST_READ files**;
- CodeQL **success**;
- Dependency Review lane **success**.

Most importantly, the live gate on `0029260...` no longer reports any durable finding-set mismatch. Exact durable/live identity equality is therefore established at **62/62**. It fails closed only on:

- `ERROR UNRESOLVED_THREADS: 62 unresolved review thread(s)`;
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL: no trusted, context-separated L2/L3 GitHub APPROVED review is bound to the exact current PR HEAD`.

This T10-closure metadata commit changes HEAD again and therefore must itself receive an exact-SHA MONDE Gate before the next independent review. No previous run is silently transferred to a later SHA.

## T10 implementation result

T10 now enforces that:

1. supported pull-request review and review-comment activity reruns the live gate, so approval/review activity cannot rely on an old successful check;
2. `registry/integration-provenance.yaml` is protected by base-preexisting independently authorized A3/A4 scope, alongside the other canonical policy trust anchors;
3. current ACCEPTED requirements are revalidated when their actual review/cold-read/owning-work/policy dependencies change even if the requirement file itself is untouched;
4. current ACCEPTED risks are revalidated when their authority/owning-work/policy dependencies change even if the risk file itself is untouched.

The implementation is deliberately dependency-driven. A rejected earlier T10 draft attempted to rejudge every historical ACCEPTED record under newer rules and correctly failed because that would create retroactive governance.

## WORK-0002 execution state

- T1, T2, T3, T5, T6, T7, T8, T9 and **T10** are DONE for their author-side scopes.
- **T4 — exact final-candidate proof plus fresh independent L2 closure — remains `IN_PROGRESS`.**
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` are restored to `DONE` after the exact T10 proof chain.
- `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending independent closure.

## Current WORK-0002 gate

Required sequence from this state:

1. Keep all **62** material review threads unresolved.
2. Prove the exact current T10-closure metadata HEAD with its own MONDE Gate; Gate #191 proves its parent, not this later SHA.
3. Confirm the live gate still reports exact durable/live equality and fails only on the 62 intentionally unresolved threads plus missing trusted context-separated exact-head approval.
4. Request another **fresh-context independent L2** on that exact proven HEAD. It must reverify all 62 accumulated findings, explicitly recheck all four T10 invariants and all earlier T7/T8/T9 closure invariants, and actively search for new lifecycle/import/authority/provenance/history/context/security/SRE/traceability bypasses.
5. If new material findings appear, reopen affected work/evidence again; do not resolve existing threads.
6. If semantic review is clean, obtain an eligible GitHub `APPROVED` review on the exact HEAD satisfying the hardened trusted/context-separated L2/L3 live-gate contract.
7. Only after both independent semantic verification and trusted exact-head approval may independently verified threads/findings be resolved, WORK-0002 completion be synchronized and the final exact-head merge gate be considered.
8. Merge with exact-head guard, then continue to WORK-0003 and WORK-0004.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance trust anchor because validators consume it as exact historical exception/adoption authority. Candidate state cannot make a same-PR exception self-authorizing. Existing WORK-0001 squash provenance, progress adoption records and malformed-YAML repair episodes remain exact historical-only, future-reuse-forbidden bridges.

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
11. live PR #2 exact HEAD, checks, reviews and all **62 unresolved review threads**
12. `.github/workflows/governance.yml`, `.github/workflows/_governance-core.yml`
13. `tools/governance/t7_closure.py`, `t8_closure.py`, `t9_closure.py`, `t10_closure.py`, `github_live_gate.py`
14. `.github/scripts/governance_t10_mutation_smoke.py`, `.github/scripts/governance_l2_mutation_smoke.py`
15. `tests/governance/test_t10_findings.py`, `test_t10_coverage.py` and prior T7/T8/T9 regression suites

No prior chat history is required.