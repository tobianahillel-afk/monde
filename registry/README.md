# MONDE Registry Index

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

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

## Status integrity

Each registry defines its allowed lifecycle states. Governance tooling should reject unknown states and invalid transitions.

Do not use vague free-text status such as `almost_done` or `looks_good`.

## AI navigation rule

An agent should normally start from the active `WORK-*` record and traverse linked IDs/paths only as needed. The registry graph is intended to minimize context loading while preventing omission of critical dependencies.

## Generated indexes

As the repository grows, human-readable tables/search indexes should be generated from registry records rather than manually maintained copies. Generated views must never become a competing source of truth.

## Validation target

Future governance CI should validate:
- schema correctness;
- unique IDs;
- valid references;
- valid lifecycle transitions;
- required fields by status/risk;
- no orphan critical records;
- `read_before` paths;
- traceability completeness;
- assumption/risk review deadlines;
- DONE/Accepted evidence requirements.
