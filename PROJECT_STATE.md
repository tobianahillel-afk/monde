# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- **PHASE-0 — Specification and repository governance** is `IN_PROGRESS`.
- **LOT-0 — AI-first repository operating system** is `IN_PROGRESS`.
- **WORK-0001** is `DONE / A3` and is integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- **WORK-0002** remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain blocked until WORK-0002 is independently closed.

## WORK-0002 default-branch bootstrap predecessor

Fresh independent L2 review of PR #2 established that its stale-green review-thread poll cannot protect PR #2 before merge because GitHub scheduled workflows execute from the trusted default branch. A narrow predecessor is therefore being proven separately in **PR #5 — `fix(governance): bootstrap stale-green thread polling`**.

This bridge belongs to WORK-0002/T12. It is not a product capability and does not weaken any governance rule. Its sole purpose is to provide a trusted `main`-resident five-minute invalidation bridge while PR #2 remains open.

The current bridge:

- enumerates open PRs and validates their server-reported `head.repo.full_name`, `head.ref`, `head.sha`, and `created_at`;
- rejects two open PRs whose complete `(head repository, branch, SHA)` identity is indistinguishable instead of guessing which PR a run belongs to;
- queries only canonical MONDE Gate workflow ID `354465551` and verifies path `.github/workflows/governance.yml`;
- validates each PR-family run using GitHub-server `head_repository.full_name`, `head_branch`, `head_sha`, `created_at`, `updated_at`, run number/id and supported terminal conclusion;
- deliberately does **not** treat the ambiguous `workflow_run.pull_requests` association list as triggering-PR identity;
- treats a run as eligible target context for the current PR only when `run.created_at >= PR.created_at`, so a closed earlier PR that used the same repo/ref/SHA cannot be revived as the rerun context for a later PR incarnation;
- considers `pull_request`, `pull_request_review`, and `pull_request_review_comment` gate runs;
- computes the newest effective commit-scoped gate state across validated historical runs, while selecting the current PR's rerun target only from runs inside the current PR-incarnation time boundary;
- when another PR sharing a SHA re-greens the commit, reruns the target PR's own current-incarnation head-identity-bound run if that PR still has unresolved threads;
- validates GraphQL `errors` fail-closed: the field may be absent or exactly an empty list only; malformed/falsey alternatives such as `{}`, `""`, `0` or `null` are rejected;
- bounds REST pagination and GraphQL review-thread pagination to `MAX_PAGES`, rejecting malformed metadata, missing/repeated cursors and exhaustion;
- grants `actions: write` only to the trusted scheduled poll job; the PR validation probe remains read-only and non-destructive.

The bootstrap is temporary. After PR #2 is merged, its canonical poller becomes the durable implementation; WORK-0003 may then rationalize/remove redundant bootstrap machinery when repository protection and merge discipline are configured.

## Stable bootstrap traceability

Fresh PR #5 review identified that this material governance behavior requires a stable normative identity rather than living only as WORK prose. The bootstrap now has a non-terminal canonical trace:

`REQ-0026 (PROPOSED) -> WORK-0002 -> TEST-0009 (PLANNED) + REVIEW-0031 (OPEN)`

- **REQ-0026 — Trusted stale-green review-state invalidation** defines the atomic bootstrap obligation.
- **TEST-0009** protects REQ-0026 and records the intended unit/contract/live-GitHub verification path without retroactively importing prior executions as a canonical PASS.
- **REVIEW-0031** is reserved for the fresh independent bootstrap review. It is intentionally numbered after REVIEW-0029/0030, which already exist on PR #2, preventing a cross-branch registry-ID collision when `main` is later integrated into PR #2.

REQ-0026 remains `PROPOSED`, TEST-0009 remains `PLANNED`, and REVIEW-0031 remains `OPEN` until their real lifecycle evidence exists. No retrospective ACCEPTED/PASS/COMPLETE state is fabricated.

## Exact bootstrap proof

Latest exact synchronized bootstrap candidate before this PROJECT_STATE update: **`3dbaddb610bd1eab1b6d5ccdeec10fcf7b0f5c16`**.

GitHub Actions run **`34994621227` / MONDE Stale-Green Bootstrap #30** is fully green on that exact head:

- **Bootstrap self-test: SUCCESS**;
- **Bootstrap GitHub contract probe: SUCCESS** against **PR #2**, the actual WORK-0002 consumer;
- the executable/test tree was previously proven on run **`34994214744` / #27** at `95cf13f0861ce47ab345655911b5ea8a3ba76ff6` with **29/29 tests**, **224/224 statements**, **88/88 branches**, and **100% line + branch coverage**;
- the live read-only probe on that corrected tree validates open-PR metadata, canonical MONDE Gate run metadata and review-thread GraphQL state while binding reruns to the current PR incarnation rather than an earlier closed PR sharing the same repo/ref/SHA.

Earlier run **#26 `34994081272`** intentionally exposed one stale test expectation after the PR-incarnation diagnostic changed; the live GitHub contract probe already passed there. The next commit preserved the more precise diagnostic while retaining compatibility, and run #27 then proved the corrected suite at 100% coverage.

## PR #5 independent review state

All material PR #5 review threads remain unresolved. Successive fresh Codex reviews have identified **17 P1 findings** so far.

The first five review rounds produced 14 findings:

- `PRR_kwDOUUI5ts8AAAABNpylnA`: canonical workflow identity; malformed REST collection handling; malformed GraphQL metadata;
- `PRR_kwDOUUI5ts8AAAABNqb2xg`: canonical-workflow pagination scope; durable WORK/PROJECT_STATE ownership; 100% coverage; real-system GitHub validation;
- `PRR_kwDOUUI5ts8AAAABNqnqWQ`: validate run event before filtering; distinguish runs sharing a commit;
- `PRR_kwDOUUI5ts8AAAABNqx3YA`: reinvalidate shared-head cross-PR success; reject unknown conclusions; reject Boolean PR numbers;
- `PRR_kwDOUUI5ts8AAAABNq6L4g`: do not treat `workflow_run.pull_requests` association cardinality as triggering-PR identity; record exact current proof in durable repository state.

Fresh exact-head review **`PRR_kwDOUUI5ts8AAAABNrJroQ`** on `ff68bfd17a7bf8439570398ca333763b6de96429` added three more P1 findings:

- `PRRT_kwDOUUI5ts6imgom` — bind reruns to the current PR incarnation so an earlier closed PR run with the same repo/ref/SHA cannot be reused;
- `PRRT_kwDOUUI5ts6imgor` — reject malformed but falsey GraphQL `errors` values rather than accepting partial data;
- `PRRT_kwDOUUI5ts6imgoz` — give the material bootstrap behavior a stable REQ identity and TEST/REVIEW verification path.

The exact 17 material thread identities are:

- `PRRT_kwDOUUI5ts6ijmtc`
- `PRRT_kwDOUUI5ts6ijmtj`
- `PRRT_kwDOUUI5ts6ijmtr`
- `PRRT_kwDOUUI5ts6ilBFN`
- `PRRT_kwDOUUI5ts6ilBFV`
- `PRRT_kwDOUUI5ts6ilBFb`
- `PRRT_kwDOUUI5ts6ilBFl`
- `PRRT_kwDOUUI5ts6ilcBE`
- `PRRT_kwDOUUI5ts6ilcBL`
- `PRRT_kwDOUUI5ts6ilysF`
- `PRRT_kwDOUUI5ts6ilysW`
- `PRRT_kwDOUUI5ts6ilysm`
- `PRRT_kwDOUUI5ts6imDdU`
- `PRRT_kwDOUUI5ts6imDdZ`
- `PRRT_kwDOUUI5ts6imgom`
- `PRRT_kwDOUUI5ts6imgor`
- `PRRT_kwDOUUI5ts6imgoz`

Author-side correction is not closure evidence. These threads stay open until a new fresh exact-head independent review verifies the synchronized final candidate.

## WORK-0002 / T12 relationship

PR #2 has the richer branch-local WORK-0002 record and remains authoritative for T7-T12 implementation history. The default-branch mirror records only the bootstrap predecessor and cross-branch handoff. After PR #5 is independently clean and merged, `main` must be integrated into PR #2 without discarding that richer state. T12 must then prove the bootstrap is genuinely **base-preexisting** rather than candidate-created.

The fresh PR #2 L2 that opened T12 expanded its material unresolved set from 67 to **73** findings. All 73 remain unresolved. Its six T12 findings cover:

1. pre-merge deployment of stale-green polling on the default branch;
2. inclusion of review-event gate runs in stale-green selection;
3. ambiguity of imported terminal status across parallel history;
4. rejection of terminal external imports without `import_commit` binding;
5. executable-command proof for workflow wiring rather than substring matching;
6. dynamic binding of live closure findings to the changed active WORK rather than hard-coded `WORK-0002`.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove this exact PROJECT_STATE synchronization descendant with the bootstrap self-test and live PR #2 GitHub contract probe.
2. Update PR #5's body to identify the exact new candidate, 17 open P1 findings, REQ-0026/TEST-0009/REVIEW-0031, and current exact-head proof.
3. Request a new fresh-context independent Codex review of that exact PR #5 HEAD. Keep all **17** PR #5 material threads unresolved while it runs.
4. If new material findings appear, correct them with dedicated regression/real-system evidence and repeat the exact-head review cycle.
5. If the fresh review is clean, independently resolve only the verified PR #5 threads and squash-merge PR #5 into `main` with an exact-head guard.
6. Re-query the new `main`, integrate it into PR #2 with an explicit two-parent merge that preserves the richer branch-local WORK-0002 tree, synchronize the six T12 PRRT identities for exact **73/73** durable/live equality, and add deterministic proof that the bootstrap trust surface is base-preexisting.
7. Re-prove PR #2 tests, 100% coverage, mutations, deterministic validators and live gate on the exact new HEAD.
8. Run another fresh-context independent L2 on PR #2. Do not resolve its 73 material threads before independent verification.
9. WORK-0002 still ultimately requires an eligible non-author exact-head GitHub `APPROVED` review satisfying the trusted/context-separated L2/L3 contract. Codex cannot substitute for that collaborator approval.
10. Only after WORK-0002 closes may WORK-0003 and WORK-0004 start.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. `registry/requirements/REQ-0026.yaml`
7. `registry/tests/TEST-0009.yaml`
8. `registry/reviews/REVIEW-0031.yaml`
9. live PR #5 exact HEAD/checks/reviews/threads
10. live PR #2 exact HEAD/checks/reviews/threads
11. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
