# PHASE-0 — Specification & Repository Governance

Status: Proposed  
Canonical roadmap: Yes

## Purpose

PHASE-0 exists so MONDE does not begin implementation before its product semantics, development operating system, capability inventory and architecture contracts are explicit enough for AI-led development.

## Phase exit criteria

PHASE-0 is complete only when:

- repository governance is operational and resumable;
- governance consistency checks are automated in CI;
- all previously validated capabilities are inventoried and assigned stable CAP IDs;
- core product vision/scope/glossary/product map are canonical;
- core World Model semantics are canonical;
- data/acquisition strategy is canonical;
- engine/lens/experience boundaries are documented;
- initial technical architecture and key ADRs are accepted;
- initial schemas/contracts are defined sufficiently for implementation;
- Phase-1 backlog has explicit dependencies/acceptance criteria;
- no critical unresolved contradiction exists across canonical docs/registries.

## LOT-0 — AI-first repository operating system

### SUBLOT-0.1 — Governance bootstrap

Work: `WORK-0001`

Deliver:
- README/orientation;
- START_HERE;
- AGENTS protocol;
- PROJECT_STATE;
- Constitution;
- work/progress/dependency/capability registry contracts;
- development lifecycle;
- DoD/testing/security/ADR rules;
- PR/issue templates;
- quality scorecard.

Status: `IN_REVIEW`

### SUBLOT-0.2 — Governance automation

Planned deliverables:
- repository governance validator;
- schema validation for machine-readable registry files;
- referential-integrity checks for IDs and `read_before` paths;
- status vocabulary validation;
- project-state ↔ active-work consistency check;
- documentation-link validation;
- PR checks that required work-item references exist;
- baseline security/secret/dependency scanning where supported;
- coverage gate scaffolding for future executable code.

Status: `PLANNED`

### SUBLOT-0.3 — Repository settings & merge discipline

Planned deliverables / owner configuration:
- repository visibility decision;
- main-branch protections/rulesets;
- required PR/status checks;
- merge strategy;
- review requirements;
- protections against force-push/deletion where supported.

Status: `PLANNED`

## LOT-1 — Canonical product inventory

### SUBLOT-1.1 — Historical capability inventory

Collect every previously validated MONDE capability, including older and newer generations, without silently deleting scope.

Process:
1. collect;
2. normalize names/synonyms;
3. identify true duplicates vs distinct semantics;
4. preserve all validated functionality;
5. assign immutable CAP IDs;
6. group by capability family/lens/engine/experience;
7. record dependencies and risk class;
8. mark documentation/implementation state.

Status: `PLANNED`

### SUBLOT-1.2 — Product vision, scope and principles

Canonicalize:
- vision;
- mission;
- product principles;
- scope/non-scope;
- glossary;
- product map;
- user/persona/use-case families.

Status: `PLANNED`

## LOT-2 — World Model specification

Planned sublots:
- primitives/ontology;
- epistemic model;
- temporal model;
- spatial model;
- identity and relation model;
- evidence/provenance model;
- BeliefState/uncertainty/reconciliation;
- World Ledger/world-generation semantics.

Status: `PLANNED`

## LOT-3 — Data & acquisition specification

Planned sublots:
- data ownership/retention/storage classes;
- Source Registry/Data Coverage Matrix/Sensor & Proxy Registry;
- Web/browser/channel acquisition;
- document/image/video/audio pipelines;
- realtime/streaming/traffic/Earth-observation;
- source discovery/change detection/monitoring;
- provenance, archival and information ancestry.

Status: `PLANNED`

## LOT-4 — Intelligence architecture

Planned sublots:
- engine registry and boundaries;
- identity/evidence/temporal/geo/reconciliation;
- causal/forecast/scenario/anomaly;
- opportunity/decision;
- Research Planner and World Scientist;
- model-science architecture.

Status: `PLANNED`

## LOT-5 — Experiences

Planned sublots:
- Console;
- Globe;
- shared `MondeContext`;
- Entity/Company/Person/Place/Building 360;
- Investigation/Mission/Decision/Live Event Room;
- evidence/timeline/replay/exploration workflows.

Status: `PLANNED`

## LOT-6 — Initial technical architecture & implementation readiness

Planned sublots:
- initial process/module topology;
- canonical stores and projections;
- schema/versioning/ID strategy;
- event/orchestration semantics;
- observability and deployment;
- model-serving strategy;
- MONDE Mini design;
- initial ADR acceptance;
- Phase-1 executable backlog.

Status: `PLANNED`

## Phase discipline

No lot is considered complete because its prose exists. Exit requires cross-document consistency, registry updates and review against the Phase-0 criteria.

Substantial product implementation should begin only after the specific contracts it depends on are accepted, even if other Phase-0 documentation continues in parallel.
