# START HERE — MONDE repository navigation

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

This file defines **how any human or AI resumes MONDE safely**.

## Fast resume — existing work

If you are continuing work already started, do **not** read the whole repository.

Read in this exact order:

1. `README.md`
2. `AGENTS.md`
3. `PROJECT_STATE.md`
4. active `registry/work-items/WORK-*.yaml`
5. every path listed under the work item's `read_before`
6. linked `REQ-*`, `ASM-*`, `RISK-*`, `CAP-*` and dependency records
7. referenced ADRs under `docs/11_ADR/`
8. exact tests/experiments/reviews linked to the work item
9. recent commits/PR discussion for that work item

Only expand beyond these files if the work item, traceability graph or dependency graph requires it.

## Registry orientation

Read `registry/README.md` when you need to determine which stable ID/registry owns information. Do not invent new registry namespaces ad hoc.

## New work — no existing work item

Before implementation **or substantial canonical documentation**:

1. Read `README.md` and `AGENTS.md`.
2. Read product material relevant to the request.
3. Search `registry/capabilities/`, `registry/requirements/` and work items for existing/overlapping semantics, including synonyms.
4. Search the repository for reusable implementation/specifications/contracts.
5. Read relevant architecture docs, dependencies and ADRs.
6. Identify what depends on the concept being changed.
7. Create a work item using `registry/work-items/_TEMPLATE.yaml`.
8. Declare requirements, assumptions, risks, dependencies, reuse, impact, acceptance criteria, review plan and validation.
9. If writing canonical specifications, follow `docs/13_QUALITY/specification-quality.md`.
10. If model/scientific behavior is involved, follow `docs/13_QUALITY/reproducibility-backtesting.md`.
11. Update `PROJECT_STATE.md` if the new work becomes active.
12. Begin work only after sufficient scope/context is explicit.

## Canonical documentation workflow

When the task is to define product/specification rather than code:

`DISCOVER EXISTING → RESEARCH IF NEEDED → REQUIREMENTS → ASSUMPTIONS/RISKS → DEPENDENCY IMPACT → SPECIFICATION → EXAMPLES/COUNTEREXAMPLES → TRACEABILITY → REVIEW COUNCIL → COLD READ → ACCEPT`

A document should not become `Accepted` because it is comprehensive-looking. It must be internally consistent, linked, testable and independently reviewable.

## Canonical document hierarchy

When documents conflict, use this precedence unless an ADR explicitly supersedes it:

1. `docs/09_GOVERNANCE/constitution.md`
2. Accepted ADRs
3. Canonical schemas/contracts
4. Accepted machine-readable registry records
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
| `docs/10_ROADMAP/` | Phases, lots, sublots and development/release process |
| `docs/11_ADR/` | Architecture Decision Records |
| `docs/12_RESEARCH/` | Non-canonical experiments and research backlog |
| `docs/13_QUALITY/` | DoD, testing, specification quality, review, backtesting, scorecards and health |

## Registry map

`registry/README.md` is the canonical registry index.

Current core registries include:

- `registry/work-items/` — execution/handover;
- `registry/capabilities/` — stable product capabilities;
- `registry/requirements/` — atomic normative requirements;
- `registry/assumptions/` — uncertain design/scientific premises;
- `registry/risks/` — risk propositions and controls;
- `registry/dependencies/` — dependency/reuse graph;
- `registry/traceability/` — end-to-end trace contract;
- `registry/reviews/` — structured review evidence;
- `registry/tests/` — important verification artifacts;
- `registry/experiments/` — reproducible experiments/backtests;
- `registry/progress/` — phase/lot/work quality state.

## Status vocabulary

Use only explicit states appropriate to each registry. Project/work progress currently uses:

- `NOT_STARTED`
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
- `NOT_APPLICABLE`

`NOT_APPLICABLE` always requires a reason in the owning work item or matrix context.

Never use vague labels such as "basically done".

## Agent handover invariant

At any time, `PROJECT_STATE.md` + active work item + its linked/read-before records must be sufficient to resume the current task without rereading the repository.

If not, project state is considered broken and must be repaired before further implementation.

## Cold-read invariant

For a newly Accepted canonical specification, a fresh agent must be able to determine:

- what is required;
- what is not required;
- what it depends on/reuses;
- what assumptions remain;
- what risks/failure modes exist;
- how correctness will be verified;
- what files/IDs must be read next.

If hidden conversation context is required, the specification is not complete.