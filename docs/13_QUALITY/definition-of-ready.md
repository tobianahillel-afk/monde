# MONDE Definition of Ready

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

The Definition of Ready prevents humans or AI agents from starting implementation/specification work with insufficient context and then inventing missing architecture during execution.

A work item should not move to `IN_PROGRESS` until every applicable Ready criterion is satisfied or a deliberate discovery/spike exception is recorded.

## Ready — objective and scope

- Problem/outcome is explicit.
- Scope `in` and `out` are explicit.
- Acceptance criteria are observable/testable.
- The work fits a defined phase/lot/sublot.
- Adjacent desirable work is not silently bundled.

## Ready — existing-state discovery

- Existing CAP/REQ/WORK records were searched, including synonyms.
- Existing code/components/contracts were searched.
- Relevant ADRs were inspected.
- Reuse candidates are listed.
- Duplicate responsibility risk has been considered.

## Ready — requirements and semantics

- Applicable `REQ-*` requirements exist or will be created as part of the specification task.
- Important terms have canonical definitions or are explicitly introduced.
- Inputs/outputs/state transitions are sufficiently known for the planned stage.
- Applicable temporal/provenance/identity/uncertainty/permission semantics are known or explicitly marked as unresolved discovery questions.

## Ready — dependencies and impact

- `depends_on`, `reuses` and stable contracts are identified.
- Upstream/downstream blast radius is assessed.
- Required migrations/reprocessing/compatibility work is identified.
- Blocking dependencies are `DONE`/usable or the work is explicitly a discovery task around them.

## Ready — assumptions and risks

- Material uncertain premises are recorded as `ASM-*`.
- Material risks are recorded as `RISK-*` or in the work item when not yet deserving standalone IDs.
- High-impact assumptions have a validation plan.
- Security/privacy/high-risk classification is known enough to select review gates.

## Ready — validation plan

Before building, the work item identifies which validation is expected:

- unit/property tests;
- contract/schema tests;
- integration/E2E;
- real-system validation;
- security/adversarial tests;
- performance/load/reliability tests;
- epistemic/data-quality checks;
- backtest/experiment/reproducibility when applicable.

The exact tests may evolve, but the work must not begin with "we will figure out how to prove it later" for critical behavior.

## Ready — review plan

- Artifact/change class is known.
- Review Council hats are selected.
- Required independence level is selected.
- Critical/high-risk changes have an explicit adversarial review plan.

## Ready — non-functional expectations

Where material, initial expectations exist for:

- latency;
- throughput;
- freshness;
- accuracy/calibration;
- availability/reliability;
- durability/recovery;
- memory/storage/compute;
- cost;
- observability.

Unknown budgets may be discovery outputs, but they must be named rather than ignored.

## Ready — agent context

- `read_before` contains the minimum sufficient canonical context.
- A fresh agent can understand the objective/dependencies without chat history.
- The task/run decomposition is bounded enough to hand over safely.

## Discovery/spike exception

A research spike may begin without complete requirements when its purpose is explicitly to resolve unknowns.

The spike must define:
- questions to answer;
- time/resource budget;
- expected artifacts/evidence;
- what it is **not** allowed to silently ship;
- decision/next-work outputs.

A spike cannot become production implementation by inertia; a follow-up Ready work item is required.

## Ready decision

Use:

- `READY` — applicable criteria satisfied;
- `BLOCKED` — prerequisite/critical unknown prevents safe work;
- `PLANNED` — accepted but not sufficiently prepared;
- `IN_PROGRESS` — only after Ready or explicit bounded discovery exception.

## Final rule

**Do not compensate for missing context by letting the implementing AI invent product semantics.** Repair readiness first.