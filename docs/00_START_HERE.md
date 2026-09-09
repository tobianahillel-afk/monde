# START HERE — MONDE repository navigation

Status: Accepted  
Canonical: Yes

This file defines **how any human or AI resumes MONDE safely**.

## Fast resume — existing work

If you are continuing work already started, do **not** read the whole repository.

Read in this exact order:

1. `README.md`
2. `AGENTS.md`
3. `PROJECT_STATE.md`
4. active `registry/work-items/WORK-*.yaml`
5. every path listed under the work item's `read_before`
6. referenced ADRs under `docs/11_ADR/`
7. exact dependency/reuse entries linked by the work item
8. recent commits/PR discussion for that work item

Only expand beyond these files if the work item or dependency graph requires it.

## New work — no existing work item

Before coding:

1. Read `README.md` and `AGENTS.md`.
2. Read product material relevant to the request.
3. Search `registry/capabilities/` to determine whether the capability already exists.
4. Search `registry/work-items/` for active/planned overlapping work.
5. Search the repository for reusable implementation.
6. Read relevant architecture docs and ADRs.
7. Create a work item using `registry/work-items/_TEMPLATE.yaml`.
8. Declare dependencies, reuse, acceptance criteria and required tests.
9. Update `PROJECT_STATE.md` if the new work becomes active.
10. Implement only after the work item is reviewable.

## Canonical document hierarchy

When documents conflict, use this precedence unless an ADR explicitly supersedes it:

1. `docs/09_GOVERNANCE/constitution.md`
2. Accepted ADRs
3. Canonical schemas/contracts
4. Capability/engine/source/model registries
5. Accepted architecture documents
6. Accepted product documents
7. Active work-item acceptance criteria
8. Draft/research documents
9. Historical chat/context

Chat is useful context, not canonical repository state.

## Documentation map

| Path | Meaning |
|---|---|
| `docs/01_PRODUCT/` | Product vision, scope, principles and vocabulary |
| `docs/02_WORLD_MODEL/` | Canonical world, evidence, temporal, identity and uncertainty semantics |
| `docs/03_ARCHITECTURE/` | Runtime/system architecture and architectural maps |
| `docs/04_DATA/` | Data strategy, sources, acquisition, provenance and retention |
| `docs/05_INTELLIGENCE_ENGINES/` | Engine specifications |
| `docs/06_CAPABILITIES/` | Capability semantics and registry guidance |
| `docs/07_EXPERIENCES/` | Console, Globe and user workflows |
| `docs/08_MODELS/` | AI/model strategy and evaluation |
| `docs/09_GOVERNANCE/` | Constitution, permissions, engineering and high-risk boundaries |
| `docs/10_ROADMAP/` | Phases, lots, sublots and release/development process |
| `docs/11_ADR/` | Architecture Decision Records |
| `docs/12_RESEARCH/` | Non-canonical experiments and research backlog |
| `docs/13_QUALITY/` | Definition of Done, test strategy, scorecards and health |

## Registry map

Registries are machine-readable operational truth.

- `registry/capabilities/`: stable capability IDs and dependencies.
- `registry/work-items/`: work execution state and handover data.
- `registry/dependencies/`: cross-component dependency declarations.
- `registry/progress/`: matrices for implementation/documentation/test state.
- future `registry/engines/`, `sources/`, `models/`, `datasets/`, `metrics/`, `lenses/`.

## Status vocabulary

Use only explicit states:

- `PROPOSED`
- `PLANNED`
- `READY`
- `IN_PROGRESS`
- `PARTIAL`
- `BLOCKED`
- `IN_REVIEW`
- `DONE`
- `DEPRECATED`
- `CANCELLED`

Never use vague labels such as "basically done".

## Agent handover invariant

At any time, `PROJECT_STATE.md` + the active work item + `read_before` references must be sufficient to resume the current task without rereading the repository.

If not, project state is considered broken and must be repaired before further implementation.
