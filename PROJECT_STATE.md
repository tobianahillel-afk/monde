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

## Exact T9 substantive candidate and proof

Exact substantive T9 candidate **`3da4047cacaaad4962b647a6625767001d328027`** passed GitHub Actions **MONDE Gate #178 / run `34952991296`** against `main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **291/291 tests PASS**;
- **3313/3313 statements** and **1624/1624 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke: **37/37 critical mutations killed**;
- fresh-L2/T7/T8/T9 mutation smoke: **39/39 critical mutations killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure, T7-closure, T8-closure and **T9-closure**: **0 errors**;
- context manifest: **19 MUST_READ files**;
- CodeQL: **success**;
- Dependency Review lane: **success**.

The stable live merge gate on this pre-synchronization substantive candidate observed exactly **58 unresolved review threads** with `stale=[]`. It failed closed for three expected conditions:

- `ERROR UNRESOLVED_THREADS: 58 unresolved review thread(s)`;
- `ERROR DURABLE_FINDING_SET`: the then-stale WORK-0002 list had not yet been synchronized to the exact 58 live PRRT identities;
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL`: no trusted, context-separated L2/L3 GitHub APPROVED review was bound to the exact current PR HEAD.

The deterministic proof is green; the live red gate is intentional until metadata synchronization, fresh independent verification and eligible exact-head approval are complete.

## T9 result

Fresh-context review `PRR_kwDOUUI5ts8AAAABNmehrQ` on exact candidate `061c17e7144396cbfd01963fb4036f3fc3c58ed3` added six material findings. T9 now implements and mutation-protects all six:

1. content-identity stability checks the **full merge history**, so a side-branch policy revision followed by revert/merge cannot disappear through history simplification;
2. continuing ACCEPTED requirement evidence requires imported review and cold-read evidence to remain fully finalized, not merely syntactically present;
3. external review `import_commit` may bind exactly once from `null` to the exact earlier first-COMPLETE materialization SHA under matching prior preauthorization, then becomes immutable; later qualification still requires one-shot authorization consumption;
4. protected-policy amendments require authority from **base-preexisting**, independently approved active A3/A4 work scope rather than scope added earlier in the same PR;
5. WORK `DONE -> IN_REVIEW` reopening requires a genuinely newly added finding/evidence identity or newly approved scope-change event for the target WORK;
6. the durable closure set is compared to GitHub by exact unique **PRRT identity set**, never by count alone.

The historical REVIEW-0029 and REVIEW-0030 import sequence was explicitly revalidated: the binding commit writes the SHA of the preceding first COMPLETE materialization commit, while authorization consumption occurs separately. T9 distinguishes this bounded legitimate binding from later evidence eligibility without creating a reusable bypass.

T9 is therefore **DONE author-side** on exact substantive SHA `3da4047c...`. This is implementation proof, not independent review approval.

## Independent-review closure set

There are **58 intentionally unresolved material review threads/findings**. Their exact GitHub PRRT identities are now durably recorded one-for-one in `registry/work-items/WORK-0002.yaml`; live GitHub remains authoritative for current resolved/unresolved state.

No thread has been author-resolved during T9 correction or synchronization.

## WORK-0002 execution state

- T1, T2, T3, T5, T6, T7, T8 and **T9** are DONE for their author-side correction scopes.
- **T4 — exact metadata-candidate proof plus fresh independent L2 closure — remains `IN_PROGRESS`.**
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` are DONE based on the exact T9 proof plus this synchronized handover.
- `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending independent closure.

## Current WORK-0002 gate

Required sequence from this state:

1. Keep all **58** material review threads unresolved.
2. Prove this metadata-synchronization descendant of `3da4047c...` with its **own exact-SHA MONDE Gate**. Gate #178 is SHA-bound and is not silently transferred to later metadata commits.
3. The metadata-head live gate should then show exact durable/live identity equality and fail only on the still-unresolved 58 threads plus missing independent exact-head approval.
4. Once that metadata HEAD is deterministic-green, request another **fresh-context independent L2** on that exact HEAD. The reviewer must reverify all 58 accumulated findings, explicitly recheck all six T9 invariants and every earlier closure invariant, and actively search for new bypasses.
5. If new material findings appear, reopen the affected work/evidence again; do not resolve threads.
6. If semantic review is clean, obtain an eligible GitHub `APPROVED` review on the exact HEAD that satisfies the hardened trusted/context-separated L2/L3 live-gate contract. A shallow approval from an arbitrary external account is insufficient.
7. Only after both independent semantic verification and trusted exact-head approval may independently verified threads/findings be resolved, WORK-0002 completion be synchronized and the final exact-head merge gate be considered.
8. Merge with exact-head guard, then continue to WORK-0003 and WORK-0004.

## Integration-provenance boundary

`registry/integration-provenance.yaml` remains an A3 meta-governance surface containing only exact immutable historical bridges: WORK-0001 squash provenance, progress adoption boundaries and exact malformed-YAML repair episodes. T9 adds no generic historical bypass and moves no predecessor-bound adoption marker. The bounded review-import binding rule is derived from real Git history and does not make unconsumed imported evidence eligible.

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
11. `registry/reviews/REVIEW-0029.yaml`, `REVIEW-0030.yaml`
12. `registry/tests/TEST-0002.yaml`, `TEST-0003.yaml`, `TEST-0007.yaml`, `TEST-0008.yaml`
13. live PR #2 exact HEAD, checks, reviews and all **58 unresolved review threads**
14. `tools/governance/t9_closure.py`, `tools/governance/github_live_gate.py`, `.github/scripts/governance_l2_mutation_smoke.py`
15. `tests/governance/test_t9_findings.py`, `test_t9_coverage.py`, `test_t9_full_history_mutation.py`, `test_t9_import_binding.py`, `test_t9_last_coverage.py`

No prior chat history is required.