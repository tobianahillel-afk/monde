# MONDE Pull Request

## Work tracking

- Work item(s): `WORK-____`
- Phase / Lot / Sublot:
- Assurance level: `A0/A1/A2/A3/A4`
- Related requirements: `REQ-...`
- Related capabilities: `CAP-...`
- Related assumptions: `ASM-...`
- Related risks: `RISK-...`
- Related ADRs:

## Objective

What exact outcome does this PR deliver?

## Definition of Ready

- [ ] Scope/problem was Ready before implementation, or this is an explicit bounded discovery/spike.
- [ ] Existing capabilities/requirements/work/components were searched, including synonyms.
- [ ] Dependencies/reuse and blast radius were identified.
- [ ] Material assumptions/risks were recorded.

## Scope

### In scope

-

### Explicitly out of scope

-

## Dependencies, reuse and impact

- `depends_on`:
- `reuses`:
- Existing components/specifications searched:
- Why any new abstraction/component is necessary:
- Blast radius:
- Upstream dependencies affected:
- Downstream dependents affected:
- Migration/reprocessing implications:

## Contracts / data semantics affected

- Schemas/interfaces:
- Temporal semantics:
- Provenance/evidence impact:
- Observed / Estimated / Simulated impact:
- Identity/uncertainty/missingness impact:
- Permissions/visibility impact:
- Backward compatibility/migration:

Use `N/A` only with a short justification.

## Specification quality

For substantial canonical behavior/docs:

- [ ] Existing/similar concepts and related docs reviewed.
- [ ] Atomic requirements are explicit/testable.
- [ ] Assumptions are separated from facts/decisions.
- [ ] Examples and counterexamples cover ambiguity/failure modes.
- [ ] Cross-document contradiction/duplication check performed.
- [ ] External facts were researched when materially required.
- [ ] Cold-read test passed / N/A with reason.

## Acceptance criteria / requirements

- [ ] AC-1 —
- [ ] `REQ-...` —

## Validation performed

### Unit
- [ ] Passed / N/A:

### Property / metamorphic
- [ ] Passed / N/A:

### Fuzz / mutation / differential / model-based
- [ ] Passed / N/A:
- Techniques used and why:

### Integration
- [ ] Passed / N/A:

### Contract/schema
- [ ] Passed / N/A:

### End-to-end
- [ ] Passed / N/A:

### Regression
- [ ] Passed / N/A:

### Real-system validation
- [ ] Passed / N/A:
- Environment/service/browser/API/database used:
- Evidence/result:

### Coverage
- Line coverage:
- Branch coverage:
- Changed-code coverage:
- Mutation score where applicable:
- Exclusions/exceptions:

## Scientific / backtest validation

For model/detector/forecast/entity-resolution/research methods:

- [ ] Baseline/comparator defined / N/A
- [ ] Leakage-safe knowledge-at-T evaluation / N/A
- [ ] Holdout/subgroup/regime checks / N/A
- [ ] Calibration/uncertainty evaluated / N/A
- [ ] `EXP-*` reproducibility manifest linked / N/A
- [ ] Resource/latency benchmark / N/A
- [ ] Shadow/canary validation / N/A
- Backtest/experiment IDs:
- Failure analysis:

## Non-functional requirements

- Performance/latency target:
- Throughput/scale target:
- Freshness target:
- Memory/storage/compute/cost budget:
- Availability/reliability target:
- RPO/RTO/recovery requirement:
- Degradation behavior:

## Security / threat model

- [ ] Trust boundaries reviewed.
- [ ] Threat model updated / N/A.
- [ ] Secrets/logging reviewed.
- [ ] Authn/authz/tenant scope tested / N/A.
- [ ] Untrusted-input boundary reviewed.
- [ ] Dependency/static/secret checks passed where configured.
- [ ] Adversarial review completed when required.
- Relevant `RISK-*`:

## Observability / operations

- Logs:
- Metrics / SLIs / SLOs:
- Traces/lineage:
- Alerts:
- Runbook/operator behavior:
- Rollback/replay/reprocessing tested:

## Failure modes tested

List meaningful negative/adversarial/failure cases explicitly.

-

## Review Council

- Required independence level:
- Required hats:
- `REVIEW-*` records:
- [ ] Architecture/reuse
- [ ] Verification & validation
- [ ] Data/epistemic where applicable
- [ ] Security/privacy where applicable
- [ ] Performance/SRE where applicable
- [ ] Model science/domain where applicable
- [ ] Documentation/traceability
- [ ] Red-team/skeptic where required
- Open findings:

## Traceability / documentation / registry updates

- [ ] Canonical docs updated.
- [ ] Work item updated.
- [ ] Progress matrix updated.
- [ ] `REQ/ASM/RISK/CAP` records updated where applicable.
- [ ] `TEST/EXP/REVIEW` evidence linked where applicable.
- [ ] Dependency declarations updated.
- [ ] Traceability chain updated.
- [ ] ADR created/updated where applicable.
- [ ] `PROJECT_STATE.md` updated if active project state changed.

## Hard gates

Confirm no unresolved applicable blocker exists in:

- [ ] Constitution / architecture invariants
- [ ] Security / authorization / visibility
- [ ] Epistemic truth labeling
- [ ] Provenance / temporal semantics
- [ ] Critical traceability
- [ ] Required verification / real-system validation
- [ ] Scientific leakage / reproducibility
- [ ] Handover / resumability

## Known limitations / follow-up work

-

## Rollback

How can this change be safely reverted, disabled or reprocessed?

## Handover check

- [ ] A new agent can resume from `PROJECT_STATE.md` + work item + linked/read-before artifacts without chat history.
- [ ] No important decision exists only in the PR discussion or transient reasoning.

## Final reviewer decision

- [ ] Definition of Ready respected
- [ ] Acceptance criteria/requirements satisfied
- [ ] Applicable assurance gates satisfied
- [ ] Definition of Done satisfied
