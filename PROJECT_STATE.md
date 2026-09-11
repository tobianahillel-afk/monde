# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git; live PR/check/thread truth lives in GitHub and must be rechecked before merge decisions.

## Current phase

**PHASE-0 — Specification, repository governance and canonical documentation**

## Current lot

**LOT-0 — AI-first repository operating system**

## Active work

- `WORK-0001` — corrective assurance closure on PR #3 / branch `chore/work-0001-assurance-closure`; it remains `IN_REVIEW` and blocks truthful completion of WORK-0002 until independently approved and merged.
- `WORK-0002` — governance automation on PR #2 / branch `feat/work-0002-governance-ci`; it remains `IN_REVIEW`.

No WORK-0003 or WORK-0004 implementation has started.

## Current WORK-0001 gate

PR #3 is the blocking dependency. Its current candidate was frozen at `06dbb76c68287130169d41f50b2464bc4f878bb5` with TEST-0006 PASS on finalized handover tree `b8180dff075ea5c8328ee56d1683380576c984ba` and TEST-0007 PASS on `669dcf7638746e07cc034cd69fa2cb08da133937`. A fresh-context L2 has been requested on the frozen PR #3 candidate. Recheck live PR #3 before any WORK-0002 completion or merge decision.

## WORK-0002 current scope

The branch implements deterministic governance validation, schema/status/reference/path checks, progress and review gates, lifecycle/change-control enforcement, context routing, live GitHub gating, supply-chain controls, CodeQL/Dependency Review, mutation smoke and the stable `MONDE / Merge Gate`.

The last fully green substantive predecessor was `c50c33009d90f079e645f0ca9e1befe1a4a77ba9`, with 76 tests, 100% line/branch coverage, 16/16 critical mutations, zero repository/strict/path/change-guard errors, CodeQL success and a green final live gate after the then-known threads were resolved.

## Latest fresh-context findings on PR #2

The latest Codex L2 on `c50c33009d90f079e645f0ca9e1befe1a4a77ba9` found six material gaps that define the current corrective slice:

1. A3/A4 assurance did not itself impose minimum review independence (`A3 ≥ L2`, `A4 ≥ L3`).
2. A COMPLETE review could be used without `artifact.commit_sha`, preventing exact freshness binding.
3. `status: PASS` test records could be structurally empty and still be trusted.
4. `NOT_APPLICABLE` progress dimensions were accepted without a non-empty work-item justification.
5. Context routing did not seed dependency closure from a changed non-WORK registry record such as `REQ-*`.
6. This handover still described obsolete pre-`c50c330` correction work instead of the actual current dependency/review state.

The current corrective commit must address all six with dedicated regression coverage and must not weaken prior gates.

## Current gate for WORK-0002

1. Keep WORK-0002 `IN_REVIEW`; do not mark it DONE while WORK-0001/PR #3 is unmerged.
2. Run the complete MONDE Gate on the current PR #2 HEAD after the six-finding correction. Treat any validator, coverage, mutation, CodeQL or live-gate failure as blocking evidence.
3. Reply to the six current Codex threads with exact-SHA proof after the real run. Do not close a finding merely because the author believes the fix is correct.
4. Once PR #3 merges, integrate the new `main` governance/lifecycle contract into PR #2 before claiming final freshness. Re-run the full gate after integration.
5. Obtain a new fresh-context L2 on the final integrated PR #2 HEAD. Only a clean/approval-capable independent result may close the remaining review gate.
6. After independent verification, finalize WORK-0002/progress/completion without rewriting historical evidence, run the gate on the merge candidate, and merge only if all live gates pass.
7. Continue with WORK-0003, then WORK-0004, in roadmap order.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials, tokens, secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material stays outside Git. WORK-0003 owns repository/ruleset/required-check/security-setting hardening while preserving public visibility.

## Product/UI/UX owner gate

Product specification and product identity are owner-gated decisions. Agents must not silently canonize the product experience, UI/UX, visual identity, brand, color system, interface density, interaction language, emotional/psychovisual tone, or other strong design choices. Before those areas become canonical, stop for an explicit co-design loop with the owner: present alternatives, ask focused questions, record the selected direction and only then proceed. The same rule applies to major product-function decisions: ask the owner rather than inventing irreversible product choices.

## Resume instructions

Minimum sequence:
1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/work-items/WORK-0002.yaml`
7. `registry/status-machines.yaml`
8. `registry/progress/matrix.yaml`
9. current PR #3 reviews/threads and HEAD
10. current PR #2 reviews/threads/checks and HEAD
11. `docs/03_ARCHITECTURE/github-control-plane.md`
12. `docs/13_QUALITY/ai-context-routing.md`
13. `tools/governance/`
14. `tests/governance/`

No prior chat history is required.