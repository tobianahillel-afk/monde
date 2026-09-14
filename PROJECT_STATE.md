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

## Exact T8 substantive candidate and proof

Exact substantive T8 candidate **`a8e576ea9ea32b59a95b397de87727a7a52b2926`** passed GitHub Actions **MONDE Gate #163 / run `34908856210`** against `main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **258/258 tests PASS**;
- **2998/2998 statements** and **1476/1476 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke: **37/37 critical mutations killed**;
- fresh-L2/T7/T8 mutation smoke: **33/33 critical mutations killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure, T7-closure and **T8-closure**: **0 errors**;
- context manifest: **19 MUST_READ files**;
- CodeQL: **success**;
- Dependency Review lane: **success**.

The stable live merge gate on this exact substantive candidate also proved that the durable finding set matches the live GitHub state at **52 unresolved threads**. It failed closed for exactly the two expected independent-closure conditions:

- `ERROR UNRESOLVED_THREADS: 52 unresolved review thread(s)`
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL: no trusted, context-separated L2/L3 GitHub APPROVED review is bound to the exact current PR HEAD`

This red live gate is intentional and is not a T8 implementation failure.

## T8 result

Fresh-context review `PRR_kwDOUUI5ts8AAAABNih5Qw` on `296ef2005de2ab5964d004d6383393b693594de9` added six material findings. T8 now implements and mutation-protects all six:

1. same-status edits to an already `ACCEPTED` requirement revalidate the full digest/review/cold-read acceptance invariant;
2. same-status edits to an already `ACCEPTED` risk revalidate canonical authority and acceptance preconditions;
3. all completion-bearing COMPLETE-review fields, including `checks`, `completed_at` and verification provenance, are immutable after completion except the explicitly bounded import-finalization field;
4. any `registry/content-identity.yaml` revision between evidence and acceptance invalidates prior acceptance evidence, including change-then-revert history;
5. live exact-head approval now requires a trusted repository collaborator plus a structured fresh-context, authoring-context-separated L2/L3 attestation covering the required Review Council hats;
6. top-level WORK `DONE -> IN_REVIEW` reopening requires a trigger scoped to the exact reopened WORK rather than an unrelated finding or scope change.

T8 is therefore **DONE author-side** on exact substantive SHA `a8e576ea...`. This is implementation proof, not independent review approval.

## Independent-review closure set

There are **52 intentionally unresolved material threads/findings**. The complete per-finding durable set is recorded in `registry/work-items/WORK-0002.yaml`; live GitHub remains authoritative for current resolved/unresolved thread state.

No thread has been author-resolved during T8 correction.

## WORK-0002 execution state

- T1, T2, T3, T5, T6, T7 and **T8** are DONE for their author-side correction scopes.
- **T4 — exact final metadata-candidate proof plus fresh independent L2 closure — is `IN_PROGRESS`.**
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` are DONE based on Gate #163 plus this synchronized handover.
- `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending independent closure.

## Current WORK-0002 gate

Required sequence from this state:

1. Keep all **52** material review threads unresolved.
2. Prove the metadata-synchronization descendant of `a8e576ea...` with its **own exact-SHA MONDE Gate**; Gate #163 is SHA-bound and is not silently transferred to later metadata commits.
3. Once that metadata HEAD is deterministic-green, request another **fresh-context independent L2** on that exact HEAD. The reviewer must reverify all 52 accumulated findings, explicitly recheck the six T8 invariants, and actively search for new bypasses.
4. If new material findings appear, reopen the affected work and evidence again; do not resolve threads.
5. If semantic review is clean, obtain an eligible GitHub `APPROVED` review on the exact HEAD that satisfies the hardened trusted/context-separated L2/L3 live-gate contract. A shallow approval from an arbitrary external account is insufficient.
6. Only after both independent semantic verification and trusted exact-head approval may verified threads/findings be resolved, WORK-0002 completion be synchronized and the final exact-head merge gate be considered.
7. Merge with exact-head guard, then continue to WORK-0003 and WORK-0004.

## Integration-provenance boundary

`registry/integration-provenance.yaml` remains an A3 meta-governance surface containing only exact immutable historical bridges: WORK-0001 squash provenance, progress adoption boundaries and exact malformed-YAML repair episodes. T8 introduced no generic historical bypass and moved no predecessor-bound adoption marker.

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
13. live PR #2 exact HEAD, checks, reviews and all **52 unresolved review threads**
14. `tools/governance/`, `.github/scripts/` and `tests/governance/`

No prior chat history is required.
