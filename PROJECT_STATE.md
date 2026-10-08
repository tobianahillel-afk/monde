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
- **T4 — exact final-integrated-candidate proof plus fresh independent L2 closure — remains `IN_PROGRESS`.**
- Gate #259 / run `36055246141` on integrated head `6e8014c7d46e2aceefa03902c37c6bdf2fac0c19` exposed one deterministic integration defect before L2: `.github/scripts/governance_t13_mutation_smoke.py` still targeted the pre-refactor `return any(...)` form of `_steps_execute_prefix`, while the current hardened implementation uses per-step parsed commands plus `if any(...): return True`. The runtime guard was correct; the mutation harness failed closed with `t13-executable-command-proof: target occurrence count != 1`. The current correction retargets that mutant to the exact current executable-prefix branch without weakening the mutation. A fresh exact-head Gate is required before any L2 request.
- Gate #260 / run `36058286810` proved the T13 mutation retarget itself, then exposed a second integration-specific defect in `change_guard`: inherited REVIEW-0082 from the PR #5/main second-parent lineage was incorrectly treated as freshness authority for substantive first-parent PR #2 changes. REVIEW-0082 is valid T12 predecessor evidence, not a review of the current PR #2 delta. The correction makes review freshness authority first-parent scoped: a reviewed commit must remain an ancestor of the head, but only a reviewed commit on the current head's first-parent lineage can stale subsequent first-parent work. A real two-parent regression reproduces PR #5/main as second parent and preserves ordinary first-parent stale-review detection.
- Live PR #2 now has **101 unresolved material threads**. REVIEW-0089 independent L2 added `PRRT_kwDOUUI5ts6muevI` and `PRRT_kwDOUUI5ts6muevQ`; REVIEW-0090 author-side `PRRT_kwDOUUI5ts6m0_t1` adds the permission-binding P1. No thread is resolved.
- WORK-0002 remains `IN_REVIEW`; AC-6 and completion remain open.
- Matrix dimensions `implementation`, `tests`, `real_system_validation` and `handover` remain `DONE` author-side; `specification_governance`, `security_review` and `review` remain `IN_REVIEW` pending exact integrated-head closure.

## Current WORK-0002 gate — REVIEW-0094 OPEN

WORK-0002 remains **IN_REVIEW / A3**, with PR #5/T12 already merged to `main`. PR #2 currently has **102/102 unresolved material review threads**, exactly matching its durable WORK-0002 finding IDs.

The latest negative independent L2 `PRR_kwDOUUI5ts8AAAABRZrUqg` closed REVIEW-0093 with P1 `PRRT_kwDOUUI5ts6qjLmJ`: a candidate-controlled lockfile could execute untrusted dependencies inside the trusted validator.

REVIEW-0094's candidate `b4591d506f425b53a2da0ba3d72d7c1d416c4edb` uses immutable Git blob `d61291f0dd17103995a0ac4473475d6782d48aeb` instead. Trusted validation loads the blob from Git to RUNNER_TEMP, compares against the PR lock before install, and installs exclusively from the immutable copy; T11 binds this exact sequence. This is an interim pinned source, not a claim that the lock path exists on default-branch main.

**OPEN checkpoint result:** Bootstrap #493 / `37845682858` succeeded; Gate #388 / `37845683806` passed candidate tests, mutations, deterministic governance, CodeQL and Dependency Review. The live merge gate correctly failed closed on 102 unresolved threads, missing trusted exact-head approval, and one durable-set mismatch: WORK-0002 accidentally concatenated `PRRT_kwDOUUI5ts6m5xW5` and `PRRT_kwDOUUI5ts6qjLmJ` into one YAML list item. This state-only correction separates them; **the corrected HEAD still requires a fresh exact-head Gate** before REVIEW-0094 may advance.

**Technical proof:** Bootstrap **#492 / 37844427321** succeeded: 450 tests, 3,853 statements / 1,640 branches, 100% line+branch and live PR #2 probe 3/100. Gate **#387 / 37844428189** passed 841 candidate tests, 8,143 statements / 3,770 branches, 100% line+branch, mutation lanes 38/38 + 40/40 + 5/5 + 28/28 + 18/18; CodeQL and Dependency Review succeeded. Trusted validate successfully loaded and compared the immutable blob, then **failed repository validation solely on two unknown references to REVIEW-0094** because that lifecycle file did not yet exist. Gate #387 is failed/negative evidence, never approval.

This commit materializes REVIEW-0094 in its true **OPEN** initial state. The next mandatory sequence is OPEN checkpoint Bootstrap+Gate → IN_PROGRESS state-only transition → frozen exact-head Bootstrap+Gate → independent fresh-context L2 across all 102 findings. No thread resolution or merge until a clean L2 and trusted non-author exact-head APPROVED evidence. WORK-0003 and WORK-0004 remain blocked.

## REVIEW-0093 — candidate-execution isolation successor

REVIEW-0093 is now **IN_PROGRESS** after exact technical proof on `3168913c85c6a122b932833297395922e61f6275` and OPEN checkpoint proof on `2c5305d3f49815b3df1eab1cd51bd2ce23629bc6`.

The successor closes REVIEW-0092 P1 `PRRT_kwDOUUI5ts6m5xW5` by moving every pytest-executing mutation smoke into the isolated `candidate-tests` job. The trusted `validate` job now starts on a fresh runner only after `candidate-tests` succeeds and is limited to exact-head checkout, pinned Python **without pip-cache restore**, fresh hash-locked toolchain install and trusted validators.

The exact workflow graph remains bound:
- top-level job set is unchanged and exact;
- reusable core job set is exactly `candidate-tests` + `validate`;
- `validate.needs` is exactly `candidate-tests`;
- final-gate needs remain exact;
- REVIEW-0091 exact permissions, REVIEW-0090 exact env/action-input bindings, REVIEW-0089 trusted execution substrate and REVIEW-0088 trusted predecessor-prefix protections remain intact.

The corrected T11 mutation harness now neutralizes the semantic `_job_contains_candidate_execution()` detector itself instead of removing only one redundant caller. Gate #381 therefore proves **26/26 T11 critical mutations killed**.

Bootstrap #443 / run `36566136600` and Gate #382 / run `36566136926` proved the OPEN checkpoint with the same complete technical proof; the live gate still failed only on **101 unresolved threads** and missing trusted exact-head approval. All **101/101 PR #2 material threads remain unresolved**. REVIEW-0093 is now `IN_PROGRESS` and requires one frozen exact-head proof before fresh independent L2.

## REVIEW-0092 — terminal negative evidence

REVIEW-0092 is **CLOSED / CHANGES_REQUIRED** on exact OPEN checkpoint head `fcf3e755050bfefa652fcf082bf786e19dea9bfd`.

Its substantive technical candidate `b830aaaeb1954541da102d4e897b734e5c82485a` passed Bootstrap #433 / run `36498023728` and Gate #371 / run `36498024030`:
- **450 bridge tests**, **3,853 statements / 1,640 branches**, **100% line + branch**;
- **839 governance tests**, **8,120 statements / 3,758 branches**, **100% line + branch**;
- mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 24/24 T11 + 18/18 T13**;
- candidate-tests, deterministic governance, CodeQL and Dependency Review all green;
- live merge gate failed only on the then-**100 unresolved threads** and missing trusted exact-head approval.

The structural job-graph fixes are valid: top-level pytest is isolated, primary/core job sets are exact, `validate.needs` and final-gate `needs` are exact, and the exact permission/env/action/substrate protections remain intact.

However author-side review `PRR_kwDOUUI5ts8AAAABPqVtcQ` / P1 `PRRT_kwDOUUI5ts6m5xW5` proved the isolation boundary is incomplete. Every mutation-smoke script copies `os.environ` and launches PR-controlled pytest. Because all five smokes still run in `validate`, a malicious test can write GitHub's `GITHUB_PATH` / `GITHUB_ENV` files and alter later trusted validators while their reviewed argv remains exact.

The trusted `validate` job also restores the same pip cache key used by candidate execution. REVIEW-0093 must eliminate both couplings.

The closure set is now **101 unresolved material threads**. No thread is resolved. REVIEW-0092 closed before `IN_PROGRESS`; Gate #372 was cancelled by the review event and is not approval or lifecycle-completion evidence.

## REVIEW-0091 — terminal negative evidence

REVIEW-0091 is **CLOSED / CHANGES_REQUIRED** on exact frozen head `214a24f126caf45182153a298b6189b436231b1a`.

Bootstrap #429 / run `36490673993` proved **450 bridge tests**, **3,853 statements / 1,640 branches**, **100% line + branch**, with live PR #2 probe SUCCESS at **3/100** requests.

Gate #363 / run `36490674152` proved **838 governance tests**, **8,089 statements / 3,738 branches**, **100% line + branch**, mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 20/20 T11 + 18/18 T13**, deterministic governance, CodeQL and Dependency Review green. The live gate failed only on the then-**98 unresolved threads** and missing trusted exact-head approval.

Fresh independent Codex L2 `PRR_kwDOUUI5ts8AAAABPp84qg` then added P1 `PRRT_kwDOUUI5ts6m5Bky`: the PR-controlled pytest step runs before the trusted mutation/validator sequence in the same job and can persist execution-context mutations such as `GITHUB_PATH` into later steps.

Author-side red-team `PRR_kwDOUUI5ts8AAAABPp9nTw` added P1 `PRRT_kwDOUUI5ts6m5DOC`: REVIEW-0091 binds permissions exactly only for known jobs, but does not require the complete workflow job set to equal the reviewed canonical set; an extra job can declare an elevated job-level token permission map.

The live/durable closure set is now **100 unresolved material threads**. REVIEW-0092 is required; no thread is resolved.

## REVIEW-0090 — exact execution-env and action-input successor

REVIEW-0090 is now **CLOSED / CHANGES_REQUIRED** on exact frozen head `7ac20ffb81be8ffe216c6fc52073fa269e9966d9`.

Bootstrap #419 / run `36459855072` succeeded. Gate #352 / run `36459855485` proved:
- **836 governance tests PASS**;
- **8,066 statements / 3,722 branches**, **100% line + branch**;
- mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 19/19 T11 + 18/18 T13**;
- CodeQL and Dependency Review SUCCESS.

The deterministic lane stopped only at repository validation because WORK-0002 already referenced REVIEW-0090 while this lifecycle record did not yet exist. No test, coverage or mutation defect remained.

The successor closes the two REVIEW-0089 P1 classes by making execution environment and action inputs exact rather than blocklist/subset based. Workflow/job env must be empty for trusted execution; sensitive step env must exactly match its reviewed required mapping. Pinned actions must expose exactly the canonical `with:` mapping, so Dependency Review rejects extra weakening inputs such as `warn-only: true`.

Bootstrap #421 / run `36469876751` and Gate #354 / run `36469877334` proved the frozen REVIEW-0090 implementation with 450 bridge tests, 836 governance tests, 100% line+branch coverage, all mutation lanes and deterministic/security validators green. The live gate failed only on 97 unresolved threads plus missing trusted exact-head approval. Codex L2 was quota-refused via `5876717580`. Author-side `PRR_kwDOUUI5ts8AAAABPn9-Eg` then added P1 `PRRT_kwDOUUI5ts6m0_t1`: security-sensitive GITHUB_TOKEN permissions are not exact-bound. The live/durable closure target is now **100 unresolved threads**. REVIEW-0091 must correct that before another L2.

## REVIEW-0089 — trusted job execution substrate successor

REVIEW-0089 is now **CLOSED / CHANGES_REQUIRED** on exact frozen head `fa2c1cc6162068d1268e9f5b7a24bc73bedfdbc5` after fresh independent L2 `PRR_kwDOUUI5ts8AAAABPk5JjQ` found two P1s.

Bootstrap #410 / run `36416893514` passed **450/450 bridge tests**, **3,853 statements / 1,640 branches**, **100% line + branch**, with live PR #2 probe SUCCESS at **3/100** requests.

Gate #341 / run `36416893817` proved the implementation before lifecycle materialization:
- **833 governance tests PASS**;
- **8,076 statements / 3,736 branches**, **100% line + branch**;
- mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 16/16 T11 + 18/18 T13**;
- CodeQL and Dependency Review SUCCESS.

The deterministic lane stopped only at repository validation because WORK-0002 referenced REVIEW-0089 before this lifecycle file existed. No test, coverage, mutation, CodeQL or Dependency Review defect remained.

The successor preserves REVIEW-0088 exact trusted predecessor ordering and now binds the job execution substrate: security-sensitive jobs reject `container`, reject `services`, and reject any explicit noncanonical `runs-on` value. The reviewed real jobs use `ubuntu-24.04`. The runner check is scoped to trusted sensitive-job validation rather than generic parser helpers, so reusable workflow call jobs and minimal unit fixtures are not falsely treated as execution proof.

Live/durable finding parity is **95 == 95**, zero missing, zero stale. All 95 threads remain unresolved.

Bootstrap #412 / run `36418281503` and Gate #343 / run `36418281767` proved the frozen REVIEW-0089 head: deterministic governance, CodeQL and Dependency Review were green; live closure failed only on **95 unresolved threads** and missing trusted exact-head approval. Independent L2 then added `PRRT_kwDOUUI5ts6muevI` (execution-poisoning env keys such as `LD_PRELOAD`) and `PRRT_kwDOUUI5ts6muevQ` (extra Dependency Review inputs such as `warn-only: true`), expanding the closure set to **97**. REVIEW-0090 must correct both before another review.

## REVIEW-0088 — trusted predecessor-step prefix successor

REVIEW-0088 is now **CLOSED / CHANGES_REQUIRED** on exact frozen head `2c1d72b42094e3f72d5eaa0421a9ba0d4f59a12e`.

Bootstrap #403 / run `36399267697` passed **450/450 tests**, **3,853 statements / 1,640 branches**, **100% line + branch**, with live PR #2 probe SUCCESS at **3/100** requests.

Gate #332 / run `36399267742` proved the REVIEW-0088 implementation itself before lifecycle materialization:
- **831 tests PASS**;
- **8,056 statements / 3,720 branches**, **100% line + branch**;
- mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 13/13 T11 + 18/18 T13**;
- CodeQL and Dependency Review SUCCESS.

Gate #332 then stopped at repository validation only because WORK-0002 already referenced REVIEW-0088 while the lifecycle record did not yet exist. No code/test/mutation failure remained.

The new T11 layer preserves every existing semantic validator and additionally binds sensitive nodes to canonical predecessor positions. Extra or reordered same-job steps before poll/core/Dependency Review/CodeQL/final-gate sensitive execution now fail closed, including `GITHUB_PATH` / `GITHUB_ENV` persistence attempts.

Bootstrap #404 / run `36400367147` and Gate #333 / run `36400367846` proved the OPEN checkpoint: **450/450** bridge tests; **831** governance tests; **3,853 / 1,640** bootstrap and **8,056 / 3,720** governance coverage at **100% line + branch**; mutations **38/38 + 40/40 + 5/5 + 13/13 + 18/18**; all deterministic/T7-T11/context validators, CodeQL and Dependency Review green. The live gate failed closed only on **94 unresolved threads** and missing trusted exact-head approval. This IN_PROGRESS state now requires one frozen exact-head proof before fresh independent L2.

Bootstrap #405 / run `36403246271` and Gate #334 / run `36403246691` proved the frozen REVIEW-0088 head with the same **831 tests**, **8,056 statements / 3,720 branches**, **100% line + branch**, full mutations/validators, CodeQL and Dependency Review green. The live gate failed closed only on **94 unresolved threads** and missing trusted exact-head approval. Codex L2 trigger `5867225086` was quota-refused by `5867227977`.

Author-side `PRRT_kwDOUUI5ts6mnZ-N` then exposed a new P1: trusted predecessor-step ordering does not constrain `job.container` / `container.env`. Exact validated commands can therefore execute inside an attacker-controlled job container or with container-level `PYTHONPATH` while every reviewed step remains unchanged. The live/durable closure set is now **95**.

REVIEW-0089 must fail closed on untrusted job execution containers for all security-sensitive jobs, preserve every REVIEW-0083→0088 protection, and add regression plus mutation coverage.

## REVIEW-0087 — terminal negative cross-step execution-context review

REVIEW-0087 is now **CLOSED / CHANGES_REQUIRED** on exact frozen head `47091d48b40d37dfb18b32f0546ea348731d7cc9`.

Bootstrap #398 / run `36359412756` and Gate #327 / run `36359413005` proved the frozen candidate at **829 tests**, **7,982 statements / 3,682 branches**, **100% line + branch**, all mutation lanes/validators green, CodeQL and Dependency Review green. The live gate failed closed only on the then-**93 unresolved threads** and missing trusted exact-head approval. The requested Codex L2 was blocked by quota.

Author-side `PRR_kwDOUUI5ts8AAAABPdq9-g` / `PRRT_kwDOUUI5ts6mfxiN` then exposed a new P1: a security-sensitive step can retain an exact accepted argv while a preceding step in the same job persists attacker-controlled execution context through `GITHUB_PATH`, `GITHUB_ENV`, workspace/system mutation or equivalent mechanisms. Isolated-step validation therefore does not establish trusted execution.

REVIEW-0088 must bind sensitive commands/actions to a trusted predecessor-step prefix/order. Arbitrary extra/reordered predecessor steps must fail closed, while the existing canonical pinned actions and exact run commands remain reusable.

## REVIEW-0086 — terminal negative exact-ref / complete-argv / probe-binding review

REVIEW-0086 is **CLOSED / CHANGES_REQUIRED** on exact frozen head `e42ddbcffce8a0265ac34b46818e021d87fc7ca8` after fresh independent L2 `PRR_kwDOUUI5ts8AAAABPQM5sQ`.

The prior candidate retained its exact-ref, complete-argv, function-shadowing and Dependency Review producer-binding corrections, but the independent review found two additional P1s:
- `PRRT_kwDOUUI5ts6mBvTj` — a multi-command `run:` can prepend an environment/state mutation such as `export PATH=...` before an otherwise exact required argv;
- `PRRT_kwDOUUI5ts6mBvTp` — the exact `depgraph` producer and guarded Dependency Review action are validated independently, so the producer can be moved below its consumer and the scan is skipped.

The durable/live closure set is now **93**. REVIEW-0087 must make security-sensitive required-command steps single-logical-command only and must structurally bind the exact Dependency Graph producer to a strictly later action consumer. No thread is resolved before a clean successor review and trusted exact-head approval.

## REVIEW-0085 — terminal negative integrated-head review

REVIEW-0085 completed on exact frozen head `4cbe42fd2c5b2fc14cd50e843c103340cf4dac99` with independent reviewer `chatgpt-codex-connector` / `PRR_kwDOUUI5ts8AAAABPPl4wg` and outcome **CHANGES_REQUIRED**.

Independent P1 findings:
- `PRRT_kwDOUUI5ts6mAc8I` — checkout action pinning does not bind the exact expected ref;
- `PRRT_kwDOUUI5ts6mAc8M` — split-line Bash function declaration can shadow the required executable;
- `PRRT_kwDOUUI5ts6mAc8O` — prefix-only command proof accepts suffixes such as `--help` that bypass real validation;
- `PRRT_kwDOUUI5ts6mAc8S` — Dependency Review action condition relies on an unvalidated capability-probe producer.

Author-side `PRRT_kwDOUUI5ts6mAdoV` independently exposed the related Bash subshell-function form `python() ( ... )`.

The live/durable unresolved closure set is now **91**. No thread is resolved. A successor review may be materialized only after all four distinct defect classes receive exact technical proof.

Historical pre-review proof on this review remains Bootstrap #365/#366 and Gate #300/#301; frozen proof is Bootstrap #367 / Gate #302.

Bootstrap #365 / run `36134916018` and Gate #300 / run `36134916263` proved the corrected candidate:
- **827 tests PASS**;
- **7,932 statements / 3,652 branches**, **100% line + branch**;
- mutations **38/38 baseline + 40/40 L2 + 5/5 T10 + 11/11 T11 + 14/14 T13**;
- repository/strict/path/change/L2/review/T7/T8/T9/T10/T11 validators all green;
- context manifest **25 MUST_READ files**;
- CodeQL and Dependency Review **success**;
- live gate failed closed only on **86 unresolved threads** and missing trusted exact-head approval, with no durable-finding mismatch.

The successor must independently falsify the five REVIEW-0084 fixes: shell-executable shadowing, Dependency Review action execution binding, required final live-gate command, complete governance-core command inventory, and pinned CodeQL init/analyze action binding.

Bootstrap #366 / run `36135753228` and Gate #301 / run `36135753428` proved the OPEN checkpoint with the same **827 tests**, **7,932 statements / 3,652 branches**, **100% line + branch**, **14/14 T13 mutations**, all deterministic validators green, and live gate blocked only on **86 unresolved threads** plus missing trusted exact-head approval. This IN_PROGRESS state now requires one frozen exact-head proof before a fresh independent L2.

## REVIEW-0084 — terminal negative integrated-head review

REVIEW-0084 completed on exact frozen head `d1850542494492a388b545dec954e078b825d9b5` with independent reviewer `chatgpt-codex-connector` / `PRR_kwDOUUI5ts8AAAABPOcDnA` and outcome **CHANGES_REQUIRED**.

The frozen candidate passed Bootstrap #356 / run `36124803925` and Gate #286 / run `36124804464`: **824 tests**, **7,851 statements / 3,596 branches**, **100% line + branch**, mutations **38/38 + 40/40 + 5/5 + 11/11 + 9/9**, all deterministic/T7-T11 validators, CodeQL and Dependency Review green. The live gate failed only on 81 unresolved threads and missing exact-head approval before review.

Independent P1 findings:
- `PRRT_kwDOUUI5ts6l9_hk` — shell function/declaration can shadow the required executable while accepted argv remains visible;
- `PRRT_kwDOUUI5ts6l9_ht` — dependency-review job condition is checked but the pinned Dependency Review action itself is not required;
- `PRRT_kwDOUUI5ts6l9_hz` — final-gate structure does not require the blocking `tools.governance.github_live_gate` command;
- `PRRT_kwDOUUI5ts6l9_h4` — governance-core structure does not require the complete deterministic command inventory;
- `PRRT_kwDOUUI5ts6l9_h8` — CodeQL job identity/result is checked but pinned init/analyze actions are not structurally required.

The live/durable unresolved closure set is now **86**. No thread is resolved. A successor review may be materialized only after all five defects receive exact technical proof.

## REVIEW-0083 — terminal negative integrated-head review

REVIEW-0083 completed on exact frozen head `cc37d74e2ee49aea62cfdfa30634c01a1032751f` with independent reviewer `chatgpt-codex-connector` / `PRR_kwDOUUI5ts8AAAABPJeT9Q` and outcome **CHANGES_REQUIRED**.

Independent P1 findings:
- `PRRT_kwDOUUI5ts6lzzao` — inherited workflow/job env and defaults.run bypass required-command proof;
- `PRRT_kwDOUUI5ts6lzzas` — single `&` backgrounds a required validator while preserving the accepted argv prefix;
- `PRRT_kwDOUUI5ts6lzzax` — PR-family dependency-review may be skipped while final gate accepts `skipped`.

Author-side duplicate `PRRT_kwDOUUI5ts6lz1l8` independently rediscovered the first defect and remains part of the live/durable 81-thread closure set.

A REVIEW-0084 successor may be created only after these defects receive exact technical proof.

## REVIEW-0083 — historical context

Fresh independent Codex review `PRR_kwDOUUI5ts8AAAABPIVhXA` reviewed exact integrated head `c80ff3a3cd9640256fca65285ba28094ac848365` and added P1 `PRRT_kwDOUUI5ts6lxalB` plus P1 `PRRT_kwDOUUI5ts6lxalH`. That negative review is retained as GitHub source evidence.

A first attempt to record the external negative review directly as a new canonical `CLOSED` record was rejected by Gate #266 because the review registry lifecycle starts at `OPEN`; that invalid state-only commit was removed from branch history. After the two P1 fixes received exact technical proof on `854c4e8aa076bd6ac1c57baae96b9f278e995c0e`, REVIEW-0083 was materialized truthfully at **OPEN**, that checkpoint is now exactly proved, and the record advances to **IN_PROGRESS**.

## Integration-provenance boundary

`registry/integration-provenance.yaml` is an A3 meta-governance trust anchor because validators consume it as exact historical exception/adoption authority. Candidate state cannot make a same-PR exception self-authorizing. Existing WORK-0001 squash provenance, progress adoption records and malformed-YAML repair episodes remain exact historical-only, future-reuse-forbidden bridges.

Historical **materialization** and evidence **eligibility** are intentionally distinct: an exact equal-tree squash bridge may recover where a record first reached its evidence-bearing status, while acceptance/completion qualification still requires the separately authorized eligible review/test identity and every current proof contract.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public visibility.

## Product/UI/UX owner gate

Product specification and product identity remain owner-gated decisions. Agents must not silently canonize product experience, UI/UX, visual identity, brand, color system, interface density, interaction language, emotional/psychovisual tone or other strong design choices. Major product-function decisions require explicit owner co-design rather than irreversible invention.

## REVIEW-0093 — terminal independent security finding (2026-10-08)

Exact PR #2 head `6cacafed55931d0f37fb0088ef4425ff05681597` passed Bootstrap #444 and deterministic governance, CodeQL and Dependency Review in Gate #383. The live merge gate remained blocked on unresolved threads and missing exact-head trusted approval.

Fresh Codex L2 `PRR_kwDOUUI5ts8AAAABRZrUqg` on that exact head added **P1 `PRRT_kwDOUUI5ts6qjLmJ`**: the trusted `validate` job still installs Python dependencies from the PR candidate's own `requirements/governance-ci.txt`. A candidate-selected, hash-locked wheel can execute a Python startup `.pth` hook before the supposed trusted validators. Hash locking alone does not establish approval of the dependency set.

REVIEW-0093 is **CLOSED / CHANGES_REQUIRED**, never approval. PR #2 now has **102 unresolved material review threads**. REVIEW-0094 must bind the validation toolchain to an approved default-branch/base lockfile, prove that binding in executable T11 governance validation, and test malicious candidate lock changes. PR #5/T12 is already merged into main and must not be redeveloped.

## REVIEW-0094 — immutable governance dependency lock / IN_PROGRESS

REVIEW-0093 is terminal negative evidence for P1 `PRRT_kwDOUUI5ts6qjLmJ`. `main` does not yet contain `requirements/governance-ci.txt`; this phase uses the exact immutable Git blob `d61291f0dd17103995a0ac4473475d6782d48aeb` as an interim explicit trust anchor, not a false claim that an approved lock already exists on the default branch.

On a separate runner, trusted `validate` extracts that blob into `RUNNER_TEMP`, compares PR candidate lock bytes before installing anything from it, and installs only from the immutable copy. `candidate-tests` remains isolated. T11 binds source, ordering, comparison and installation; its mutant suite proves both the source and drift checks cannot be bypassed.

**The REVIEW-0094 OPEN checkpoint is now proved.** Exact head `a3a3a94f3ae1c0377c495c7b4c88283782a2703e` passed Bootstrap #494 / run `37846507623` and Gate #389 / run `37846508065`:
- Bootstrap: **450/450 tests** and **100% line + branch**, live PR #2 probe successful.
- Governance: **841 tests**, **8,143 statements / 3,770 branches**, **100% line + branch**.
- Mutations: **38/38 baseline + 40/40 L2 + 5/5 T10 + 28/28 T11 + 18/18 T13** killed.
- Deterministic governance, CodeQL and Dependency Review: **SUCCESS**.
- Live final gate: fail-closed **only** on **102 unresolved PR #2 threads** and missing independently trusted exact-head APPROVED review. Live/durable finding identity remains aligned.

REVIEW-0094 now advances `OPEN -> IN_PROGRESS` in a state-only commit. This new frozen head needs its own Bootstrap + complete Gate proof before fresh-context L2. No review thread may be resolved before independent semantic acceptance and the separate qualifying non-author exact-head GitHub approval.

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
11. live PR #2 exact HEAD, checks, reviews and all **102 unresolved review threads**
12. `.github/workflows/governance.yml`, `.github/workflows/_governance-core.yml`
13. `tools/governance/t7_closure.py`, `t8_closure.py`, `t9_closure.py`, `t10_closure.py`, `t11_closure.py`, `github_live_gate.py`, `thread_state_poll.py`
14. `.github/scripts/governance_t10_mutation_smoke.py`, `.github/scripts/governance_t11_mutation_smoke.py`, `.github/scripts/governance_l2_mutation_smoke.py`
15. `tests/governance/test_t11_findings.py`, `test_t11_additional_coverage.py`, `test_t13_findings.py`, `test_thread_state_poll.py` and prior T7/T8/T9/T10 regression suites
16. `registry/requirements/REQ-0026.yaml`, `registry/tests/TEST-0009.yaml`, `registry/tests/TEST-0010.yaml`, `registry/reviews/REVIEW-0082.yaml`, `registry/reviews/REVIEW-0083.yaml`, `registry/reviews/REVIEW-0084.yaml`, `registry/reviews/REVIEW-0085.yaml`, `registry/reviews/REVIEW-0086.yaml`, `registry/reviews/REVIEW-0087.yaml`, `registry/reviews/REVIEW-0088.yaml`, `registry/reviews/REVIEW-0089.yaml`, `registry/reviews/REVIEW-0090.yaml`, `registry/reviews/REVIEW-0091.yaml`, `registry/reviews/REVIEW-0092.yaml`, `registry/reviews/REVIEW-0093.yaml`, and `.github/workflows/monde-stale-green-bootstrap.yml`

No prior chat history is required.
