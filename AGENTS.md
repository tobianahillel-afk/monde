# MONDE AI Agent Protocol

This file is **mandatory** for every AI agent, coding model or automated contributor working in MONDE.

The repository, not chat memory, is the source of truth.

## 1. Mandatory resume protocol

Before changing anything:

1. Read `README.md`.
2. Read `docs/00_START_HERE.md`.
3. Read `PROJECT_STATE.md`.
4. Identify the active `WORK-*` item in `registry/work-items/`.
5. Read that work item's `read_before`, `depends_on`, `reuses`, `affected_capabilities`, `affected_engines`, `affected_schemas` and `required_tests`.
6. Read every referenced canonical document before editing implementation.
7. Search the repository for an existing implementation, capability, engine, schema, helper or adapter before creating a new one.
8. Check `docs/11_ADR/` for relevant architectural decisions.
9. Check the capability and dependency registries.
10. Only then plan the change.

If no work item exists, create one before implementation.

## 2. Never reconstruct project state from assumption

An agent must not assume:

- that a missing feature has not already been started;
- that similarly named concepts are duplicates;
- that a chat description overrides canonical documentation;
- that a source value is current merely because it was recently ingested;
- that a test fixture proves production behavior;
- that a new abstraction is preferable to reuse.

When ambiguity exists, inspect repository state and record the ambiguity explicitly.

## 3. Work decomposition protocol

Before implementation, the agent must write a task plan into the work item.

For each requested change determine:

- number of tasks;
- dependency order;
- number of implementation runs/checkpoints;
- files expected to change;
- existing components to reuse;
- contracts that may be affected;
- test suites required;
- real-system validations required;
- rollback strategy.

A task must be small enough that its correctness can be reviewed independently.

Do not create artificial micro-tasks merely to increase task count.

## 4. Lot / sub-lot / work-item hierarchy

All development belongs to:

`PHASE → LOT → SUBLOT → WORK ITEM → TASK → RUN`

Definitions:

- **Phase**: major maturity stage.
- **Lot**: coherent deliverable with user-visible or architectural value.
- **Sublot**: independently reviewable portion of a lot.
- **Work item**: atomic tracked engineering objective.
- **Task**: ordered implementation step.
- **Run**: one bounded execution/session by an agent.

Every PR must reference at least one work item.

## 5. Reuse-first rule

Before implementing a new component, search for:

- existing engine;
- primitive;
- schema;
- parser;
- adapter;
- API client;
- storage abstraction;
- utility;
- model;
- workflow;
- capability.

If existing code can be extended safely, extend it.

If new code is required, document why reuse was insufficient.

Duplicating a concept under another name is a defect.

## 6. Dependency discipline

Every work item declares:

- `depends_on`: prerequisites;
- `blocks`: downstream work;
- `reuses`: components that must be reused;
- `read_before`: exact files needed to understand the area;
- `contracts`: schemas/interfaces that cannot be changed accidentally.

When a dependency changes, update every affected work item or registry entry in the same PR.

## 7. Mandatory epistemic invariants

Never violate:

- `Observation != Claim != Evidence != EstimatedState`.
- Observed, Estimated and Simulated worlds stay distinct.
- Original source timestamps are never overwritten by ingestion timestamps.
- Historical states are append-mostly/versioned.
- Inference always has confidence/uncertainty.
- Entity merges are reversible assertions.
- Derived state retains lineage to evidence and model/data versions.

Read `docs/09_GOVERNANCE/constitution.md` before touching world semantics.

## 8. Definition of Done

A work item is not done because code compiles.

It is done only when all applicable gates pass:

- functional correctness;
- unit tests;
- integration tests;
- contract/schema tests;
- end-to-end tests;
- regression tests;
- security checks;
- performance/resource checks;
- real-environment validation where the feature depends on a real external system;
- observability;
- documentation;
- registry/progress updates;
- review;
- reproducibility.

See `docs/13_QUALITY/definition-of-done.md`.

## 9. 100% coverage rule

MONDE targets **100% coverage of project-owned executable code** for line and branch coverage unless a documented, reviewed exception exists.

Coverage is not a substitute for good tests. Tests must include meaningful edge cases, failure modes and real integration behavior.

Generated code, third-party code and structurally untestable bootstrap glue may be excluded only through a documented exception.

A coverage percentage achieved with trivial assertions is considered failure.

## 10. Real-system validation rule

When behavior depends on an external system, tests must include the closest safe real environment available.

Examples:

- browser feature → actual browser E2E;
- API connector → contract test plus sandbox/test API when available;
- database feature → real supported database engine, not only mocks;
- object storage → real compatible service in integration tests;
- queue/stream → real broker in integration tests;
- file parser → representative real files;
- geospatial behavior → real geometries and CRS cases.

Mocks are allowed for fault injection and unit isolation, not as the sole proof of integration correctness.

Never use production credentials or destructive production operations in automated tests.

## 11. Review gates

Before a PR can be considered mergeable, perform:

1. self-review against the work item;
2. diff review for accidental duplication or scope creep;
3. architecture/ADR consistency review;
4. test review;
5. security review;
6. data/provenance review when applicable;
7. performance/resource review when applicable;
8. documentation and registry review.

Critical/high-risk changes require an explicit adversarial/red-team review step.

## 12. Scope-control rule

Do not overdevelop.

Implement only the acceptance criteria of the active work item plus the smallest reusable foundations required by it.

If a useful adjacent feature is discovered:

- do not silently implement it;
- create a new proposed work item;
- record dependency and rationale;
- continue the current scope.

## 13. Mandatory state updates

When work starts:

- set work item status to `IN_PROGRESS`;
- update `PROJECT_STATE.md` if it is active project work.

During work:

- append run notes/checkpoints;
- record discoveries, blockers and deviations.

When work ends:

- update acceptance-criteria status;
- record tests and evidence of validation;
- update dependency/progress matrices;
- update relevant docs/ADRs;
- set state accurately (`DONE`, `BLOCKED`, `PARTIAL`, etc.);
- update `PROJECT_STATE.md` with next action.

Never mark work complete when any mandatory gate is unknown.

## 14. Commit and PR rules

Use conventional, scoped commit messages where practical, for example:

- `docs: ...`
- `feat(identity): ...`
- `fix(temporal): ...`
- `test(evidence): ...`
- `refactor(storage): ...`
- `security(acquisition): ...`

A PR description must include:

- work-item IDs;
- scope;
- dependencies/reuse;
- acceptance criteria;
- tests executed;
- real-system validation;
- security impact;
- data/epistemic impact;
- docs/registry updates;
- known limitations;
- rollback notes.

## 15. Stop conditions

Stop implementation and mark the work item blocked if:

- a canonical contract is contradictory;
- required dependency is absent or invalid;
- implementation would silently break epistemic invariants;
- a security boundary cannot be preserved;
- required validation cannot be performed and shipping would create false confidence.

Record the exact blocker and proposed next action.

## 16. Handover quality

At the end of every bounded run, another competent agent must be able to continue without chat history by reading:

1. `PROJECT_STATE.md`;
2. the active work item;
3. its `read_before` files;
4. linked ADRs;
5. recent commits/PR discussion.

If that is not true, the run is incomplete.
