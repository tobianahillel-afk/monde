# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git; live PR/check/thread truth lives in GitHub and must be rechecked before merge decisions.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

## Current blocking sublot

**SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**

PR #1 was already squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`. WORK-0001 remained `IN_REVIEW` because its A3 assurance debt had not received a fresh-context L2 review before that merge.

## Active work

- `WORK-0001` — post-merge assurance correction on **PR #3** / branch `chore/work-0001-assurance-closure`; it blocks truthful completion of WORK-0002.
- `WORK-0002` — governance automation on open PR #2 / branch `feat/work-0002-governance-ci`; implementation is advanced but remains `IN_REVIEW` and depends on WORK-0001.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 review history

Fresh-context Codex review of merged bootstrap commit `b88e9edf2a`, recorded as `REVIEW-0003`, found three material gaps: missing atomic REQ identities, missing registry-specific lifecycle machines, and stale post-merge handover state.

PR #3 corrected that first set and was re-reviewed at HEAD `2d4dea7e51a6cc55b159ff3001637e3ca8ec3ee9`. That fresh L2 found six additional issues, all still open until correction and proof:

1. P1 — TEST-0001 had been retrofitted to claim coverage of corrective files while its execution SHA remained the older merge;
2. P1 — REVIEW-0001 had been retrofitted with REQ-0001..REQ-0014 although those records did not exist when it ran;
3. P1 — review `CLOSED` state could incorrectly count as approval evidence;
4. P1 — progress had a state list but no canonical initial state/transition table and duplicated the matrix vocabulary;
5. P1 — existing NOT_APPLICABLE dimensions in WORK-0002/0003/0004 lacked work-item justifications;
6. P2 — REQ-0008 overlapped REQ-0012 by also owning non-compensable hard-gate behavior.

The current correction preserves historical TEST/REVIEW boundaries, makes `status-machines.yaml` the sole lifecycle vocabulary (including progress transitions), supplies all current N/A justifications, and leaves hard-gate ownership exclusively with REQ-0012. A new fresh-context L2 is required after evidence for this corrected HEAD is recorded.

## WORK-0002 state

PR #2 substantive HEAD `c50c33009d90f079e645f0ca9e1befe1a4a77ba9` previously passed MONDE Gate run `34509930758` after its then-known threads were resolved. A newer fresh-context L2 on that same HEAD found six additional issues that remain open: assurance-derived minimum review independence, mandatory reviewed SHA for completed reviews, substantive PASS test evidence, N/A justification enforcement, direct changed-registry context seeding, and stale handover state.

WORK-0002 remains `IN_REVIEW`; do not merge or mark it DONE before WORK-0001 is DONE and those six findings are corrected, re-proven and freshly re-reviewed.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle/traceability correction

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. `registry/progress/matrix.yaml` stores state instances only and does not define a second vocabulary.

WORK-0001 material bootstrap behavior is normalized into `REQ-0001` through `REQ-0014`. Historical TEST-0001 and REVIEW-0001 remain bound to what actually existed when they ran; corrective evidence is recorded separately.

## Next action

1. Finish the six-finding correction on PR #3 and record a new SHA-bound corrective TEST record.
2. Reply to the six threads only after that evidence exists; resolve them only after the correction is independently re-reviewed.
3. Obtain a fresh-context L2 review on the corrected PR #3 HEAD and fix any further material finding.
4. Only after approval, finalize REVIEW/progress/WORK-0001 completion evidence and merge PR #3.
5. Rebase/update PR #2 on the new main contract, then fix its six current fresh-L2 findings with regression/mutation tests and exact-SHA CI proof.
6. Obtain a fresh L2 on corrected PR #2; only then finalize/merge WORK-0002.
7. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

## Resume instructions

Minimum manual sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/status-machines.yaml`
7. `registry/requirements/REQ-0001.yaml` through `REQ-0014.yaml`
8. `registry/reviews/REVIEW-0003.yaml` and subsequent PR #3 review evidence
9. corrective TEST record plus historical `registry/tests/TEST-0001.yaml`
10. live PR #3 checks/review threads
11. live PR #2 checks and unresolved threads

No prior chat history is required.
