# MONDE Definition of Done

Status: Accepted  
Canonical: Yes

A work item is `DONE` only when every applicable criterion below is satisfied or an explicit reviewed exception is documented.

## Functional

- Acceptance criteria are satisfied.
- Behavior matches canonical contracts/documentation.
- Failure modes and edge cases have defined behavior.
- No unrelated scope was silently added.

## Architecture

- Existing components were searched and reused where appropriate.
- No duplicate primitive/engine/schema/helper/capability was introduced.
- Dependencies and contracts are explicit.
- Relevant ADRs are respected or superseded explicitly.
- Changes do not violate the MONDE Constitution.

## Data / epistemics

When applicable:

- provenance is retained;
- event/source/ingestion time semantics remain distinct;
- observed/estimated/simulated states remain distinct;
- uncertainty/confidence is explicit;
- missing-value semantics are correct;
- revisions/history are preserved;
- entity resolution is reversible where identity is uncertain;
- source independence/ancestry is not falsely inflated.

## Tests

- Unit tests pass.
- Integration tests pass.
- Contract/schema tests pass.
- End-to-end tests pass where applicable.
- Regression tests cover fixed defects.
- Security tests pass where applicable.
- Performance/resource tests or benchmarks pass where applicable.
- Real-system validation has been performed for integrations where practical.
- Project-owned executable code meets 100% meaningful line and branch coverage target, or a reviewed exception exists.

## Test quality

- Assertions test behavior, not merely execution.
- Important negative/failure paths are covered.
- Time, concurrency, retry and idempotency cases are tested where relevant.
- Tests are deterministic or explicitly model nondeterminism.
- Flaky tests are treated as defects.
- Mocks are not the sole proof of external integration correctness.

## Security

- Input trust boundaries are identified.
- Secrets are not committed/logged/exposed.
- Authentication/authorization/tenant boundaries are tested where relevant.
- Untrusted content is isolated/validated before entering trusted state.
- Dependency/static/secret scanning requirements are green.
- High-risk functions receive appropriate adversarial review.

## Reliability / operations

- Timeouts, retries, backoff and idempotency are defined where needed.
- Backpressure/queue growth is bounded where needed.
- Recovery behavior is tested.
- Observability exists: logs/metrics/traces/events appropriate to the component.
- Failures are diagnosable without attaching a debugger to production.
- Resource consumption is bounded and documented for material paths.

## Performance

When relevant:

- latency objective defined;
- throughput objective defined;
- memory/storage/compute budget defined;
- representative benchmark executed;
- no hidden O(world) or unbounded in-memory assumption exists.

## Documentation

- Canonical behavior documentation updated.
- Public/internal contracts documented.
- New concepts added to glossary/architecture docs when required.
- Examples updated if behavior changed.
- ADR updated/created for significant decisions.

## Tracking / handover

- Work item status and task/run log updated.
- Progress matrix updated.
- Dependencies/reuse declarations updated.
- Capability/model/source/engine registries updated where applicable.
- `PROJECT_STATE.md` updated when active project state changes.
- Known limitations and follow-up work are recorded.
- Another agent can resume without chat history.

## Review

- Self-review complete.
- Diff reviewed for accidental changes, duplication and dead code.
- Architecture review complete where applicable.
- Test review complete.
- Security review complete where applicable.
- Data/epistemic review complete where applicable.
- Performance review complete where applicable.
- No unresolved review thread or blocker remains.

## Final rule

`DONE` means **implemented, verified, documented, observable, reproducible, auditable and safely resumable**.

If any of these claims is unknown, use `PARTIAL`, `BLOCKED` or `IN_REVIEW`, not `DONE`.
