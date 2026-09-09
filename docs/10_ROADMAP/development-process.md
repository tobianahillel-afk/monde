# MONDE Development Process

Status: Accepted  
Canonical: Yes

## 1. Hierarchy

All work is organized as:

`PHASE → LOT → SUBLOT → WORK ITEM → TASK → RUN → PR → REVIEW → MERGE`

No implementation bypasses this chain unless explicitly classified as emergency maintenance and documented afterward.

## 2. Phase

A phase defines a maturity objective for MONDE. It is not merely a calendar period.

Each phase has:

- goals;
- entry criteria;
- exit criteria;
- lots;
- architectural constraints;
- quality thresholds;
- explicit non-goals.

## 3. Lot

A lot is a coherent deliverable with measurable value and bounded architecture scope.

Every lot must define:

- purpose;
- capabilities delivered;
- dependencies;
- data contracts;
- user/system outcome;
- acceptance tests;
- exit criteria.

## 4. Sublot

A sublot is the smallest coherent slice that can be implemented and reviewed without requiring the entire lot to exist.

Sublots should minimize cross-branch coupling and allow independent validation.

## 5. Work item

A work item is the canonical engineering execution unit.

It must use `registry/work-items/_TEMPLATE.yaml` and declare:

- scope in/out;
- acceptance criteria;
- `read_before` files;
- dependencies;
- components to reuse;
- affected capabilities/engines/schemas/docs;
- contracts;
- implementation tasks;
- planned agent runs;
- required test suites;
- real-system validation;
- risk;
- rollback;
- run log and handover state.

## 6. Task decomposition by AI agents

Before editing implementation, the active agent must decide how many tasks and runs are needed.

The decomposition should optimize for:

- independent reviewability;
- limited blast radius;
- clear dependency order;
- ability to validate after each meaningful step;
- minimal repeated context loading;
- no hidden architectural work.

A planned run should end at a coherent checkpoint, not in the middle of an unexplained refactor.

## 7. Run protocol

Each agent run has:

- objective;
- tasks attempted;
- repository baseline/branch;
- files read;
- files changed;
- tests/validation executed;
- discoveries;
- deviations;
- blockers;
- next action.

Append concise run notes to the work item. Do not rely on conversation history as the handover log.

## 8. Branching

Default workflow:

1. start from current `main`;
2. create a scoped branch;
3. update/create work item;
4. implement;
5. validate;
6. update docs/registries/state;
7. open PR;
8. run automated checks;
9. perform structured review;
10. merge only when applicable gates pass.

Suggested branch names:

- `feat/<work-id>-<slug>`
- `fix/<work-id>-<slug>`
- `docs/<work-id>-<slug>`
- `refactor/<work-id>-<slug>`
- `security/<work-id>-<slug>`

Bootstrap/migration branches may use a descriptive prefix.

## 9. Required review sequence

Every non-trivial PR is reviewed in this order:

### Gate A — Scope and reuse

- Acceptance criteria are satisfied and nothing unrelated was silently added.
- Existing components were searched and reused where appropriate.
- No duplicate engine/schema/helper/capability was introduced.

### Gate B — Architecture and contracts

- Dependencies are declared.
- ADRs are respected.
- Public/internal contracts changed intentionally.
- Backward compatibility/migration is handled.

### Gate C — Data and epistemic correctness

Applicable when touching world/data semantics:

- observed/estimated/simulated distinction preserved;
- temporal semantics preserved;
- provenance/lineage preserved;
- missing values and uncertainty handled;
- entity resolution remains reversible where uncertain.

### Gate D — Testing

- required suites executed;
- 100% project-owned line/branch coverage target satisfied or exception documented;
- regression cases included;
- failures/edge cases tested;
- tests are meaningful rather than percentage-only.

### Gate E — Real-system validation

If the feature integrates a browser/API/database/broker/object store/model/runtime/external service, validate against the closest safe real environment available.

Mocks alone are insufficient proof of integration correctness.

### Gate F — Security

- trust boundaries reviewed;
- secrets handled correctly;
- untrusted input isolated/validated;
- authn/authz and tenant scope tested where applicable;
- dependency/security tooling passes;
- high-risk behavior receives adversarial review.

### Gate G — Performance and reliability

When applicable:

- latency/throughput/resource budget validated;
- retries/idempotency/timeouts/backpressure tested;
- failure/recovery behavior tested;
- no unbounded memory/world loading.

### Gate H — Documentation and handover

- canonical docs updated;
- capability/work/progress/dependency registries updated;
- ADR created/updated when a decision changed;
- `PROJECT_STATE.md` updated if this is active work;
- next agent can resume without chat history.

## 10. Merge rule

A PR may be merged only when:

- acceptance criteria are met;
- applicable gates are green;
- unresolved blockers are absent;
- state/registries/docs accurately describe what now exists.

Do not merge merely because CI is green.

## 11. Post-merge

After merge:

- work item becomes `DONE` only if Definition of Done is actually satisfied;
- downstream blocked work may become `READY`;
- progress matrix is updated;
- next work item becomes active explicitly;
- obsolete branches are removed according to repository policy.

## 12. Bug workflow

A bug fix must:

1. create/reference a work item or tracked issue;
2. reproduce the bug where feasible;
3. add a failing regression test first or explain why impossible;
4. fix the smallest responsible layer;
5. validate adjacent contracts;
6. add real-system reproduction for integration defects when practical;
7. update docs if observed behavior/contract changes.

## 13. Architecture-change workflow

Before implementing a durable architecture change:

1. inspect existing ADRs;
2. create a new ADR if the choice is significant or irreversible/costly;
3. record considered alternatives;
4. identify migration and rollback;
5. link affected work items/capabilities;
6. implement only after decision status permits it.

## 14. Scope escalation

When an implementation reveals adjacent required work:

- if strictly necessary for current acceptance criteria, add it to the plan and explain why;
- if useful but not required, create a follow-up work item;
- never silently turn one sublot into a whole new subsystem.

## 15. Release/lot exit review

At the end of every sublot and lot, perform a structured retrospective:

- capabilities promised vs delivered;
- open defects;
- coverage and test health;
- security findings;
- performance/resource results;
- documentation freshness;
- dependency debt;
- architecture deviations;
- operational readiness;
- lessons and follow-up work.

A lot is not complete until this review is recorded.
