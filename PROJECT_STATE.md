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

PR #3 corrected that first set and was re-reviewed at HEAD `2d4dea7e51a6cc55b159ff3001637e3ca8ec3ee9`. That L2, recorded as `REVIEW-0004`, found six additional issues: historical TEST/REVIEW evidence had been widened, CLOSED reviews could count as approval, progress lacked explicit transitions/single-source vocabulary, current N/A values lacked justifications, and REQ-0008 overlapped REQ-0012.

`TEST-0004` was then executed against exact corrective tree `23ef1a88e9a5106b12144d4c6649868a6a691a8f` and recorded PASS in commit `e8337d833ca0b524bed69318ca4b3691c9ce6c23`.

A new fresh-context Codex L2 on HEAD `d5be907160c7fad3d86b2e0ce84911a3dcaab7d9`, recorded as `REVIEW-0005`, found three further issues:

1. historical TEST-0001 was still an active PASS despite `execution.commit_sha: null`;
2. an R1/R2 finding could be marked `ACCEPTED` without explicit accepting authority/evidence;
3. REQ-0010 was compound and mixed several independently fail-able specification-governance obligations.

The third corrective pass supersedes TEST-0001 without inventing a historical SHA, makes blocking-finding acceptance authority machine-representable, records the owner authority for REVIEW-0001/F-3, and splits AC-10 normative ownership across atomic REQ-0010 plus REQ-0015..REQ-0019.

`TEST-0005` was executed against exact substantive corrective tree `2712795dc9f10c1efed2088313d125f6f915cc98` and records PASS. Its lifecycle was recorded through PLANNED → READY → RUNNING → PASS; the PASS record is committed as `89d39c75fe29d8bbcbe016cecaa6c87d935f1c47`. Another fresh-context L2 is now required before any REVIEW-0004/REVIEW-0005 finding is closed or WORK-0001 becomes DONE.

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

`registry/status-machines.yaml` is the single lifecycle source of truth for registry and progress statuses/transitions. Active state-bound PASS evidence requires an exact tested commit SHA; unprovable legacy PASS evidence is superseded rather than repaired by guessing.

A blocking R1/R2 finding may be non-blocking through `ACCEPTED` only with explicit accepting actor, authority role, authority evidence, rationale, date and review condition appropriate to the work item's assurance level.

WORK-0001 material bootstrap behavior is represented by `REQ-0001` through `REQ-0019`. AC-10 deliberately maps to several atomic normative owners: REQ-0010 and REQ-0015..REQ-0019.

## Next action

1. Attach TEST-0005 exact-SHA proof to the three REVIEW-0005 GitHub threads without resolving them.
2. Request another fresh-context L2 review of the current PR #3 HEAD.
3. If the reviewer finds anything material, correct and re-prove it; otherwise record the approving review and verify the REVIEW-0004/REVIEW-0005 findings as resolved.
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
7. `registry/requirements/REQ-0001.yaml` through `REQ-0019.yaml`
8. `registry/reviews/REVIEW-0003.yaml`, `REVIEW-0004.yaml`, and `REVIEW-0005.yaml`
9. `registry/tests/TEST-0004.yaml`, `TEST-0005.yaml`, plus superseded historical `TEST-0001.yaml`
10. live PR #3 reviews/threads
11. live PR #2 checks and unresolved threads

No prior chat history is required.
