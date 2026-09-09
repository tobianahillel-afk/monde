# MONDE Assurance Levels

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

MONDE should be rigorous without making every typo fix require the same process as a World Model semantic change. Assurance levels scale evidence, review independence and testing effort with blast radius and risk.

Assurance level is **minimum required rigor**, not permission to skip applicable hard gates.

## A0 — Research / Draft

Use for:
- exploratory notes;
- bounded spikes;
- non-canonical research;
- prototypes that cannot affect canonical/production state.

Minimum:
- explicit objective/questions;
- time/resource budget;
- no silent production promotion;
- findings/assumptions recorded;
- handover if work continues.

## A1 — Local / Low Risk

Use for:
- small documentation clarification;
- local refactor with no contract change;
- low-risk tooling.

Minimum:
- work item or appropriately tracked change;
- self-review + relevant reviewer where non-trivial;
- affected tests/docs;
- no unresolved hard gate.

## A2 — Standard Product/Engineering

Default for material feature/component work.

Requires:
- Definition of Ready;
- requirements/acceptance criteria;
- dependency/reuse/impact analysis;
- assumptions/risks as needed;
- appropriate unit/integration/contract/E2E tests;
- real-system validation where applicable;
- Review Council L1/L2 depending scope;
- docs/traceability/observability;
- Definition of Done.

## A3 — Critical

Use when failure can materially corrupt world truth, availability, permissions, major performance, financial/scientific conclusions or foundational architecture.

Examples:
- Entity Resolution core;
- World Ledger semantics;
- identity/permission engine;
- major storage/distributed architecture;
- promoted forecasting/detection models;
- source provenance pipeline;
- production browser/acquisition boundary.

Requires A2 plus:
- context-separated review (`L2`) minimum;
- explicit threat/risk model;
- adversarial/failure-injection cases;
- reproducibility/backtesting where scientific/model behavior exists;
- performance/resource benchmark;
- rollback/replay validation;
- operational/observability review;
- no unresolved R1/R2 findings unless formally accepted at appropriate authority.

## A4 — Constitutional / High-Risk / Systemic

Use for:
- changing MONDE constitutional invariants;
- cross-world epistemic semantics;
- major authorization/visibility model changes;
- high-risk capability foundations;
- irreversible migrations affecting canonical history;
- changes capable of systemic corruption across many engines/capabilities.

Requires A3 plus:
- dedicated ADR;
- multi-reviewer/adversarial `L3` target;
- explicit alternatives and reversibility analysis;
- migration/reprocessing plan;
- formal owner approval where required;
- staged/shadow/canary rollout where runtime behavior is involved;
- independent validation of critical tests/evidence;
- post-deployment/merge review plan.

## Automatic escalation signals

Raise assurance level when any applies:
- blast radius becomes `WORLD_SEMANTIC` or `CONSTITUTIONAL`;
- authentication/authorization/tenant scope changes;
- high-risk/sensitive data/capability involved;
- data loss/history corruption possible;
- critical source of truth changes;
- model output directly affects major decisions/alerts;
- irreversible migration;
- large cost/performance impact;
- novel external execution/acquisition boundary;
- insufficiently validated assumptions underpin the design.

## De-escalation

Do not lower assurance solely to reduce process burden. De-escalation requires evidence that blast radius/risk is genuinely smaller, usually by narrowing scope or isolating the change behind a stable boundary.

## Work-item field

Each material work item should declare:

```yaml
assurance:
  level: A2
  rationale: ""
  escalation_triggers: []
```

## Independent test/reviewer principle

For A3/A4, the authoring agent should not be the only source of:
- expected behavior;
- test cases;
- review approval;
- interpretation of benchmark/backtest results.

Use a fresh reviewer/context or human review where practical to reduce correlated reasoning errors.

## Non-compensable gates

At every assurance level, applicable hard gates in `project-scorecard.md` remain blocking. High numeric quality elsewhere cannot compensate for a critical security, provenance, temporal leakage, authorization or epistemic defect.
