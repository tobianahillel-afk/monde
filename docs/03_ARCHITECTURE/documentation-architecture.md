# MONDE Documentation Architecture

Status: Accepted  
Canonical: Yes

## Goal

MONDE documentation must let a new human or AI answer, without reading the entire repository:

1. What is MONDE?
2. What is the current project state?
3. What work is active?
4. What must I read before modifying it?
5. What already exists and must be reused?
6. What contracts/dependencies can I break?
7. What tests prove the behavior?
8. What architectural decisions explain the current design?
9. What remains unfinished?
10. How do I hand the work to the next agent?

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

Changes here are high impact and normally require ADR review.

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

Constitution, development/security rules, visibility/permissions, high-risk boundaries, auditability and data policies.

### Layer K — Roadmap/execution

`docs/10_ROADMAP/` plus `registry/work-items/` and `registry/progress/`.

Roadmap docs define planned phases/lots. Work items define actual executable engineering state.

### Layer L — Decisions

`docs/11_ADR/`

Explains durable decisions and why alternatives were rejected.

### Layer M — Research

`docs/12_RESEARCH/`

Draft hypotheses, experiments and references. Research documents are non-canonical until promoted through review/ADR/specification.

### Layer N — Quality

`docs/13_QUALITY/`

Definition of Done, testing strategy, MONDE Mini, benchmarks, scorecards and World Model health.

## Canonical document front matter

Every substantial canonical Markdown document should begin with:

```text
Status: Draft | Proposed | Accepted | Deprecated
Canonical: Yes | No
Owner: optional role/component
Last Updated: YYYY-MM-DD
Depends On: optional canonical references
Supersedes: optional references
Related Capabilities: CAP-...
Related ADRs: ADR-...
```

During bootstrap older docs may omit some fields, but the project should converge on this contract.

## What belongs in a work item vs documentation

### Work item

Use for:
- current implementation plan;
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
- contracts;
- invariants;
- reusable operational procedures.

Never leave an important durable architectural rule only inside a closed PR/work item.

## Read-before contract

Every work item contains exact `read_before` paths. The goal is minimum sufficient context, not maximum reading.

A good `read_before` list includes:

- semantic contract being modified;
- owning engine/module spec;
- relevant ADRs;
- interfaces reused;
- test strategy for the area.

A work item with `read_before: []` is acceptable only for truly isolated bootstrap/administrative changes.

## Dependency-driven navigation

The dependency registry is also a documentation router.

When work item A depends on component B, its dependency record should point to the canonical document/contract explaining B. An agent follows dependencies until it has enough context; it should not read unrelated documentation.

## Status freshness

`PROJECT_STATE.md` must remain intentionally concise. It points to active work items rather than duplicating their detail.

After any merge that changes active work:

- update phase/lot/sublot if needed;
- update active work IDs;
- update blockers;
- update next action;
- update required resume files if they changed.

A stale `PROJECT_STATE.md` is a release-blocking repository defect for AI-led development.

## Capability traceability

Each capability eventually maps:

`CAP-ID → docs → engines → schemas → work items → implementation → tests → status`

No capability is considered implemented because a UI button exists. The registry status must be supported by implementation/test evidence.

## Engine traceability

Each engine eventually maps:

`ENGINE-ID → responsibility → contracts → dependencies → capabilities → implementation → test suites → observability`

## Source/model traceability

Sources and models receive stable IDs so evidence can refer to exact source/model versions without relying on prose names.

## Documentation validation automation — target state

CI should eventually validate:

- all work-item IDs unique;
- all capability IDs unique/immutable;
- referenced IDs exist;
- `read_before` paths exist;
- status values are valid;
- DONE work items satisfy required completion flags;
- registry ↔ documentation references are non-broken;
- active project state points to existing work;
- orphan implementation areas are detected where feasible;
- docs links are valid;
- ADR numbering/status is valid.

## Historical preservation

Documentation changes are versioned in Git. Do not rewrite historical decisions to pretend they were always known.

When a decision changes:

- create/supersede an ADR;
- update current canonical documentation;
- let Git/ADR history preserve the previous state.

## Desired property

At any commit SHA, it should be possible to reconstruct:

- what MONDE was supposed to do;
- what was implemented;
- what was being worked on;
- why architecture looked that way;
- which tests/validation supported it;
- what the next agent was expected to do.
