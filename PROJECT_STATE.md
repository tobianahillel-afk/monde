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

## Latest exact reviewed candidate and proof

Exact candidate `296ef2005de2ab5964d004d6383393b693594de9` passed deterministic lanes in MONDE Gate run `34904175139` / run number **160** against `main@29086643387ff46ab6636dd2fa3014efccc10165`:

- **244/244 tests PASS**;
- **2801/2801 statements** and **1374/1374 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke: **37/37 critical mutations killed**;
- fresh-L2/T7 mutation smoke: **26/26 critical mutations killed**;
- repository validator: **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure and T7-closure: **0 errors**;
- context manifest: **19 MUST_READ files**;
- CodeQL: **success**;
- Dependency Review lane: **success**.

The live merge gate on that exact HEAD failed closed only on the then-expected 46 unresolved threads and absence of an independent exact-head approval. That proof is now **pre-T8 evidence only**: it does not close findings discovered by the subsequent independent review.

## Fresh independent L2 result — six new material findings

Fresh-context GitHub Codex review `PRR_kwDOUUI5ts8AAAABNih5Qw`, submitted on exact candidate `296ef2005de2ab5964d004d6383393b693594de9`, added **six** material findings. The durable closure set is therefore **52**, all intentionally unresolved:

1. `PRRT_kwDOUUI5ts6iTnww` — changed `ACCEPTED` requirements must revalidate canonical digest/review/cold-read acceptance invariants even when status is unchanged.
2. `PRRT_kwDOUUI5ts6iTnw7` — edited `ACCEPTED` risks must revalidate authority and acceptance invariants even when status is unchanged.
3. `PRRT_kwDOUUI5ts6iTnw-` — COMPLETE-review immutability must include `checks`, `completed_at` and `verification_result` source/executor provenance, not only the earlier semantic projection.
4. `PRRT_kwDOUUI5ts6iTnxB` — identity-policy binding must reject **any intervening** `content-identity.yaml` revision between evidence and acceptance, including change-then-revert where endpoint blobs are equal.
5. `PRRT_kwDOUUI5ts6iTnxE` — exact-head `APPROVED` review is necessary but insufficient: the approver must be trusted/context-separated and bound to qualifying fresh-context L2 evidence.
6. `PRRT_kwDOUUI5ts6iTnxI` — top-level WORK-status `DONE -> IN_REVIEW` reopening triggers must be tied to the exact reopened WORK and cannot borrow unrelated findings/scope changes.

No existing or new thread may be author-resolved during correction.

## WORK-0002 execution state

- T1, T2, T3, T5, T6 and T7 remain DONE for their historical correction scopes.
- **T8 — correction of the six `Nih5Qw` findings — is `IN_PROGRESS`.**
- **T4 — exact final-candidate proof plus approval-capable fresh independent L2 closure — is `BLOCKED` on T8.**
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` are reopened to `IN_REVIEW` because new independent evidence invalidated their previous completion claim.

## Independent-review closure set

The first 46 findings remain exactly the historical closure set already recorded in `registry/work-items/WORK-0002.yaml` and prior review threads. The six `Nih5Qw` findings above extend that set to **52**. The work item is the durable per-finding source; live GitHub remains the authoritative source for current thread resolved/unresolved state.

## T8 correction requirements

T8 must add fail-closed regressions and mutation protection for all six new invariants while preserving every earlier T1–T7 guarantee:

- revalidate continuing ACCEPTED requirement/risk invariants on same-status semantic edits;
- expand COMPLETE-review semantic immutability to every field that can make a review newly completion-eligible;
- detect any identity-policy revision across the full evidence→acceptance ancestry interval, even if reverted;
- require live exact-head approval to be tied to trusted/context-separated L2 evidence rather than actor inequality alone;
- scope top-level WORK reopening triggers to the exact target work item;
- keep all historical exceptions exact, predecessor-bound and future-non-reusable.

## Current WORK-0002 gate

Required sequence from this state:

1. Keep all **52** material review threads unresolved.
2. Implement T8 with targeted adversarial regressions and mutation targets; do not weaken earlier gates to make history pass.
3. Run the full exact-SHA MONDE Gate on the T8 substantive candidate: 100% line+branch, baseline + L2/T7/T8 mutation smoke, repository/strict/path/change/L2/review-closure/T7/T8 gates, CodeQL, Dependency Review and live fail-closed state.
4. Synchronize TEST records and handover only after exact-SHA proof exists.
5. Request another fresh-context independent L2 on the exact final candidate, requiring re-verification of **all 52** findings plus active adversarial search for new bypasses.
6. Require qualifying independent approval evidence on the exact HEAD under the hardened trusted-L2 live-gate contract.
7. Only after independent verification may the corresponding threads/findings be resolved and durable completion evidence recorded.
8. Synchronize WORK-0002 completion, run the final exact-head merge candidate gate, merge with exact-head guard, then continue with WORK-0003 and WORK-0004.

## Integration-provenance boundary

`registry/integration-provenance.yaml` remains an A3 meta-governance surface containing only exact immutable historical bridges: WORK-0001 squash provenance, progress adoption boundaries and exact malformed-YAML repair episodes. T8 must not introduce a generic historical bypass or move any predecessor-bound adoption marker to accommodate current changes.

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
