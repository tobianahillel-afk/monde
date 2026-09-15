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

## T10 trigger

Fresh-context GitHub Codex review `PRR_kwDOUUI5ts8AAAABNnPvYg`, submitted on 2026-09-15 against exact candidate `9e4144d255590360f99652e59c38a02dbf95ccfa`, opened four new P1 findings:

1. rerun the merge gate when review/review-comment state changes so a prior green live check cannot become stale after later review activity;
2. treat `registry/integration-provenance.yaml` as a protected trust anchor so a candidate PR cannot authorize its own historical exception policy;
3. revalidate an already `ACCEPTED` requirement when one of its bound review/cold-read/owning-work/policy dependencies changes even if the requirement file itself is untouched;
4. revalidate an already `ACCEPTED` risk when its authority/owning-work/policy dependencies change even if the risk file itself is untouched.

The exact new thread identities are:

- `PRRT_kwDOUUI5ts6ieH4A`
- `PRRT_kwDOUUI5ts6ieH4C`
- `PRRT_kwDOUUI5ts6ieH4H`
- `PRRT_kwDOUUI5ts6ieH4L`

This expands the intentionally unresolved material closure set from 58 to **62**. None of these 62 threads is author-resolved.

## Exact T10 substantive candidate and proof

Exact T10 substantive candidate **`ef161b7e54c7f90433e1f303cdfd464827773870`** passed all deterministic/security lanes in GitHub Actions **MONDE Gate #190 / run `34962364980`** against `main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **312/312 tests PASS**;
- **3482/3482 statements** and **1696/1696 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke: **37/37 critical mutations killed**;
- fresh-L2/T7/T8/T9 mutation smoke: **40/40 critical mutations killed**;
- dedicated T10 mutation smoke: **5/5 critical mutations killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure, T7-closure, T8-closure, T9-closure and **T10-closure**: **0 errors**;
- context manifest: **19 MUST_READ files**;
- CodeQL: **success**;
- Dependency Review lane: **success**.

The live gate on `ef161b7...` observed exactly **62 unresolved review threads** and failed closed for the expected state:

- `ERROR UNRESOLVED_THREADS: 62 unresolved review thread(s)`;
- `ERROR DURABLE_FINDING_SET`: only the four T10 PRRT identities above were missing from the then-current 58-entry durable set, with `stale=[]`;
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL`: no trusted, context-separated L2/L3 GitHub `APPROVED` review was bound to the exact current PR HEAD.

This handover commit synchronizes the durable 62-thread set and truthfully reopens the implementation/test/real-system/handover dimensions invalidated by the new review. It is metadata, not independent completion evidence, and must receive its own exact-SHA Gate.

## T10 implementation result

T10 is author-side implemented but remains `IN_PROGRESS` until this synchronized metadata descendant is proven. The substantive implementation on `ef161b7...` now:

- protects `registry/integration-provenance.yaml` under the same base-preexisting authority rule as the other canonical policy trust anchors;
- performs **dependency-driven** continuing acceptance revalidation rather than naively rejudging every historical acceptance under later rules;
- projects the actual acceptance dependencies of each current ACCEPTED requirement/risk and reruns the invariant only when one of those dependencies changed;
- reruns the governance workflow on pull-request review and review-comment activity supported by GitHub Actions, while the live gate itself remains fail-closed on the exact current state;
- keeps all T7/T8/T9 historical adoption/provenance boundaries exact and non-reusable.

An earlier T10 draft attempted global revalidation of all ACCEPTED records and correctly failed because it would have retroactively imposed newer T9 rules on historical acceptances. That design was removed; current T10 is dependency-scoped.

## Independent-review closure set

There are **62 intentionally unresolved material review threads/findings**. Their exact GitHub PRRT identities are recorded one-for-one in `registry/work-items/WORK-0002.yaml` by this synchronization commit. Live GitHub remains authoritative for current resolved/unresolved state.

No thread has been author-resolved during T10 correction or synchronization.

## WORK-0002 execution state

- T1, T2, T3, T5, T6, T7, T8 and T9 are DONE for their author-side correction scopes.
- **T10 — four findings from `PRR_kwDOUUI5ts8AAAABNnPvYg` — is `IN_PROGRESS` pending exact-SHA proof of this synchronization descendant.**
- **T4 — exact final-candidate proof plus fresh independent L2 closure — remains `IN_PROGRESS`, downstream of T10.**
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` are reopened to `IN_REVIEW` until the synchronized T10 descendant is proven.
- `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending independent closure.

## Current WORK-0002 gate

Required sequence from this state:

1. Keep all **62** material review threads unresolved.
2. Prove this synchronized metadata descendant of `ef161b7...` with its **own exact-SHA MONDE Gate**. Gate #190 is SHA-bound and is not silently transferred to this later commit.
3. Confirm the live gate now reports exact durable/live PRRT-set equality and fails only on the 62 unresolved threads plus missing trusted context-separated exact-head approval.
4. If deterministic proof is green, synchronize T10 to `DONE` and restore only the author-side dimensions actually reproven (`implementation`, `tests`, `real_system_validation`, `handover`) before proving that metadata HEAD as well.
5. Then request another **fresh-context independent L2** on the exact resulting HEAD. The reviewer must reverify all 62 accumulated findings, explicitly recheck all four T10 invariants and every earlier T7/T8/T9 closure invariant, and actively search for new bypasses.
6. If new material findings appear, reopen affected work/evidence again; do not resolve threads.
7. If semantic review is clean, obtain an eligible GitHub `APPROVED` review on the exact HEAD satisfying the hardened trusted/context-separated L2/L3 contract.
8. Only after independent semantic verification and trusted exact-head approval may independently verified threads/findings be resolved, WORK-0002 completion be synchronized and the final exact-head merge gate be considered.
9. Merge with exact-head guard, then continue to WORK-0003 and WORK-0004.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is now explicitly treated as an A3 meta-governance trust anchor in T10 because it contains exact historical exception/adoption authority consumed by validators. Candidate state cannot make a same-PR historical exception self-authorizing; authority must come from the independently authorized predecessor boundary. Existing WORK-0001 squash provenance, progress adoption records and malformed-YAML repair episodes remain exact historical-only, future-reuse-forbidden bridges.

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