# MONDE Documentation Architecture

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Goal

MONDE documentation must let a new human or AI answer, without reading the entire repository:

1. What is MONDE?
2. What is the current project state?
3. What work is active?
4. What must I read before modifying it?
5. What already exists and must be reused?
6. What requirements/assumptions/risks govern it?
7. What contracts/dependencies can I break?
8. What tests/experiments prove the behavior?
9. What architectural decisions explain the current design?
10. What remains unfinished?
11. How do I hand the work to the next agent?

## Canonical information layers

### Layer A — Orientation

- `README.md`: product/repository overview.
- `docs/00_START_HERE.md`: mandatory reading/navigation protocol.
- `AGENTS.md`: operating rules for AI contributors.
- `PROJECT_STATE.md`: current phase/lot/sublot/active work/next action.

These four files are the only mandatory global orientation set for every new run.

### Layer B — Product truth

`docs/01_PRODUCT/`

Defines why MONDE exists, user value, product boundaries, principles, glossary and product map.

Product docs describe **what/why**, not implementation details.

### Layer C — World semantics

`docs/02_WORLD_MODEL/`

Defines canonical primitives and semantics: Entity, Observation, Claim, Evidence, Source, Event, Relation, State, Belief, Forecast, Scenario, temporal/spatial support, uncertainty and ledger behavior.

Changes here are high impact and normally require ADR + epistemic review.

### Layer D — System architecture

`docs/03_ARCHITECTURE/`

Defines system boundaries, modules/processes, storage, compute, data flow, orchestration, serving, caches, observability and deployment.

Architecture docs describe durable structure. Temporary implementation notes belong in work items.

### Layer E — Data/acquisition

`docs/04_DATA/`

Defines data strategy, source discovery, source registry, provenance, retention, coverage, acquisition and modality-specific pipelines.

### Layer F — Intelligence engines

`docs/05_INTELLIGENCE_ENGINES/`

One canonical document per major engine. Each should state responsibility, inputs, outputs, invariants, dependencies, failure modes, APIs/contracts, observability and tests.

### Layer G — Capabilities

`docs/06_CAPABILITIES/` plus `registry/capabilities/`.

Human-readable documents explain capability families. Machine-readable registry entries are the canonical index of individual capabilities and stable CAP IDs.

### Layer H — Experiences

`docs/07_EXPERIENCES/`

Console, Globe, Entity 360s, Mission Workspace, Investigation, Live Event Room and other user experiences. Experience docs must reference capabilities/engines rather than redefine their semantics.

### Layer I — Models

`docs/08_MODELS/` plus future `registry/models/`.

Defines specialist model architecture, evaluation, tournament/promotion, active learning, distillation, drift, serving and reproducibility.

### Layer J — Governance

`docs/09_GOVERNANCE/`

Constitution, development/security rules, threat modeling, visibility/permissions, high-risk boundaries, auditability and data policies.

### Layer K — Roadmap/execution

`docs/10_ROADMAP/` plus `registry/work-items/` and `registry/progress/`.

Roadmap docs define planned phases/lots. Work items define actual executable engineering state.

### Layer L — Decisions

`docs/11_ADR/`

Explains durable decisions and why alternatives were rejected.

### Layer M — Research

`docs/12_RESEARCH/`

Research questions, evidence gathering, experiments and non-canonical findings. Follow `research-protocol.md`; findings become canonical only after promotion into requirements/specifications/ADRs/registries.

### Layer N — Quality and assurance

`docs/13_QUALITY/`

Contains:
- Definition of Ready;
- Definition of Done;
- testing strategy;
- specification-quality protocol;
- Review Council;
- assurance levels;
- advanced verification;
- non-functional requirements;
- reproducibility/backtesting;
- MONDE Mini/golden-world strategy;
- benchmarks/scorecards/World Model health.

## Machine-readable project memory

`registry/README.md` is the canonical index.

Core project-memory registries include:
- `WORK-*` work items;
- `CAP-*` capabilities;
- `REQ-*` requirements;
- `ASM-*` assumptions;
- `RISK-*` risks;
- `REVIEW-*` review evidence;
- `TEST-*` verification artifacts;
- `EXP-*` reproducible experiments/backtests;
- typed dependencies and progress state.

Future runtime/product registries include engines, sources, datasets, models, metrics, SLOs and lenses.

## Canonical document front matter

Every substantial canonical Markdown document should begin with:

```text
Status: Draft | Proposed | Accepted | Deprecated
Canonical: Yes | No
Owner: optional role/component
Last Updated: YYYY-MM-DD
Depends On: optional canonical references
Supersedes: optional references
Related Requirements: REQ-...
Related Capabilities: CAP-...
Related ADRs: ADR-...
```

During bootstrap older docs may omit some fields, but the project should converge on this contract.

## Specification lifecycle

Canonical documentation is an engineered artifact and follows:

`DISCOVER → REQUIREMENTS → IMPACT → ASSUMPTIONS/RISKS → SPECIFY → EXAMPLES/COUNTEREXAMPLES → TRACE → REVIEW → COLD-READ → ACCEPT`

See `docs/13_QUALITY/specification-quality.md`.

## What belongs in a work item vs documentation vs registry

### Work item

Use for:
- current implementation/specification plan;
- task/run decomposition;
- branch-specific discoveries;
- validation evidence;
- blockers;
- short-lived migration notes;
- handover.

### Canonical documentation

Use for:
- durable product behavior;
- stable architecture;
- detailed semantics;
- contracts/invariants;
- examples/counterexamples;
- reusable operational procedures.

### Registry

Use for:
- stable identity;
- lifecycle/status;
- machine-readable dependencies/links;
- compact verification/traceability metadata.

Never leave an important durable architectural rule only inside a closed PR/work item, and never duplicate a full specification into registry YAML.

## Read-before contract

Every work item contains exact `read_before` paths. The goal is minimum sufficient context, not maximum reading.

A good `read_before` list includes:

- semantic contract being modified;
- owning engine/module spec;
- relevant ADRs;
- interfaces reused;
- linked requirements/assumptions/risks;
- test/assurance guidance for the area.

## Dependency-driven navigation

The dependency/traceability graph is also a documentation router.

When work item A depends on component B, its records should point to the canonical document/contract explaining B. An agent follows dependencies until it has enough context; it should not read unrelated documentation.

Before changing a stable concept the agent asks `WHAT DEPENDS ON THIS?` and follows downstream references.

## Status freshness

`PROJECT_STATE.md` must remain intentionally concise. It points to active work items rather than duplicating their detail.

After any merge that changes active work:

- update phase/lot/sublot if needed;
- update active work IDs;
- update blockers;
- update next action;
- update required resume files if they changed.

A stale `PROJECT_STATE.md` is a release-blocking repository defect for AI-led development.

## End-to-end traceability

Target chain:

`PRODUCT GOAL → REQ-ID → CAP-ID → ADR/DESIGN → ENGINE/SCHEMA → WORK-ID → IMPLEMENTATION → TEST/EXP → REVIEW/VALIDATION → OBSERVABILITY`

Assumptions/risks attach wherever they matter.

No capability is considered implemented because a UI button exists. The registry status must be supported by implementation/test evidence.

## Documentation validation automation — target state

CI should eventually validate:

- unique immutable IDs;
- registry schemas/status transitions;
- referenced IDs exist;
- `read_before` paths exist;
- DONE work items satisfy required completion/review/traceability flags;
- Accepted specs satisfy required metadata/gates where machine-checkable;
- orphan accepted requirements/DONE capabilities are detected;
- registry ↔ documentation references are non-broken;
- active project state points to existing work;
- docs links/front matter are valid;
- ADR numbering/status is valid;
- expired assumptions/risks are surfaced;
- architecture fitness functions pass.

## Historical preservation

Documentation changes are versioned in Git. Do not rewrite historical decisions to pretend they were always known.

When a decision changes:

- create/supersede an ADR;
- update current canonical documentation;
- retain requirement/capability mapping history;
- let Git/ADR/registry history preserve the previous state.

## Desired property

At any commit SHA, it should be possible to reconstruct:

- what MONDE was supposed to do;
- which requirements/assumptions/risks existed;
- what was implemented;
- what was being worked on;
- why architecture looked that way;
- which tests/experiments/reviews supported it;
- which external research informed material decisions;
- what the next agent was expected to do.
