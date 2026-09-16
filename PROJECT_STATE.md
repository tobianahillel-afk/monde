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

PR #5 (`chore/work-0002-stale-green-bootstrap`) remains the narrow trusted-default-branch predecessor for WORK-0002/T12. No merge and no review-thread resolution is permitted while the current material findings remain open.

## Review lifecycle

- REVIEW-0031..0039: terminal `COMPLETE / CHANGES_REQUIRED` negative evidence.
- REVIEW-0040 and REVIEW-0041: `CLOSED` administrative negative evidence after author-side findings invalidated their frozen heads before independent review completion.
- REVIEW-0042: `COMPLETE / CHANGES_REQUIRED` on `1120bbb9d1548bf0b20c6c1052731c0bf4154a00`, adding P1s `PRRT_kwDOUUI5ts6i0j_C` and `PRRT_kwDOUUI5ts6i0j_F`.
- REVIEW-0043: **`COMPLETE / CHANGES_REQUIRED`** on exact frozen HEAD `3bce7808d7d30b361559d54663bc0808ab4cdcf6`; independent Codex review `PRR_kwDOUUI5ts8AAAABNyER4A` added:
  - `PRRT_kwDOUUI5ts6i1TEN` — 14 distinct stale-green heads consume all 60 calls before the first rerun; the 61st target-job request fails, no invalidation occurs, and every later schedule repeats the same zero-progress state.
  - `PRRT_kwDOUUI5ts6i1TES` — shared-head PR thread state can change after initial classification; rerunning a now-clean sibling can finish last and restore a green SHA-scoped required check while another sibling remains unresolved.
- PR #5 therefore has **46 inline material threads**, all still unresolved.

## Exact proof chain

- `682a34d762bcceb24a066016496de7974c1ef046` — REVIEW-0042 terminal-negative checkpoint; Bootstrap #94 / `35067287447` green.
- `bea8e9fa28a7771c0642c5b3ad79fccbc37b3f40` — PR-bound `refs/pull/<N>/merge` authority + late open-authority revalidation; #95 / `35068179930`: 79 tests, 638 statements, 286 branches, 100% + live probe.
- `4f259e348953c0f45f7f1ed06497cbf554cec789` — 60-call hard budget; #96 / `35068715977`: 80 tests, 652 statements, 288 branches, 100%, live probe 7/60.
- `b4f8e07b108b1ee881498b0a1b8b0e3afd007de0` — warning cleanup; #97 / `35068890722` same proof, no project-code SyntaxWarning.
- REVIEW-0043 OPEN `0137f18306af30c5fecf786bbcc864fc0732314d` — #98 / `35069264480` green.
- REVIEW-0043 IN_PROGRESS exact `3bce7808d7d30b361559d54663bc0808ab4cdcf6` — #99 / `35069698601`: **80/80 tests, 652 statements, 288 branches, 100% line+branch**, live PR #2 probe `open_prs=2, gate_heads=1, target_pr=2, unresolved_threads=true`, request consumption `7/60`; subsequently rejected by independent REVIEW-0043.

## What REVIEW-0043 disproved

The 60-call guard solved unbounded token consumption but did **not** solve REQ-0026 availability semantics. In a one-page nominal case with 14 stale-green unique heads, the bridge spends 2 open-snapshot calls + 14 Checks + 14 GraphQL + 2 fresh-open calls + 28 double Actions-history reads = 60 before any target job/rerun. The next request is blocked, no required check changes, and the same state repeats forever. Resource bounding must therefore preserve forward progress/fairness rather than fail before mutation.

PR identity revalidation is also insufficient for shared heads: review-thread state itself must be reclassified close enough to rerun, and/or the shared SHA must be verified after reruns so a clean sibling cannot revive merge eligibility for an unresolved sibling.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch. After PR #5 eventually merges, PR #2 must integrate new `main` and port/reuse the final trusted-base behavior into `tools/governance/thread_state_poll.py`, including the eventual progress-preserving resource strategy and shared-head final-state protection.

Separate handoff remains: pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## Current next action

1. Keep all 46 PR #5 inline material threads unresolved.
2. Prove this synchronized REVIEW-0043 terminal-negative / WORK-0002 / PROJECT_STATE checkpoint exactly.
3. Correct both REVIEW-0043 P1s:
   - replace cap-before-mutation behavior with a bounded progress/fair batching strategy that cannot permanently starve stale PRs;
   - reclassify current thread state immediately before shared-head reruns and protect against a clean sibling restoring the shared check green.
4. Add adversarial regressions for the 14-head zero-progress case and shared-head unresolved→resolved transition.
5. Re-prove exact-head line/branch coverage + live PR #2 contract behavior.
6. Open a fresh successor review only after the corrective candidate is green; lifecycle checkpoints must themselves be proven.
7. Any new material finding requires another successor; do not mechanically resolve historical threads.
8. Only a clean exact-head successor permits controlled verification/resolution and guarded PR #5 merge consideration.
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
10. live PR #5 exact HEAD/checks/reviews/46 threads
11. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.