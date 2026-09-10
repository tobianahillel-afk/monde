# MONDE Registry Index

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-11

## Purpose

The `registry/` tree is MONDE's machine-readable project memory. Human-readable documentation explains concepts; registries provide stable identities, status and links so humans and AI agents can navigate, validate and automate the project without reconstructing state from prose.

## ID namespaces

| Prefix | Registry | Meaning |
|---|---|---|
| `WORK-*` | `registry/work-items/` | Executable engineering/specification objective |
| `CAP-*` | `registry/capabilities/` | Stable product capability |
| `REQ-*` | `registry/requirements/` | Atomic normative requirement |
| `ASM-*` | `registry/assumptions/` | Material uncertain premise |
| `RISK-*` | `registry/risks/` | Tracked failure/risk proposition |
| `REVIEW-*` | `registry/reviews/` | Structured independent review evidence |
| `TEST-*` | `registry/tests/` | Important test/verification artifact |
| `EXP-*` | `registry/experiments/` | Reproducible experiment/backtest |
| `DEP-*` | `registry/dependencies/` | Typed dependency/reuse relation |
| future `ENGINE-*` | `registry/engines/` | Intelligence/core engine identity |
| future `SRC-*` | `registry/sources/` | Source definition |
| future `DATASET-*` | `registry/datasets/` | Dataset/data-product identity |
| future `MODEL-*` | `registry/models/` | Model identity/version family |
| future `METRIC-*` | `registry/metrics/` | Canonical metric semantics |
| future `SLO-*` | `registry/slos/` | Service/reliability objective |
| future `LENS-*` | `registry/lenses/` | Lens identity |

ADRs live in `docs/11_ADR/` with immutable `ADR-*` IDs.

## Global ID rules

1. IDs are immutable once published/merged.
2. Deleted/superseded records retain their IDs historically.
3. Never reuse an ID.
4. Renaming does not imply a new ID when semantics remain the same.
5. Semantic split/merge must preserve mapping history.
6. References use IDs, not only free-text names.
7. Human-friendly names can change; stable IDs are the integration contract.

## Registry versus documentation

Use a registry when MONDE needs to answer mechanically:
- does this thing exist?
- what is its status?
- what does it depend on?
- what references it?
- what proves it?
- what superseded it?

Use canonical documentation for:
- detailed semantics;
- rationale;
- architecture;
- examples/counterexamples;
- operating procedures.

Do not duplicate long specifications into YAML records.

## Core traceability graph

The target relationship is:

`REQ → CAP → ADR/DESIGN → ENGINE/SCHEMA → WORK → TEST/EXP → REVIEW → VALIDATION/OBSERVABILITY`

`ASM` and `RISK` attach anywhere they materially affect the chain.

A material accepted governance behavior is not exempt merely because no product capability exists yet: it still requires a stable `REQ-*` identity and a verification/review path. Bootstrap requirements may therefore trace directly `REQ → WORK → TEST/REVIEW` until product capability records exist.

## Status integrity

`registry/status-machines.yaml` is the single machine-readable lifecycle contract for current registries **and for progress state**. It defines registry initial states, allowed states, valid transitions, review outcome/disposition vocabulary, the progress lifecycle used by phase/lot/sublot/task/run/quality dimensions, and any exact historical migration/import/replay exception needed to preserve immutable Git history.

Rules:
1. A registry record may use only states declared for that registry.
2. A transition must be explicitly allowed by that registry's machine; metadata-only edits may retain the same state.
3. `registry/progress/matrix.yaml` stores current progress instances only; it does not define or duplicate a status vocabulary.
4. A matrix WORK status mirrors the `work_items` registry machine; other progress-bearing matrix/task/run/dimension state uses `status-machines.yaml#progress`.
5. `NOT_APPLICABLE` is a progress-dimension state, not a universal registry state, and requires a non-empty work-item justification.
6. A progress dimension already marked `DONE` may move back to `IN_REVIEW` only when new evidence, a review finding, dependency change, or invalidated proof materially re-questions prior completion. The owning WORK/project handover must identify the trigger, affected downstream completion assumptions must be re-evaluated, and normal gates apply before it returns to `DONE`.
7. Historical transition/import/replay exceptions do not create generic shortcuts. Each exception must identify the exact record and exact Git boundary it preserves, explain why immutable history cannot be repaired honestly, forbid future reuse, and receive independent review.
8. A lifecycle checkpoint is evidence only if that state existed while the governed activity was actually in that state. Replaying `OPEN → IN_PROGRESS → COMPLETE` after an external review already finished is not repository-native execution evidence.
9. If a review completed externally before its REVIEW record is materialized, the normal post-v7 path is a one-shot preauthorized import: a matching authorization must already exist in an earlier parent commit, bind the record/result/reviewed SHA/source review, and the actual import commit must be recorded afterward before the review can satisfy a completion gate.
10. An external-import authorization is consumable once. A consumed authorization cannot be reused by another review or commit.
11. Lifecycle changes are governance changes: update the canonical machine, affected templates/schemas/validators, migrations and review evidence together rather than adding an ad-hoc state locally.
12. Governance tooling must fail closed on unknown states, invalid transitions, unbound external imports and migration/import/replay-exception mismatches.

Human-readable registry-specific documents may explain these states but must not define a competing lifecycle truth.

## AI navigation rule

An agent should normally start from the active `WORK-*` record and traverse linked IDs/paths only as needed. The registry graph is intended to minimize context loading while preventing omission of critical dependencies.

## Generated indexes

As the repository grows, human-readable tables/search indexes should be generated from registry records rather than manually maintained copies. Generated views must never become a competing source of truth.

## Validation target

Governance CI should validate:
- schema correctness;
- unique IDs;
- valid references;
- registry-specific and progress lifecycle states/transitions from `registry/status-machines.yaml`;
- exact matching and non-reusability of any declared historical transition/import/replay exception;
- external-review import authorization exists in an earlier parent commit, matches the source review/result/artifact, is consumed once and is bound afterward to the actual import commit;
- required fields by status/risk;
- no orphan critical/material records;
- `read_before` paths;
- traceability completeness;
- assumption/risk review deadlines;
- DONE/Accepted evidence requirements;
- progress `NOT_APPLICABLE` justifications;
- reviewed reopening evidence for any `DONE → IN_REVIEW` progress regression.
