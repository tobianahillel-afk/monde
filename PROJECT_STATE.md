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

Fresh independent L2 review of PR #2 found that the stale-green review-thread poll introduced on the WORK-0002 branch cannot protect PR #2 before merge because GitHub scheduled workflows execute from the default branch. A small default-branch predecessor is therefore being proven separately in **PR #5 — `fix(governance): bootstrap stale-green thread polling`**.

This bridge belongs to WORK-0002/T12. It is not a new product capability and does not weaken any governance rule. Its sole purpose is to provide a trusted `main`-resident five-minute poll while PR #2 is still open. The bridge:

- enumerates open PRs and current review-thread state;
- queries only the canonical MONDE Gate workflow by stable workflow ID `354465551` and path `.github/workflows/governance.yml`;
- considers `pull_request`, `pull_request_review`, and `pull_request_review_comment` gate runs;
- reruns only a **successful** exact-head canonical gate when a live review thread is unresolved;
- fails closed on malformed REST/GraphQL data and bounded-pagination exhaustion;
- uses a scheduled job with `actions: write`, `contents: read`, and `pull-requests: read` only;
- provides a PR-only GitHub contract probe that is read-only and non-destructive.

The bootstrap is temporary. After PR #2 is merged, its canonical poller becomes the durable implementation; WORK-0003 may then rationalize/remove redundant bootstrap machinery when repository protection and merge discipline are configured.

## Exact bootstrap proof

Current proven bootstrap candidate before this documentation synchronization: **`d97af6b08801c160013261043218ffb9d37bae8d`**.

GitHub Actions run **`34987413138` / MONDE Stale-Green Bootstrap #8** passed both required proof lanes:

- **Bootstrap self-test: success**, with hash-locked `coverage.py` and enforced **100% line + branch coverage** over `.github/scripts/stale_green_bootstrap.py`;
- **Bootstrap GitHub contract probe: success**, exercising live GitHub REST, GraphQL review-thread and canonical Actions-run contracts on the exact PR head with read-only permissions and no rerun/mutation.

Earlier fresh Codex reviews on PR #5 found and drove correction of canonical-workflow identity binding, malformed REST/GraphQL fail-closed behavior, canonical-workflow pagination scope, coverage, real-system contract validation and durable state tracking. Those review threads remain unresolved pending another fresh exact-head independent review; author-side correction is not closure evidence.

## WORK-0002 / T12 relationship

PR #2 has a richer branch-local WORK-0002 record and remains the authoritative implementation state for T12. The default-branch mirror records only this bootstrap predecessor and the cross-branch handoff. After PR #5 is independently clean and merged, `main` must be integrated into PR #2 without discarding its richer T7–T12 state. T12 on PR #2 must then prove that the bootstrap is genuinely **base-preexisting** rather than self-authorized candidate state.

The fresh PR #2 L2 that opened T12 expanded the material unresolved set from 67 to **73** findings. All remain unresolved. The six T12 findings cover:

1. pre-merge deployment of stale-green polling on the default branch;
2. inclusion of review-event gate runs in stale-green selection;
3. ambiguity of imported terminal status across parallel history;
4. rejection of terminal external imports without `import_commit` binding;
5. executable-command proof for workflow wiring rather than substring matching;
6. dynamic binding of live closure findings to the changed active WORK rather than hard-coded `WORK-0002`.

## Repository visibility

MONDE intentionally remains **public**. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Current next action

1. Prove the exact PR #5 documentation/state-tracking descendant with the bootstrap self-test and live GitHub contract probe.
2. Request another fresh-context independent Codex review of that exact PR #5 HEAD. Keep all PR #5 review threads unresolved during the review.
3. If no new material issue appears, independently close the verified PR #5 threads and merge PR #5 into `main` with an exact-head guard.
4. Re-query the new `main`, integrate it into PR #2 while preserving the richer branch-local WORK-0002 state, and add a T12 closure check requiring the bootstrap predecessor to exist in the base/preexisting history.
5. Re-prove all T12 code, tests, mutations and durable 73-thread identity tracking on the exact PR #2 HEAD.
6. Run another fresh-context independent L2 on PR #2. Do not resolve its 73 material threads before independent verification.
7. WORK-0002 still ultimately requires an eligible non-author exact-head GitHub `APPROVED` review satisfying the trusted/context-separated L2/L3 contract. The Codex connector itself has no collaborator permission and cannot satisfy that approval requirement.
8. Only after WORK-0002 closes may WORK-0003 and WORK-0004 start.

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
