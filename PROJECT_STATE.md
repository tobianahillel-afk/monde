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

- enumerates open PRs and validates their server-reported `head.repo.full_name`, `head.ref`, and `head.sha`;
- rejects two open PRs whose complete `(head repository, branch, SHA)` identity is indistinguishable instead of guessing which PR a run belongs to;
- queries only canonical MONDE Gate workflow ID `354465551` and verifies path `.github/workflows/governance.yml`;
- validates each PR-family run using GitHub-server `head_repository.full_name`, `head_branch`, and `head_sha`, and deliberately does **not** treat the ambiguous `workflow_run.pull_requests` association list as triggering-PR identity;
- considers `pull_request`, `pull_request_review`, and `pull_request_review_comment` gate runs;
- computes the newest effective commit-scoped gate state by `updated_at`, then run number/id as deterministic tie-breakers;
- when another PR sharing a SHA re-greens the commit, reruns the target PR's own head-identity-bound run if that PR still has unresolved threads;
- validates terminal conclusions and timezone-aware timestamps fail-closed;
- bounds REST pagination and GraphQL review-thread pagination to `MAX_PAGES`, rejecting malformed metadata, missing/repeated cursors and exhaustion;
- grants `actions: write` only to the trusted scheduled poll job; the PR validation probe remains read-only and non-destructive.

The bootstrap is temporary. After PR #2 is merged, its canonical poller becomes the durable implementation; WORK-0003 may then rationalize/remove redundant bootstrap machinery when repository protection and merge discipline are configured.

## Exact bootstrap proof

Latest proven substantive bootstrap candidate before this documentation synchronization: **`68115ec3c548c428d21bd4a7b6ad0c58f13b5752`**.

GitHub Actions run **`34992248872` / MONDE Stale-Green Bootstrap #18** passed both required proof lanes:

- **Bootstrap self-test: SUCCESS** — **23/23 tests**, **207/207 statements**, **80/80 branches**, **100% line + branch coverage** over `.github/scripts/stale_green_bootstrap.py`;
- **Bootstrap GitHub contract probe: SUCCESS** — read-only live GitHub REST/GraphQL/Actions validation against **PR #2**, the actual WORK-0002 consumer. The probe observed `open_prs=2`, `gate_heads=193`, successfully bound canonical runs through GitHub-server head repository/ref/SHA metadata, and confirmed `unresolved_threads=true` for PR #2.

An intermediate exact-head run `34992135223` on `088fdc1016c271b74ed541414c741c2816e5ba04` intentionally failed its contract probe because it attempted to require a canonical MONDE Gate run for PR #5 itself. PR #5 does not contain the canonical gate; that gate lives on PR #2. Run #18 corrects the probe to exercise the real consumer contract instead of an impossible bootstrap-PR contract.

## PR #5 independent review state

All material PR #5 review threads remain unresolved. Successive fresh Codex reviews have identified **14 P1 findings** so far:

- `PRR_kwDOUUI5ts8AAAABNpylnA`: canonical workflow identity; malformed REST collection handling; malformed GraphQL metadata;
- `PRR_kwDOUUI5ts8AAAABNqb2xg`: canonical-workflow pagination scope; durable WORK/PROJECT_STATE ownership; 100% coverage; real-system GitHub validation;
- `PRR_kwDOUUI5ts8AAAABNqnqWQ`: validate run event before filtering; distinguish runs sharing a commit;
- `PRR_kwDOUUI5ts8AAAABNqx3YA`: reinvalidate shared-head cross-PR success; reject unknown conclusions; reject Boolean PR numbers;
- `PRR_kwDOUUI5ts8AAAABNq6L4g`: do not treat `workflow_run.pull_requests` association cardinality as triggering-PR identity; record exact current proof in durable repository state.

The exact thread identities are:

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

Author-side correction is not closure evidence. These threads stay open until a new fresh exact-head independent review verifies the synchronized final candidate.

## WORK-0002 / T12 relationship

PR #2 has the richer branch-local WORK-0002 record and remains authoritative for T7–T12 implementation history. The default-branch mirror records only the bootstrap predecessor and cross-branch handoff. After PR #5 is independently clean and merged, `main` must be integrated into PR #2 without discarding that richer state. T12 must then prove the bootstrap is genuinely **base-preexisting** rather than candidate-created.

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

1. Prove this exact documentation/state synchronization descendant with the bootstrap self-test and live PR #2 GitHub contract probe.
2. Request a new fresh-context independent Codex review of that exact PR #5 HEAD. Keep all **14** PR #5 material threads unresolved while it runs.
3. If new material findings appear, correct them with dedicated regression/real-system evidence and repeat the exact-head review cycle.
4. If the fresh review is clean, independently resolve only the verified PR #5 threads and squash-merge PR #5 into `main` with an exact-head guard.
5. Re-query the new `main`, integrate it into PR #2 with an explicit two-parent merge that preserves the richer branch-local WORK-0002 tree, synchronize the six T12 PRRT identities for exact **73/73** durable/live equality, and prove the bootstrap predecessor is base-preexisting.
6. Re-prove PR #2 tests, 100% coverage, mutations, deterministic validators and live gate on the exact new HEAD.
7. Run another fresh-context independent L2 on PR #2. Do not resolve its 73 material threads before independent verification.
8. WORK-0002 still ultimately requires an eligible non-author exact-head GitHub `APPROVED` review satisfying the trusted/context-separated L2/L3 contract. Codex cannot substitute for that collaborator approval.
9. Only after WORK-0002 closes may WORK-0003 and WORK-0004 start.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0002.yaml`
6. live PR #5 exact HEAD/checks/reviews/threads
7. live PR #2 exact HEAD/checks/reviews/threads
8. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit checkout

No prior chat history is required.
