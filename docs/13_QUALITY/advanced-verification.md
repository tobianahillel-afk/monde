# MONDE Advanced Verification Ladder

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

100% line/branch coverage proves execution reach, not that assertions are strong. Critical MONDE components therefore use stronger verification methods where appropriate.

These techniques are selected by assurance level and risk; not every local change needs every method.

## Verification ladder

### V0 — Static correctness

- formatter/linter;
- type checking;
- schema validation;
- dependency/architecture rules;
- static security analysis.

### V1 — Example tests

- unit tests;
- edge cases;
- explicit failures;
- regression examples.

### V2 — Property / invariant testing

Generate broad input spaces and assert invariants rather than only fixed examples.

Good targets:
- temporal interval algebra;
- ID normalization;
- reversible merges;
- idempotency;
- serialization round trips;
- conservation constraints;
- policy monotonicity.

### V3 — Fuzzing

Use fuzzing for parsers/protocols/untrusted boundaries:
- HTML/document/archive parsers;
- API payloads;
- schema decoders;
- URL handling;
- binary/media metadata boundaries;
- query languages.

Track crashes, hangs, memory/resource amplification and invariant violations.

### V4 — Mutation testing

For important deterministic logic, mutate production code and verify tests fail.

Use to detect:
- assertions that merely execute code;
- untested condition meaning;
- weak branch tests;
- misleading 100% coverage.

Core truth/identity/temporal/policy logic should target a high mutation score with justified survivors.

### V5 — Metamorphic testing

When exact expected output is difficult, assert transformations that should preserve/change results predictably.

Examples:
- reordering duplicate source arrivals must not change canonical idempotent outcome;
- unit conversion should preserve physical quantity;
- adding a duplicate repost should not multiply source-independence confidence;
- moving knowledge cutoff earlier must not reveal future evidence;
- increasing restrictive permission scope must not widen visible data.

### V6 — Differential testing

Compare independent implementations/methods on the same input.

Examples:
- two parsers for critical formats;
- specialized model versus deterministic baseline;
- old promoted model versus candidate;
- two independent route/time calculations;
- database query versus reference implementation.

Disagreement becomes an investigation target rather than automatically choosing one answer.

### V7 — Historical replay / backtesting

Use leakage-safe historical event packs and knowledge-at-T replay for models/detectors/research behavior.

See `reproducibility-backtesting.md`.

### V8 — Fault injection / chaos

Inject:
- timeouts;
- partial failures;
- duplicates;
- out-of-order events;
- stale/revised data;
- dependency outage;
- corrupt payload;
- worker loss;
- model unavailable;
- cache inconsistency.

Validate explicit degraded/unknown behavior rather than silent incorrect success.

### V9 — Formal/model-based verification

For small but critical state machines/protocols, consider model-based testing or formal/model checking.

Candidates:
- World Generation publication state machine;
- work/status transitions;
- permission/visibility lattice;
- ledger revision semantics;
- distributed idempotency/deduplication protocol;
- scenario isolation from observed state;
- irreversible migration sequencing.

Formal methods should target narrow critical invariants, not attempt to formally prove the entire system.

## Architecture fitness functions

Durable architectural rules should become executable checks where possible.

Examples:
- forbidden dependency directions;
- no direct writes to canonical world state outside owning boundary;
- no Simulated → Observed dependency path;
- no unversioned model material inference;
- no source timestamp field overwritten by ingestion timestamp;
- no unrestricted cross-tenant cache key;
- no critical module importing an acquisition/browser implementation directly when a contract boundary is required;
- bounded package/component dependency cycles.

Fitness functions run continuously in CI so architecture degradation is detected early.

## Golden semantic assertions

MONDE Mini should include high-value semantic invariants such as:
- duplicate news copies do not become independent evidence;
- approximate dates stay approximate;
- late backfill does not appear as a current event;
- corrected source creates revision history;
- entity split restores independent histories;
- simulation cannot mutate observed world;
- missing observation is not zero;
- stale evidence lowers freshness without deleting history.

## Test independence

For A3/A4 changes, improve independence by having a reviewer or separate agent context propose adversarial/test cases without seeing only the author's intended happy path.

A useful pattern is:

1. author implements/specifies;
2. independent tester derives tests from requirements/contracts;
3. compare author's and tester's case sets;
4. add missing/falsifying cases;
5. reviewer inspects resulting evidence.

## Nondeterministic systems

For ML/distributed/concurrent behavior:
- record seeds when meaningful;
- bound stochastic expectations statistically;
- repeat tests under controlled schedules/loads;
- capture replayable event traces;
- avoid pretending exact deterministic equality where semantics are probabilistic.

## Failure triage

When advanced verification finds a discrepancy classify it:
- implementation defect;
- test defect;
- specification ambiguity;
- invalid assumption;
- model uncertainty;
- flaky/non-deterministic environment;
- external dependency change.

Specification ambiguity discovered by tests is a specification defect and must be repaired canonically.

## Assurance mapping

- A1: V0–V1 normally sufficient.
- A2: V0–V3 as applicable, plus integration/E2E.
- A3: consider V4–V8 based on failure modes.
- A4: use strongest practical combination, including V9 for narrow critical invariants where valuable.

## Final rule

Coverage is a floor. **A test suite is strong when plausible defects, adversarial inputs and semantic violations actually make it fail.**