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

## T11 trigger and closure state

Fresh-context GitHub Codex review `PRR_kwDOUUI5ts8AAAABNoalkw` against exact candidate `cc6e98d542fbedf097a8ffbb7eb5dcf128237c84` opened five material findings:

1. audit the pre-T10 `registry/integration-provenance.yaml` bootstrap rather than skipping those historical edits;
2. traverse full merge history when locating the first imported `COMPLETE` / `PASS` materialization;
3. invalidate a previously successful merge gate when an existing review conversation is later unresolved even though GitHub Actions has no native review-thread trigger;
4. scan committed Git blobs rather than textual patches so binary-classified secret-bearing blobs cannot bypass history scanning;
5. validate effective workflow-trigger structure from parsed YAML rather than matching source snippets.

The exact new thread identities are:

- `PRRT_kwDOUUI5ts6igleE`
- `PRRT_kwDOUUI5ts6igleI`
- `PRRT_kwDOUUI5ts6igleM`
- `PRRT_kwDOUUI5ts6igleS`
- `PRRT_kwDOUUI5ts6igleV`

This expands the material closure set from 62 to **67**. None of these 67 threads is author-resolved.

T11 corrected all five and is **DONE author-side**. T4 independent closure remains `IN_PROGRESS`.

## Live PR #2 preflight — 73-thread closure set

A cold live re-query on 2026-09-22 found **73 unresolved** PR #2 review threads, while the branch-local WORK-0002 durable set still contained 67. Gate #228 / run `34997568781` on exact HEAD `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` confirmed the exact six missing identities and no stale durable IDs:

- `PRRT_kwDOUUI5ts6ijUTn` — deploy the stale-green poller before relying on a default-branch-only schedule;
- `PRRT_kwDOUUI5ts6ijUT4` — include review/review-comment-triggered successes in polling;
- `PRRT_kwDOUUI5ts6ijUUC` — reject ambiguous parallel first-status materializations;
- `PRRT_kwDOUUI5ts6ijUUK` — reject terminal external imports without import binding;
- `PRRT_kwDOUUI5ts6ijUUV` — validate executable command structure rather than run-text substrings;
- `PRRT_kwDOUUI5ts6ijUUf` — resolve durable findings from the active work item rather than hard-code WORK-0002.

Current code already represents the latter five corrections. The first finding is the cross-branch/default-branch bootstrap problem owned by PR #5 / the trusted stale-green predecessor and cannot close until that predecessor is independently accepted and integrated.

Gate #228's deterministic lane passed **357/357 tests**, **100% coverage**, repository validation **0 errors / 0 warnings**. Its merge gate failed closed on the 73 intentionally unresolved threads, the six then-missing durable IDs, and absence of trusted context-separated exact-head approval.

The exact durable-set correction head `47d7bcc1840af45059e47e979040808e4b202d4e` then reached **Gate #230 / run `35710776945`**. The live gate reported only `UNRESOLVED_THREADS: 73` and `INDEPENDENT_EXACT_HEAD_APPROVAL`: **the DURABLE_FINDING_SET error disappeared, proving exact 73/73 durable/live PRRT identity equality**.

The T12/T13 identity-split head `242f6c9553c4e42bfbb4e6aad2ca27596573ecb2` reached **Gate #231 / run `35711181317`**:
- **357/357 tests**, **100% line + branch coverage**;
- mutations **37/37 baseline**, **40/40 L2**, **5/5 T10**, **8/8 T11**, **5/5 T13**;
- repository/strict/path/change/L2/review/T7/T8/T9/T10/T11 validators **0 errors**;
- context manifest **19 MUST_READ files**;
- CodeQL and Dependency Review **success**;
- live gate failed only on the intentionally unresolved **73 threads** and missing trusted context-separated exact-head approval.

No thread was resolved by these synchronizations.

## Exact T11 proof

The first T11 candidate `0b943783c80e22e7d47c854b3a4db0b79ebe9f0f` reached MONDE Gate #199 / run `34971757299`: all 339 tests passed, but the 100% coverage gate correctly failed on newly introduced T11/poller branches. The coverage-only descendant `b3daae25ec569b960e95c12d98f387a44f562abe` reached Gate #200 / run `34972089486`, where coverage and mutations passed but the T11 validator exposed 12 historical WORK-0001 review imports whose source-side materialization was hidden by squash integration.

The correction deliberately did **not** modify the `integration-provenance` trust anchor. Instead T11 now separates two contracts:

- exact historical first-status recovery may follow an already-authorized tree-equivalent squash bridge when the source/import/integrated commits, ancestry, expected tree and non-reuse flags all match exactly;
- evidence qualification remains separately fail-closed under T7/T9 and still requires explicit eligible review/test IDs.

Exact substantive T11 SHA **`5e7af51bcc08698de930eed5dba62ab9ba3e74af`** passed deterministic/security lanes in **MONDE Gate #201 / run `34973462479`** with:

- **344/344 tests PASS**;
- **3761/3761 statements** and **1808/1808 branches**, **100.00% line + branch coverage**;
- baseline mutation smoke **37/37**;
- fresh-L2/T7/T8/T9 mutation smoke **40/40**;
- dedicated T10 mutation smoke **5/5**;
- dedicated T11 mutation smoke **8/8**;
- repository validator **0 errors / 0 warnings across 67 records**;
- strict governance, path safety, change guard, fresh-L2 hardening, review-closure, T7, T8, T9, T10 and **T11** closure validators **0 errors**;
- context manifest **19 MUST_READ files**;
- CodeQL **success**;
- Dependency Review lane **success**.

The exact live gate on `5e7af51...` observed **67 unresolved review threads** and failed closed only on:

- `ERROR UNRESOLVED_THREADS: 67 unresolved review thread(s)`;
- `ERROR DURABLE_FINDING_SET`: exactly the five T11 identities above were missing from the then-current 62-entry durable set, with `stale=[]`;
- `ERROR INDEPENDENT_EXACT_HEAD_APPROVAL`: no trusted, context-separated L2/L3 GitHub `APPROVED` review was bound to that exact HEAD.

This durable-state synchronization commit adds exactly those five PRRT identities and no author-side resolutions. Because it changes HEAD, it must receive its own exact-SHA MONDE Gate before the next independent review; Gate #201 proves its substantive parent, not this later metadata state.

## T11 implementation result

T11 now enforces that:

1. the pre-T10 `integration-provenance` bootstrap equals the exact immutable five-commit history already independently reviewed;
2. imported REVIEW/TEST first-status discovery uses full merge history and cannot hide a side-branch materialization;
3. exact squash-tree history recovery proves materialization without silently broadening acceptance-evidence allowlists;
4. changed committed blobs are scanned directly for high-confidence secrets with an explicit fail-closed size bound, including blobs Git classifies as binary;
5. supported review/review-comment events rerun the live gate immediately, while a bounded scheduled poll invalidates a previously green gate if an existing review thread is later unresolved;
6. workflow review/poll triggers and T11 wiring are validated from effective parsed YAML structure rather than comments or text fragments.

## WORK-0002 execution state

- T1, T2, T3, T5, T6, T7, T8, T9, T10, **T11**, **T12**, **T13** and **T14** are DONE for their author-side/integration scopes.
- **T12 — trusted default-branch stale-green predecessor — is now `DONE / integrated`.** PR #5 received clean independent REVIEW-0082 on exact reviewed head `71ed1cb233d16f032ff27cf5a88dfe039e2ba618`, all 83 reviewed PR #5 threads were resolved under controlled closure, reconciliation head `e9d67333f35fc0460ea65806f829257ed0a0266a` passed Bootstrap #333 / run `36053041482`, and PR #5 merged to `main` as `b4b52c77fbf05eda65e8f0e951959da70e7edbe7`.
- T13 is the canonical name for the five branch-local corrections previously carried by files named `t12`; those artifacts remain DONE author-side.
- **T14 — post-PR5 two-parent merge-history integration hardening — remains `DONE` author-side.** This integration commit must preserve its contract by taking PR #2 head `90d762af389990b5e57fce83397a558276500dd5` and new `main` `b4b52c77fbf05eda65e8f0e951959da70e7edbe7` as its two parents.
- **T4 — exact final-integrated-candidate proof plus fresh independent L2 closure — remains `IN_PROGRESS`.
- Gate #259 / run `36055246141` on integrated head `6e8014c7d46e2aceefa03902c37c6bdf2fac0c19` exposed one deterministic integration defect before L2: `.github/scripts/governance_t13_mutation_smoke.py` still targeted the pre-refactor `return any(...)` form of `_steps_execute_prefix`, while the current hardened implementation uses per-step parsed commands plus `if any(...): return True`. The runtime guard was correct; the mutation harness failed closed with `t13-executable-command-proof: target occurrence count != 1`. The current correction retargets that mutant to the exact current executable-prefix branch without weakening the mutation. A fresh exact-head Gate is required before any L2 request.
- Gate #260 / run `36058286810` proved the T13 mutation retarget itself, then exposed a second integration-specific defect in `change_guard`: inherited REVIEW-0082 from the PR #5/main second-parent lineage was incorrectly treated as freshness authority for substantive first-parent PR #2 changes. REVIEW-0082 is valid T12 predecessor evidence, not a review of the current PR #2 delta. The correction makes review freshness authority first-parent scoped: a reviewed commit must remain an ancestor of the head, but only a reviewed commit on the current head's first-parent lineage can stale subsequent first-parent work. A real two-parent regression reproduces PR #5/main as second parent and preserves ordinary first-parent stale-review detection.
**
- Live PR #2 now has **77 unresolved material threads**. The prior 75 remain unresolved. Fresh independent integrated-head Codex review `PRR_kwDOUUI5ts8AAAABPIVhXA` on exact head `c80ff3a3cd9640256fca65285ba28094ac848365` added two P1 findings: `PRRT_kwDOUUI5ts6lxalB` (the generic non-first-parent review-freshness exemption is too broad) and `PRRT_kwDOUUI5ts6lxalH` (required workflow commands can still be made non-blocking with step-level controls such as `continue-on-error: true`). The external negative L2 remains live source evidence; canonical successor REVIEW-0083 has **not** been opened yet.
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` remain `DONE` author-side; `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending exact integrated-head closure.

## Current WORK-0002 gate

Required sequence from this integrated state:

1. Keep all **77** PR #2 material review threads unresolved while the two REVIEW-0083 findings are corrected and proved.
2. Treat T12 as integrated/default-branch reality; do not reopen PR #5 or substitute PR #2's own cron for the merged bootstrap.
3. Preserve the already-proved corrections for `PRRT_kwDOUUI5ts6lURur` and `PRRT_kwDOUUI5ts6lURuu`.
4. Correct P1 `PRRT_kwDOUUI5ts6lxalB` by replacing the topology-wide second-parent freshness skip with one exact, non-reusable WORK-0002 / REVIEW-0082 / PR #5 / T12-merge predecessor exception; every other second-parent review remains freshness-enforced.
5. Correct P1 `PRRT_kwDOUUI5ts6lxalH` by rejecting job/step execution controls that can make a required governance command non-blocking, including `continue-on-error`, unexpected `if`, custom shell/working-directory and dangerous Python/PATH environment overrides.
6. Protect both corrections with regressions and mutation smoke, then run the full MONDE governance gate and require deterministic/security/mutation/CodeQL/Dependency Review success plus exact durable/live **77/77** finding identity equality.
7. Only after exact technical proof may canonical REVIEW-0083 be materialized at `OPEN`; do not retroactively replay the earlier external negative L2 as a terminal registry transition.
8. Advance REVIEW-0083 through OPEN -> IN_PROGRESS with exact-head proofs, then request a fresh-context successor L2 over all 77 findings plus integration effects.
9. If new material findings appear, durably add their exact identities and correct them before any resolution.
10. If semantic review is clean, obtain an eligible GitHub `APPROVED` review on the exact HEAD satisfying the hardened trusted/context-separated L2/L3 contract.
11. Only after independent semantic verification and trusted exact-head approval may independently verified PR #2 threads/findings be resolved, WORK-0002 completion be synchronized and the final exact-head merge gate be considered.
12. Merge PR #2 with exact-head guard, then continue to WORK-0003 and WORK-0004.

## REVIEW-0083 predecessor finding handoff

Fresh independent Codex review `PRR_kwDOUUI5ts8AAAABPIVhXA` reviewed exact integrated head `c80ff3a3cd9640256fca65285ba28094ac848365` and added P1 `PRRT_kwDOUUI5ts6lxalB` plus P1 `PRRT_kwDOUUI5ts6lxalH`. That negative review is retained as GitHub source evidence.

A first attempt to record it directly as a new canonical `CLOSED` review was rejected by Gate #266 because the review registry lifecycle starts at `OPEN` and cannot be replayed retroactively after external review. The invalid state-only commit was removed from the PR branch. The successor canonical REVIEW-0083 therefore remains **unopened** until the two fixes have exact technical proof; it will then begin truthfully at `OPEN`.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance trust anchor because validators consume it as exact historical exception/adoption authority. Candidate state cannot make a same-PR exception self-authorizing. Existing WORK-0001 squash provenance, progress adoption records and malformed-YAML repair episodes remain exact historical-only, future-reuse-forbidden bridges.

Historical **materialization** and evidence **eligibility** are intentionally distinct: an exact equal-tree squash bridge may recover where a record first reached its evidence-bearing status, while acceptance/completion qualification still requires the separately authorized eligible review/test identity and every current proof contract.

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
11. live PR #2 exact HEAD, checks, reviews and all **77 unresolved review threads**
12. `.github/workflows/governance.yml`, `.github/workflows/_governance-core.yml`
13. `tools/governance/t7_closure.py`, `t8_closure.py`, `t9_closure.py`, `t10_closure.py`, `t11_closure.py`, `github_live_gate.py`, `thread_state_poll.py`
14. `.github/scripts/governance_t10_mutation_smoke.py`, `.github/scripts/governance_t11_mutation_smoke.py`, `.github/scripts/governance_l2_mutation_smoke.py`
15. `tests/governance/test_t11_findings.py`, `test_t11_additional_coverage.py`, `test_t13_findings.py`, `test_thread_state_poll.py` and prior T7/T8/T9/T10 regression suites
16. `registry/requirements/REQ-0026.yaml`, `registry/tests/TEST-0009.yaml`, `registry/tests/TEST-0010.yaml`, `registry/reviews/REVIEW-0082.yaml`, and `.github/workflows/monde-stale-green-bootstrap.yml`

No prior chat history is required.
