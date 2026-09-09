# MONDE AI Agent Protocol

This file is **mandatory** for every AI agent, coding model or automated contributor working in MONDE.

The repository, not chat memory, is the source of truth.

## 1. Mandatory resume protocol

Before changing anything:

1. Read `README.md`.
2. Read `docs/00_START_HERE.md`.
3. Read `PROJECT_STATE.md`.
4. Identify the active `WORK-*` item in `registry/work-items/`.
5. Read that work item's `read_before`, `depends_on`, `reuses`, `affected_capabilities`, `affected_engines`, `affected_schemas`, requirements/assumptions/risks and `required_tests`.
6. Read every referenced canonical document before editing specification or implementation.
7. Search the repository for an existing implementation, capability, requirement, engine, schema, helper, adapter or synonym before creating a new one.
8. Check `docs/11_ADR/` for relevant architectural decisions.
9. Check capability, dependency, requirement, assumption, risk and traceability registries.
10. Only then plan the change.

If no work item exists, create one before implementation.

## 2. Never reconstruct project state from assumption

An agent must not assume:

- that a missing feature has not already been started;
- that similarly named concepts are duplicates;
- that a chat description overrides canonical documentation;
- that a source value is current merely because it was recently ingested;
- that a test fixture proves production behavior;
- that a new abstraction is preferable to reuse;
- that a detailed specification is internally complete;
- that an unstated assumption is safe;
- that another document has no dependency merely because it was not in the initial context window.

When ambiguity exists, inspect repository state and record the ambiguity explicitly.

## 3. Work decomposition protocol

Before implementation, the agent must write a task plan into the work item.

For each requested change determine:

- number of tasks;
- dependency order;
- number of implementation runs/checkpoints;
- files expected to change;
- existing components to reuse;
- requirements being satisfied;
- assumptions being relied upon;
- risks introduced/changed;
- contracts that may be affected;
- test suites required;
- review hats required;
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
- capability;
- requirement or invariant already defining equivalent behavior.

Search synonyms and related domains, not only the exact requested phrase.

If existing code/specification can be extended safely, extend it.

If new code is required, document why reuse was insufficient.

Duplicating a concept under another name is a defect.

## 6. Dependency discipline

Every work item declares:

- `depends_on`: prerequisites;
- `blocks`: downstream work;
- `reuses`: components that must be reused;
- `read_before`: exact files needed to understand the area;
- `contracts`: schemas/interfaces that cannot be changed accidentally;
- `requirements`: behavioral obligations;
- `assumptions`: material uncertain premises;
- `risks`: tracked failure possibilities.

When a dependency changes, update every affected work item or registry entry in the same PR.

Before changing a stable concept, explicitly ask **WHAT DEPENDS ON THIS?** and inspect the traceability/dependency graph.

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

A work item is not done because code compiles or documentation is long.

It is done only when all applicable gates pass:

- functional correctness;
- specification quality;
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
- registry/progress/traceability updates;
- required review hats;
- reproducibility/backtesting where applicable.

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
4. specification/requirements/traceability review;
5. test/verification review;
6. security review where applicable;
7. data/provenance/epistemic review where applicable;
8. performance/SRE review where applicable;
9. documentation/handover review;
10. adversarial/skeptic review for foundational, critical or high-risk changes.

Use `docs/13_QUALITY/review-council.md` to determine required hats and independence level.

Critical/high-risk changes should not rely on author self-review as the sole approval.

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
- record discoveries, blockers and deviations;
- add newly discovered assumptions/risks/dependencies rather than leaving them only in reasoning;
- update requirement/traceability mappings when scope changes legitimately.

When work ends:

- update acceptance-criteria status;
- record tests and evidence of validation;
- update dependency/progress/traceability matrices;
- update relevant docs/ADRs/requirements/assumptions/risks;
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
- requirements/capabilities;
- dependencies/reuse;
- assumptions/risks;
- acceptance criteria;
- tests executed;
- backtests/reproducibility evidence where applicable;
- real-system validation;
- security impact;
- data/epistemic impact;
- docs/registry/traceability updates;
- required review hats/outcomes;
- known limitations;
- rollback notes.

## 15. Stop conditions

Stop implementation and mark the work item blocked if:

- a canonical contract is contradictory;
- required dependency is absent or invalid;
- an important assumption is both unvalidated and capable of invalidating the design;
- implementation would silently break epistemic invariants;
- a security boundary cannot be preserved;
- required validation cannot be performed and shipping would create false confidence;
- critical traceability is broken such that impact cannot be understood.

Record the exact blocker and proposed next action.

## 16. Handover quality

At the end of every bounded run, another competent agent must be able to continue without chat history by reading:

1. `PROJECT_STATE.md`;
2. the active work item;
3. its `read_before` files;
4. linked requirements/assumptions/risks;
5. linked ADRs;
6. recent commits/PR discussion.

If that is not true, the run is incomplete.

## 17. Documentation/specification is first-class engineering

When the task is to write or change canonical documentation, do **not** treat it as exempt from engineering discipline.

Follow `docs/13_QUALITY/specification-quality.md`:

1. discover existing concepts and synonyms;
2. identify related requirements/capabilities/dependencies;
3. inspect upstream/downstream documents;
4. external research when required by the specification and permitted by the task;
5. record assumptions and unresolved uncertainty;
6. write atomic/testable requirements;
7. include examples, counterexamples and failure modes;
8. check security/performance/operations/data semantics where relevant;
9. run cross-document contradiction and duplication review;
10. update traceability;
11. perform required Review Council hats;
12. perform a cold-read test before `Accepted`.

A canonical document is defective if implementation cannot determine what behavior to build/test from it.

## 18. Scientific validation and backtesting

Forecasts, detectors, entity resolution, causal models, source scoring, research planners and learned/model-based behavior must follow `docs/13_QUALITY/reproducibility-backtesting.md`.

Never evaluate historical performance using information unavailable at the historical cutoff.

Require appropriate:

- baseline;
- leakage-safe splits/cutoffs;
- calibration/uncertainty metrics;
- subgroup/regime evaluation;
- reproducibility manifest;
- resource benchmark;
- failure analysis;
- shadow/canary validation before critical promotion.

Negative results that prevent repeated dead ends should be recorded.

## 19. AI anti-omission protocol

Before finalizing a plan/specification/PR, explicitly ask:

- What important category did I not inspect?
- What adjacent concept could already own this responsibility?
- Which upstream/downstream dependency could be affected?
- Which failure mode makes the happy-path design misleading?
- Which assumption am I treating as fact?
- Which timestamp/provenance/permission semantics could be lost?
- What would a security reviewer object to?
- What would an SRE/performance reviewer object to?
- What would an epistemic reviewer object to?
- What would falsify the claimed improvement?
- Can a simpler design satisfy the same requirements?
- Can another agent resume this without hidden context?

Record material discoveries rather than leaving them only in transient reasoning.
