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

PR #5 (`chore/work-0002-stale-green-bootstrap`) is the narrow trusted-default-branch predecessor for WORK-0002/T12. The executable path is `.github/scripts/stale_green_bootstrap_pr_snapshot.py`.

The corrected candidate now:

1. double-reads stable unique open Pull Requests authority;
2. classifies exact merge-acceptable Checks + unresolved review threads before target discovery;
3. re-reads stable open authority immediately before target selection;
4. binds every canonical PR-family workflow run to its triggering PR through the exact reusable-workflow ref `refs/pull/<N>/merge` rather than dynamic `workflow_run.pull_requests[]` associations;
5. distinguishes same-repository/ref/SHA PRs by PR number and reruns only the stale PR's bound run;
6. validates the selected protected current-attempt `MONDE / Merge Gate` job;
7. routes all GitHub API calls through one invocation budget capped at **60** calls; the 61st call fails before network I/O and every invocation logs `used/60`;
8. retains filtered Actions window partitioning, stable unique snapshots, strict identifiers/attempts and fail-closed metadata validation.

Only the trusted scheduled default-branch path has `actions: write`; the live PR #2 probe remains read-only.

## Review lifecycle

- REVIEW-0031..0039: `COMPLETE / CHANGES_REQUIRED`.
- REVIEW-0040 and REVIEW-0041: `CLOSED` administrative negative evidence after author-side findings invalidated their frozen heads before independent review completion.
- REVIEW-0042: `COMPLETE / CHANGES_REQUIRED` on exact frozen HEAD `1120bbb9d1548bf0b20c6c1052731c0bf4154a00`; independent Codex review `PRR_kwDOUUI5ts8AAAABNxvvZg` added two P1s:
  - `PRRT_kwDOUUI5ts6i0j_C`: duplicate open repo/ref/SHA abort left the shared green check usable;
  - `PRRT_kwDOUUI5ts6i0j_F`: open authority could change after thread classification and before target selection.
- PR #5 has **44 inline material threads**, all still unresolved.
- REVIEW-0043 is the fresh successor L2. This checkpoint creates it as `OPEN`; it must be exact-head proven before transition to `IN_PROGRESS`.

## Corrective proof chain after REVIEW-0042

- `682a34d762bcceb24a066016496de7974c1ef046` — synchronized REVIEW-0042 terminal-negative checkpoint; Bootstrap #94 / `35067287447` self-test + live probe SUCCESS.
- `bea8e9fa28a7771c0642c5b3ad79fccbc37b3f40` — shared-head per-PR authority + late open-authority revalidation; Bootstrap #95 / `35068179930`: **79/79 tests**, **638 statements / 286 branches**, 100% line+branch, live PR #2 probe SUCCESS.
- `4f259e348953c0f45f7f1ed06497cbf554cec789` — global request budget; Bootstrap #96 / `35068715977`: **80/80 tests**, **652 statements / 288 branches**, 100% line+branch, live probe `7/60`; a local test regex emitted a SyntaxWarning.
- `b4f8e07b108b1ee881498b0a1b8b0e3afd007de0` — warning cleanup only; Bootstrap #97 / `35068890722`: **80/80 tests**, **652 statements / 288 branches**, 100% line+branch, live PR #2 probe SUCCESS with `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true` and `request budget: 7/60`. No project-code SyntaxWarning remains.

## Historical rate-limit P1

`PRRT_kwDOUUI5ts6is6BX` remains unresolved as a review thread, but the candidate now has executable quantitative containment: at most 60 script-issued GitHub API calls per invocation. With the ten-minute schedule, the scheduled bridge can issue at most **360 script calls/hour**, leaving explicit headroom under GitHub's documented 1,000 REST requests/hour/repository `GITHUB_TOKEN` primary limit; GraphQL calls are conservatively counted in the same local budget. REVIEW-0043 must challenge whether this is a sufficient supported-capacity contract and whether fail-closed budget exhaustion has acceptable operational semantics.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse this final behavior into `tools/governance/thread_state_poll.py`, including reusable-workflow per-PR authority, late open-authority revalidation, explicit request-budget controls and the existing exact-check/incarnation/snapshot/job guarantees.

A separate PR #2 handoff remains: pull-request base retargeting must positively create a fresh gate. `workflow_run.pull_requests[]` is dynamically refreshed and cannot serve as event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all 44 PR #5 inline material threads unresolved.
2. Prove this synchronized `REVIEW-0043 OPEN` + WORK-0002 + TEST-0009 + PROJECT_STATE checkpoint exactly.
3. If green, atomically transition REVIEW-0043 to `IN_PROGRESS`, synchronize WORK/PROJECT, and prove that exact descendant.
4. Freeze the proven IN_PROGRESS SHA and invoke fresh-context independent Codex REVIEW-0043.
5. REVIEW-0043 must re-check all 44 historical inline findings, both REVIEW-0042 P1s, the reusable-workflow PR-binding contract, remaining TOCTOU and the 60-call resource budget.
6. Any new material finding requires correction/re-proof and a successor review; do not resolve historical threads mechanically.
7. Only a clean exact-head independent successor review permits controlled verification/resolution and a guarded PR #5 merge decision.
8. After PR #5 merge, integrate main into PR #2, port durable parity, prove T12, run fresh PR #2 L2, obtain eligible non-author exact-head APPROVED review, then consider WORK-0002 closure.
9. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0042.yaml
9. registry/reviews/REVIEW-0043.yaml
10. live PR #5 exact HEAD/checks/reviews/threads
11. live PR #2 exact HEAD/checks/reviews/threads
12. PR #2 branch-local WORK-0002 / PROJECT_STATE after explicit integration checkout

MONDE remains public. Never commit credentials, tokens or secrets.