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

- `WORK-0001` — post-merge assurance correction on branch `chore/work-0001-assurance-closure`; it blocks truthful completion of WORK-0002.
- `WORK-0002` — governance automation on open PR #2 / branch `feat/work-0002-governance-ci`; implementation is advanced but remains `IN_REVIEW` and depends on WORK-0001.

No WORK-0003 or WORK-0004 implementation has started.

## Current status

`IN_REVIEW`

## WORK-0001 fresh L2 result

A fresh-context GitHub Codex review was executed against merged bootstrap commit `b88e9edf2a` and is recorded as `REVIEW-0003`. It found three material gaps:

1. P1 — the fourteen material bootstrap acceptance criteria had no atomic `REQ-*` identities or REQ→TEST/REVIEW trace;
2. P1 — registry-specific lifecycle vocabularies/transitions were not canonically defined for REQ/ASM/RISK/REVIEW/TEST/EXP/DEP and related registries;
3. P2 — this handover file still instructed agents to review/merge PR #1 after it had already merged.

The current corrective branch addresses those findings by adding `REQ-0001` through `REQ-0014`, centralizing lifecycle truth in `registry/status-machines.yaml`, strengthening TEST-0001 traceability, and replacing the stale handover state. These corrections still require a fresh L2 re-review before WORK-0001 can become DONE.

## WORK-0002 state

PR #2 current substantive HEAD is `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`.

MONDE Gate run `34509930758` is green after rerunning its live final gate: 76 tests, 100% line/branch coverage, 16/16 critical mutations, repository/strict/path/change validators green, context manifest generated, CodeQL green, and live review-thread gate green for the findings known before the newest review.

A newer fresh-context Codex review on `c50c33009d` then found six additional issues that remain open and must **not** be resolved until corrected and CI-proven:

1. P1 — minimum review independence must derive from assurance level, not only the work's declared target;
2. P1 — COMPLETE/CLOSED review evidence must be bound to a reviewed commit SHA;
3. P1 — TEST status PASS must require substantive execution/protection/evidence fields;
4. P1 — progress `NOT_APPLICABLE` must require a work-item justification;
5. P2 — context routing must seed graph closure from directly changed non-WORK registry records;
6. P2 — PR #2 handover state was stale relative to its current HEAD/review history.

WORK-0002 remains `IN_REVIEW`; do not merge or mark it DONE before WORK-0001 is DONE and these six findings are corrected, re-proven and freshly re-reviewed.

## Repository visibility decision

The repository intentionally remains **public** by explicit owner decision. This is not a pending privatization task.

Public-code-safe constraints are mandatory:
- never commit credentials, tokens or secrets;
- never commit private/personal datasets or user-identifying runtime data;
- keep sensitive runtime data and secrets outside Git in appropriate stores/secret managers;
- WORK-0003 will harden branch/ruleset/required-check/merge/security settings while preserving public visibility.

## Canonical lifecycle/traceability correction

`registry/status-machines.yaml` is the lifecycle source of truth for current registry statuses/transitions. `registry/progress/matrix.yaml` remains the project/work progress view and must not be treated as a universal status vocabulary.

WORK-0001 material bootstrap behavior is normalized into `REQ-0001` through `REQ-0014`; TEST-0001 and review evidence link to these requirements.

## Next action

1. Open a corrective PR from `chore/work-0001-assurance-closure` to `main`.
2. Re-run a fresh-context L2 review on the complete corrective diff; fix any new material finding rather than force-closing it.
3. Only after the correction is approved, update REVIEW/TEST/progress/WORK-0001 completion evidence and merge the corrective PR.
4. Rebase/update PR #2 on the new main contract, then fix its six current fresh-L2 findings with regression/mutation tests and exact-SHA CI proof.
5. Obtain a fresh L2 on the corrected PR #2 head; only then finalize/merge WORK-0002.
6. Start WORK-0003 after WORK-0002; WORK-0004 remains after WORK-0003.

## Resume instructions

Minimum manual sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/status-machines.yaml`
7. `registry/requirements/REQ-0001.yaml` through `REQ-0014.yaml`
8. `registry/reviews/REVIEW-0003.yaml`
9. `registry/tests/TEST-0001.yaml`
10. live corrective-PR state once opened
11. live PR #2 checks and unresolved threads

No prior chat history is required.
