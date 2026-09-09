# MONDE Development Process

Status: Accepted  
Canonical: Yes

## 1. Hierarchy

All work is organized as:

`PHASE → LOT → SUBLOT → WORK ITEM → TASK → RUN → PR → REVIEW → MERGE`

No implementation bypasses this chain unless explicitly classified as emergency maintenance and documented afterward.

Specifications, documentation, models and infrastructure changes use the same hierarchy; "docs-only" does not mean "governance-free".

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

A work item is the canonical engineering/specification execution unit.

It must use `registry/work-items/_TEMPLATE.yaml` and declare:

- scope in/out;
- acceptance criteria;
- linked requirements;
- assumptions and risks;
- `read_before` files;
- dependencies;
- components to reuse;
- affected capabilities/engines/schemas/docs;
- contracts;
- impact/blast radius;
- implementation/specification tasks;
- planned agent runs;
- required review hats and independence level;
- required test suites;
- scientific/backtest validation where applicable;
- observability expectations where applicable;
- real-system validation;
- rollback;
- run log and handover state.

## 6. Specification before implementation

Substantial behavior must be specified before implementation reaches production status.

Canonical specification work follows `docs/13_QUALITY/specification-quality.md` and should:

1. discover existing concepts/synonyms;
2. inventory dependencies and reuse;
3. define atomic `REQ-*` requirements;
4. external-research factual/domain questions where needed and permitted;
5. record material `ASM-*` assumptions;
6. record `RISK-*` risks;
7. analyze upstream/downstream blast radius;
8. describe inputs/outputs/state/failure modes;
9. define temporal/provenance/permission/performance semantics where relevant;
10. include examples and counterexamples;
11. map verification strategy;
12. perform cross-document contradiction/duplicate review;
13. pass required Review Council hats;
14. pass a cold-read test before `Accepted`.

Implementation should not invent missing product semantics ad hoc. If specification is insufficient, repair or explicitly amend the spec/work item first.

## 7. Task decomposition by AI agents

Before editing implementation or a substantial specification, the active agent must decide how many tasks and runs are needed.

The decomposition should optimize for:

- independent reviewability;
- limited blast radius;
- clear dependency order;
- ability to validate after each meaningful step;
- minimal repeated context loading;
- no hidden architectural work;
- no mixing of unrelated specification and implementation scope.

A planned run should end at a coherent checkpoint, not in the middle of an unexplained refactor.

## 8. Run protocol

Each agent run has:

- objective;
- tasks attempted;
- repository baseline/branch;
- files read;
- files changed;
- requirements/assumptions/risks discovered or changed;
- tests/validation executed;
- review findings addressed;
- discoveries;
- deviations;
- blockers;
- next action.

Append concise run notes to the work item. Do not rely on conversation history as the handover log.

## 9. Branching

Default workflow:

1. start from current `main`;
2. create a scoped branch;
3. update/create work item;
4. perform discovery/specification gates appropriate to the task;
5. implement/write the artifact;
6. validate;
7. update docs/registries/traceability/state;
8. open PR;
9. run automated checks;
10. perform structured Review Council review;
11. resolve findings and re-run affected validation;
12. merge only when applicable gates pass.

Suggested branch names:

- `feat/<work-id>-<slug>`
- `fix/<work-id>-<slug>`
- `docs/<work-id>-<slug>`
- `refactor/<work-id>-<slug>`
- `security/<work-id>-<slug>`

Bootstrap/migration branches may use a descriptive prefix.

## 10. Required review sequence

Every non-trivial PR is reviewed in this order.

### Gate A — Scope, requirements and reuse

- Acceptance criteria/requirements are satisfied and nothing unrelated was silently added.
- Existing components/capabilities/requirements were searched and reused where appropriate.
- No duplicate engine/schema/helper/capability/concept was introduced.
- Assumptions and risks are explicit rather than hidden.

### Gate B — Architecture, impact and contracts

- Dependencies are declared.
- Upstream/downstream impact has been inspected.
- ADRs are respected.
- Public/internal contracts changed intentionally.
- Backward compatibility/migration/reprocessing is handled.

### Gate C — Data and epistemic correctness

Applicable when touching world/data semantics:

- observed/estimated/simulated distinction preserved;
- temporal semantics preserved;
- provenance/lineage preserved;
- missing values and uncertainty handled;
- source independence/revision semantics preserved;
- entity resolution remains reversible where uncertain.

### Gate D — Specification/testability

- canonical behavior is sufficiently specified;
- examples and counterexamples disambiguate semantics;
- requirements map to verification;
- conflicting related docs have been reviewed;
- a fresh agent can understand what to build/test without hidden chat context.

### Gate E — Testing

- required suites executed;
- 100% project-owned line/branch coverage target satisfied or exception documented;
- regression cases included;
- failures/edge cases tested;
- tests are meaningful rather than percentage-only;
- important tests identify which requirements/contracts/risks they protect.

### Gate F — Scientific validation / backtesting

Applicable to forecasts, detectors, entity resolution, source scoring, causal methods, learned models and research planning:

- baseline defined;
- historical evaluation is leakage-safe;
- knowledge-at-T cutoff preserved;
- calibration/uncertainty and subgroup/regime performance evaluated where relevant;
- reproducibility manifest exists;
- resource performance benchmarked;
- failure analysis recorded;
- shadow/canary validation performed when required before promotion.

See `docs/13_QUALITY/reproducibility-backtesting.md`.

### Gate G — Real-system validation

If the feature integrates a browser/API/database/broker/object store/model/runtime/external service, validate against the closest safe real environment available.

Mocks alone are insufficient proof of integration correctness.

### Gate H — Security / privacy / policy

- trust boundaries reviewed;
- secrets handled correctly;
- untrusted input isolated/validated;
- authn/authz and tenant scope tested where applicable;
- dependency/security tooling passes;
- high-risk behavior receives adversarial review;
- visibility/retention/sensitive-data semantics reviewed where applicable.

### Gate I — Performance, reliability and operations

When applicable:

- latency/throughput/resource budget validated;
- retries/idempotency/timeouts/backpressure tested;
- failure/recovery behavior tested;
- degradation behavior explicit;
- no unbounded memory/world loading;
- operator diagnostics/rollback/replay exist.

### Gate J — Observability

When applicable:

- logs identify runs/jobs/errors without leaking secrets;
- metrics/SLIs cover important behavior;
- traces/lineage support diagnosis;
- alert conditions are defined for material operational failures;
- observability itself is tested where practical.

### Gate K — Documentation, traceability and handover

- canonical docs updated;
- capability/work/progress/dependency/requirement/assumption/risk registries updated;
- traceability chain updated;
- ADR created/updated when a decision changed;
- `PROJECT_STATE.md` updated if this is active work;
- next agent can resume without chat history.

## 11. Review Council and independence

Use `docs/13_QUALITY/review-council.md`.

Material work requires explicit review perspectives. Foundational/security/high-risk/world-semantic changes target context-separated or multi-reviewer validation rather than author-only approval.

Reviewers inspect source artifacts/diffs/tests, not merely the author's summary.

## 12. Non-compensable gates

Numeric score cannot compensate for critical failures. A work item cannot be DONE with an applicable unresolved hard-gate failure in:

- Constitution/invariants;
- security/authorization;
- epistemic truth labeling;
- provenance/time semantics;
- critical traceability;
- required verification/real-system validation;
- scientific leakage/reproducibility;
- resumability/handover.

See `project-scorecard.md`.

## 13. Merge rule

A PR may be merged only when:

- acceptance criteria are met;
- applicable gates are green;
- required Review Council findings are resolved;
- unresolved blockers are absent;
- state/registries/docs accurately describe what now exists.

Do not merge merely because CI is green or because a reviewer summary sounds persuasive.

## 14. Post-merge

After merge:

- work item becomes `DONE` only if Definition of Done is actually satisfied;
- downstream blocked work may become `READY`;
- progress matrix is updated;
- next work item becomes active explicitly;
- obsolete branches are removed according to repository policy;
- any new assumptions/risks requiring future validation remain tracked.

## 15. Bug workflow

A bug fix must:

1. create/reference a work item or tracked issue;
2. reproduce the bug where feasible;
3. identify the requirement/contract violated;
4. add a failing regression test first or explain why impossible;
5. fix the smallest responsible layer;
6. validate adjacent contracts and blast radius;
7. add real-system reproduction for integration defects when practical;
8. preserve the regression as a permanent test case where appropriate;
9. update docs if observed behavior/contract changes.

## 16. Architecture-change workflow

Before implementing a durable architecture change:

1. inspect existing ADRs;
2. search dependency/traceability graph;
3. create a new ADR if the choice is significant or irreversible/costly;
4. record considered alternatives;
5. identify assumptions/risks;
6. identify migration, reprocessing and rollback;
7. link affected requirements/work items/capabilities;
8. implement only after decision status permits it.

## 17. Model/scientific change workflow

Before promoting a model/detector/forecast/research-method change:

1. define target requirement and baseline;
2. freeze evaluation protocol/holdout where applicable;
3. prevent temporal/entity/source leakage;
4. run backtests/experiments with `EXP-*` manifests;
5. evaluate quality, calibration, robustness and resources;
6. perform required Model Science/Domain/Epistemic/V&V reviews;
7. shadow/canary important replacements;
8. promote through explicit versioned decision;
9. preserve previous version and rollback path.

## 18. Scope escalation

When an implementation/specification reveals adjacent required work:

- if strictly necessary for current acceptance criteria, add it to the plan and explain why;
- if useful but not required, create a follow-up work item;
- never silently turn one sublot into a whole new subsystem.

## 19. Release/lot exit review

At the end of every sublot and lot, perform a structured retrospective:

- capabilities/requirements promised vs delivered;
- open defects;
- test/coverage health;
- scientific/backtest health where applicable;
- security/privacy findings;
- performance/resource results;
- observability/operational readiness;
- documentation/traceability freshness;
- assumption/risk debt;
- dependency debt;
- architecture deviations;
- real-system validation;
- lessons and follow-up work.

A lot is not complete until this review is recorded.

## 20. Meta-process improvement

The process itself is versioned and reviewed. If repeated defects escape a gate, create a work item to improve the process/test/tooling rather than relying on agents to "remember to be more careful" next time.
