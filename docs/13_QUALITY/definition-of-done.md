# MONDE Definition of Done

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

A work item is `DONE` only when every applicable criterion below is satisfied or an explicit reviewed exception is documented at the appropriate assurance/risk level.

`DONE` cannot be obtained by averaging away a failed hard gate.

## Readiness/history

- The work entered implementation/specification through the Definition of Ready or an explicit bounded discovery exception.
- Scope changes discovered during execution were recorded rather than silently absorbed.
- Material assumptions/risks discovered during work are no longer hidden in transient reasoning.

## Functional / requirements

- Acceptance criteria are satisfied.
- Applicable `REQ-*` requirements are satisfied or intentionally superseded.
- Behavior matches canonical contracts/documentation.
- Failure modes and edge cases have defined behavior.
- No unrelated scope was silently added.
- No material implemented behavior is orphaned from requirement/capability/rationale.

## Specification quality

For substantial canonical behavior:

- specification-quality gates were completed;
- existing concepts/synonyms were searched;
- dependencies/upstream/downstream impact were reviewed;
- assumptions and risks are explicit;
- examples/counterexamples disambiguate semantics;
- a cold-read reviewer can understand what to build/test without chat history;
- conflicting related canonical docs were updated or superseded.

## Architecture

- Existing components were searched and reused where appropriate.
- No duplicate primitive/engine/schema/helper/capability was introduced.
- Dependencies and contracts are explicit.
- Blast radius/migrations/reprocessing are handled.
- Relevant ADRs are respected or superseded explicitly.
- Changes do not violate the MONDE Constitution.
- Applicable architecture fitness functions pass.

## Data / epistemics

When applicable:

- provenance is retained;
- event/source/ingestion time semantics remain distinct;
- observed/estimated/simulated states remain distinct;
- uncertainty/confidence is explicit and appropriately calibrated;
- missing-value semantics are correct;
- revisions/history are preserved;
- entity resolution is reversible where identity is uncertain;
- source independence/ancestry is not falsely inflated;
- knowledge-at-T semantics are preserved in replay/backtest;
- no future-information leakage is known.

## Tests / verification

- Unit tests pass where applicable.
- Property/metamorphic tests pass where useful.
- Integration tests pass.
- Contract/schema tests pass.
- End-to-end tests pass where applicable.
- Regression tests cover fixed defects.
- Security tests pass where applicable.
- Performance/resource tests or benchmarks pass where applicable.
- Real-system validation has been performed for integrations where practical.
- Project-owned executable code meets 100% meaningful line and branch coverage target, or a reviewed exception exists.
- Important `TEST-*` artifacts identify the requirements/contracts/risks they protect where this traceability is material.

## Test strength

- Assertions test behavior, not merely execution.
- Important negative/failure paths are covered.
- Time, concurrency, retry and idempotency cases are tested where relevant.
- Tests are deterministic or explicitly model nondeterminism.
- Flaky tests are treated as defects.
- Mocks are not the sole proof of external integration correctness.
- A3/A4 components use stronger techniques from `advanced-verification.md` where justified: mutation, fuzzing, differential/metamorphic testing, fault injection or model checking.

## Scientific/model validation

When applicable:

- baseline/comparator is defined;
- evaluation/backtest is temporally leakage-safe;
- relevant holdout/subgroup/regime checks are complete;
- calibration/uncertainty metrics are reported;
- reproducibility `EXP-*` manifest exists;
- model/data/feature/code versions are traceable;
- resource/latency cost is measured;
- failure analysis is recorded;
- shadow/canary validation is complete where required for promotion;
- previous promoted behavior and rollback path are retained.

## Security / privacy / policy

- Input trust boundaries are identified.
- Required threat model is complete/current.
- Secrets are not committed/logged/exposed.
- Authentication/authorization/tenant boundaries are tested where relevant.
- Untrusted content is isolated/validated before entering trusted state.
- Dependency/static/secret scanning requirements are green where configured.
- High-risk functions receive appropriate adversarial review.
- Visibility/retention/derived-data policy is preserved where applicable.
- No unresolved critical security/authorization finding exists.

## Reliability / operations

- Timeouts, retries, backoff and idempotency are defined where needed.
- Backpressure/queue growth is bounded where needed.
- Recovery behavior is tested.
- Degradation behavior is explicit (stale/partial/unknown/fail-closed/etc.).
- Replay/reprocessing/rollback exists where required.
- Failures are diagnosable without attaching a debugger to production.
- Resource consumption is bounded and documented for material paths.

## Performance / NFRs

When relevant:

- applicable NFRs are explicit;
- latency/throughput/freshness objectives are defined;
- memory/storage/compute/cost budgets are defined;
- representative benchmark/load profile executed;
- no hidden O(world) or unbounded in-memory assumption exists;
- performance improvements do not silently weaken correctness/provenance/permissions.

## Observability

When relevant:

- logs include useful run/job/version context without secrets;
- metrics/SLIs cover protected behavior;
- traces/lineage support diagnosis;
- alerting is defined for material failure/degradation;
- dashboards/runbooks exist for critical operational components;
- observability paths are validated where practical.

## Documentation / research provenance

- Canonical behavior documentation updated.
- Public/internal contracts documented.
- New concepts added to glossary/architecture docs when required.
- Examples updated if behavior changed.
- ADR updated/created for significant decisions.
- External factual/technical assumptions material to the design were researched or explicitly left as tracked assumptions.
- Research findings promoted into canonical artifacts through review rather than copied blindly.

## Traceability / registries

- Work item status and task/run log updated.
- Progress matrix updated.
- Dependencies/reuse declarations updated.
- `REQ-*`, `ASM-*`, `RISK-*`, `CAP-*` and affected registries updated as applicable.
- Important reviews/tests/experiments are linked where applicable.
- Requirement → capability/design → implementation → verification trace is intact for critical behavior.
- `PROJECT_STATE.md` updated when active project state changes.
- Known limitations and follow-up work are recorded.

## Review

- Self-review complete.
- Diff reviewed for accidental changes, duplication and dead code.
- Required Review Council hats were completed for the artifact/risk class.
- Required review independence level was met or exception approved.
- Architecture/specification/test/security/data/performance/operations reviews completed where applicable.
- Critical assumptions were challenged.
- No unresolved blocking review finding remains.

## Handover

- Another agent can resume without chat history from `PROJECT_STATE` + active work item + linked/read-before records.
- Next action is explicit.
- No important decision remains only in a conversation or transient model reasoning.

## Hard-gate rule

Applicable failures in Constitution, critical security/authorization, epistemic truth labeling, provenance/time semantics, critical traceability, required real-system validation, scientific leakage/reproducibility or handover remain blocking regardless of numeric score.

## Final rule

`DONE` means **specified, implemented where applicable, verified, scientifically validated where applicable, secure, documented, observable, reproducible, auditable and safely resumable**.

If any mandatory claim is unknown, use `PARTIAL`, `BLOCKED` or `IN_REVIEW`, not `DONE`.