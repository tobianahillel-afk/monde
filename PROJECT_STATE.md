# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- PHASE-0 and LOT-0 remain `IN_PROGRESS`.
- WORK-0001 is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- WORK-0002 remains `IN_REVIEW / A3` on PR #2 / `feat/work-0002-governance-ci`.
- WORK-0003 and WORK-0004 remain blocked until WORK-0002 independently closes.

## PR #5 / T12 trusted predecessor

PR #5 (`chore/work-0002-stale-green-bootstrap`) is the narrow trusted-default-branch predecessor for WORK-0002/T12. It currently executes through `.github/scripts/stale_green_bootstrap_pr_snapshot.py` and uses exact Checks authority, stable unique open/closed PR snapshots, stale-green-first thread classification, bounded/stable Actions target discovery, current-incarnation filtering, strict identifiers/attempts and protected target-job validation. Only the trusted scheduled path has `actions: write`; the live probe is read-only.

## Review lifecycle

- REVIEW-0031..0039: `COMPLETE / CHANGES_REQUIRED`.
- REVIEW-0040: `CLOSED` after author-side ordering-race P1 invalidated its frozen head before independent review.
- REVIEW-0041: `CLOSED` after author-side Pull Requests pagination/snapshot P1 invalidated its frozen head before independent review.
- REVIEW-0042: `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `1120bbb9d1548bf0b20c6c1052731c0bf4154a00` from independent Codex review `PRR_kwDOUUI5ts8AAAABNxvvZg`, submitted `2026-09-16T07:07:05Z`.
- REVIEW-0042 added:
  - `PRRT_kwDOUUI5ts6i0j_C`: two open PRs with the same repository/ref/SHA but divergent thread state cannot be handled by merely aborting the poll, because the shared green check remains usable.
  - `PRRT_kwDOUUI5ts6i0j_F`: a same-identity PR can open after the initial stable snapshot and before target selection, allowing its newer run to be selected for the stale PR.
- PR #5 now has **44 inline material threads**, all unresolved.

## Exact proof chain

- Pull Requests snapshot correction `5d4e3a5578d4ccf26ca8b89d0717a150d6d6102b` — Bootstrap #91 / `35034183087`: 72 tests, 506 statements, 222 branches, 100% line+branch, live adapter probe SUCCESS.
- REVIEW-0042 OPEN `e629ca97ed608f523802375f184c72580b0c7e3a` — #92 / `35034454790`: self-test and live probe SUCCESS.
- REVIEW-0042 IN_PROGRESS frozen HEAD `1120bbb9d1548bf0b20c6c1052731c0bf4154a00` — #93 / `35034635337`: 72/72 tests, 506 statements, 222 branches, 100% line+branch, live adapter-based PR #2 probe SUCCESS. REVIEW-0042 then returned CHANGES_REQUIRED with the two P1 findings above.

## Remaining SRE concern

Historical P1 `PRRT_kwDOUUI5ts6is6BX` remains unresolved. Moving the schedule to ten minutes reduces API pressure but is not a quantitative proof that the GitHub-token rate-limit failure class is closed. The successor must either correct the request pattern or establish/enforce an explicit supported-capacity contract with quantitative evidence.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final hardened bootstrap behavior into `tools/governance/thread_state_poll.py`. This includes shared-head per-PR authority, late open-authority revalidation, quantitative request-budget controls and the existing exact-check/incarnation/snapshot/job guarantees.

A separate durable PR #2 handoff finding also remains: a pull-request base retarget must positively create a fresh gate. The current durable workflow consumes `github.event.pull_request.base.sha` but does not subscribe to `pull_request: edited`; GitHub workflow-run `pull_requests[]` associations are dynamically refreshed and cannot prove original event-time base/head provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 and eligible trusted non-author exact-head APPROVED collaborator evidence.

## Current next action

1. Keep all 44 PR #5 inline material threads unresolved.
2. Materialize REVIEW-0042 `COMPLETE / CHANGES_REQUIRED` in synchronized REVIEW/WORK/PROJECT state.
3. Correct both REVIEW-0042 P1s: shared-head per-PR invalidation and late open-authority TOCTOU.
4. Add regressions for both cases.
5. Revisit `PRRT_kwDOUUI5ts6is6BX` with quantitative request-budget evidence/correction.
6. Re-prove the corrective exact head at 100% line+branch plus live read-only PR #2 probe.
7. Open and prove a fresh successor L2 review; do not resolve historical threads before a clean successor review.
8. Only then consider controlled thread resolution and a guarded PR #5 merge decision.
9. After PR #5 merge, integrate main into PR #2, port durable parity, prove T12, complete fresh PR #2 review/approval, then consider WORK-0002 closure.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0040.yaml
9. registry/reviews/REVIEW-0041.yaml
10. registry/reviews/REVIEW-0042.yaml
11. live PR #5 HEAD/checks/reviews/threads
12. live PR #2 HEAD/checks/reviews/threads
13. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit integration checkout

MONDE remains public. Never commit credentials, tokens or secrets.
