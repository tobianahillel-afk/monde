# MONDE Testing Strategy

Status: Accepted  
Canonical: Yes

## Objective

Testing must prove that MONDE behaves correctly under realistic conditions, not merely that isolated functions execute.

The repository targets **100% meaningful line and branch coverage for project-owned executable code**, with reviewed exceptions only.

## Test pyramid / portfolio

MONDE uses multiple complementary suites.

### 1. Unit tests

Purpose: deterministic validation of small logic units.

Required for:
- parsers and normalizers;
- temporal/spatial utilities;
- confidence calculations;
- entity matching logic;
- state transitions;
- serialization/validation;
- policy and permission logic;
- retry/backoff and error classification;
- model pre/post-processing.

Unit tests should cover boundary values and failure paths, not just representative happy cases.

### 2. Property-based tests

Use where invariants are stronger than examples.

Candidates:
- temporal interval operations;
- reversible entity merge/split semantics;
- identifier normalization;
- units/conversions;
- graph transforms;
- deduplication/idempotency;
- serialization round-trips;
- conservation constraints.

### 3. Contract/schema tests

Every stable boundary should have executable contracts.

Validate:
- API request/response schemas;
- events/messages;
- database/lakehouse schemas;
- source connector outputs;
- model inputs/outputs;
- capability DSL contracts;
- version compatibility and migrations.

Breaking changes require explicit migration/versioning and ADR review where material.

### 4. Integration tests

Test real supported dependencies in isolated environments whenever feasible.

Examples:
- PostgreSQL/PostGIS;
- ClickHouse;
- object store compatible with production contract;
- message broker/event stream;
- search engine;
- cache;
- browser runtime;
- local model serving runtime.

Mocks can isolate failures but cannot replace all real-dependency integration tests.

### 5. Connector tests

Every external data connector should have:

- parser fixtures from representative real source material;
- schema drift tests;
- pagination/delta tests;
- rate-limit behavior;
- retry/timeout behavior;
- duplicate delivery/idempotency;
- malformed/partial input;
- time-zone/time-vintage tests;
- provenance completeness assertions.

When a safe sandbox/test endpoint exists, include periodic live contract checks.

### 6. Browser end-to-end tests

Browser-dependent behavior must be tested in a real supported browser engine.

Cover:
- navigation;
- JavaScript-rendered pages;
- downloads;
- session persistence;
- authorized authentication flows where test accounts exist;
- form interactions;
- page/DOM changes;
- screenshots/snapshots;
- network failures/timeouts;
- challenge detection and human-assisted handoff behavior.

Do not rely only on mocked DOM fixtures for browser acquisition correctness.

### 7. End-to-end system tests

Validate complete paths such as:

`source → capture → parse → evidence → entity resolution → ledger → serving/API → UI/query`

Important flows should assert provenance and temporal lineage at every boundary.

### 8. Golden-world tests — MONDE Mini

Maintain a small deterministic synthetic/curated world containing:

- people;
- organizations;
- places;
- buildings;
- observations;
- conflicting claims;
- source revisions;
- temporal relations;
- events;
- forecasts/scenarios.

Every core engine runs against MONDE Mini in CI to detect semantic regressions.

MONDE Mini must include intentionally difficult cases:
- same-name different entities;
- aliases changing over time;
- contradicting sources;
- stale evidence;
- missing values;
- approximate dates;
- duplicate/reposted information;
- inferred vs observed state.

### 9. Regression tests

Every production-relevant bug receives a regression test when technically feasible.

The regression test should fail before the fix and pass after it.

### 10. Security tests

Depending on component:

- SAST/static analysis;
- dependency vulnerability scan;
- secret scanning;
- authn/authz tests;
- tenant isolation;
- SSRF/path traversal/deserialization/upload tests;
- prompt-injection/untrusted-content boundary tests;
- malicious document/archive tests in isolated fixtures;
- privilege-boundary tests;
- rate/abuse control tests.

High-risk capabilities require dedicated abuse-case/red-team test plans.

### 11. Data-quality tests

Every important data product should test:

- schema validity;
- required provenance fields;
- uniqueness where expected;
- referential integrity;
- plausible ranges;
- unit correctness;
- temporal consistency;
- spatial validity;
- missingness semantics;
- revision handling;
- freshness expectations;
- source coverage changes.

### 12. Epistemic invariant tests

CI should eventually assert globally that:

- inferred data is not labeled observed;
- observations retain source/evidence;
- source time and ingestion time are distinct;
- simulations cannot mutate observed state;
- entity merges remain reversible;
- confidence/uncertainty is present for uncertain inference;
- historical state is not silently overwritten.

### 13. Model tests

AI/ML components require more than unit coverage:

- fixed evaluation sets;
- per-domain/per-language metrics;
- calibration metrics where probabilistic;
- latency and memory benchmarks;
- robustness tests;
- drift checks;
- false-positive/false-negative analysis;
- deterministic version/model artifact references;
- comparison against current promoted model.

Model promotion requires Model Tournament or equivalent acceptance process once available.

### 14. Performance tests

For material paths define budgets for:

- p50/p95/p99 latency;
- throughput;
- CPU/GPU utilization;
- peak memory;
- I/O and storage growth;
- network usage;
- cost per unit of work.

Test representative scale and adversarial worst cases. Avoid extrapolating from toy data without documenting the assumption.

### 15. Load / soak tests

Long-running and streaming components should be tested for:

- memory leaks;
- queue accumulation;
- backpressure;
- retry storms;
- connection leaks;
- clock/time-window issues;
- state drift;
- graceful restart/recovery.

### 16. Chaos/failure-injection tests

For critical paths inject:

- dependency timeout;
- partial source failure;
- duplicate events;
- out-of-order events;
- corrupted payload;
- stale cache;
- lost worker;
- database failover;
- object-store transient failure;
- model unavailable.

Correct behavior should degrade explicitly rather than silently fabricate certainty.

### 17. UI tests

Console/Globe eventually require:

- component tests;
- accessibility tests;
- visual regression for critical views;
- browser E2E;
- context synchronization tests;
- temporal navigation/replay tests;
- evidence drill-down tests;
- permission/visibility tests;
- large-data rendering tests.

### 18. Real-world validation

Before shipping an integration, validate with representative real-world inputs/environment where safe and authorized.

Examples:
- actual public API schema;
- real public PDF/document formats;
- real browser rendering;
- real geospatial data;
- real database engines;
- real video/audio samples with known expected extraction.

Production itself must not become the first meaningful integration test.

## Coverage policy

Coverage gates should eventually enforce:

- line coverage: 100% project-owned executable code;
- branch coverage: 100% project-owned executable code;
- changed-code coverage: 100%;
- reviewed exclusions only.

Exclusions must be documented with:
- exact files/lines;
- reason;
- risk;
- alternative validation;
- reviewer approval;
- expiry/review date when appropriate.

Generated/vendor code is outside the project-owned coverage denominator.

## Test evidence in work items/PRs

Every PR records:

- suites executed;
- exact commands/workflows;
- environment;
- coverage result;
- live/real-system checks;
- failures intentionally tested;
- performance results when applicable;
- known gaps.

## Flaky-test policy

A flaky test is a defect.

It must be fixed, quarantined with a tracked work item and explicit owner, or removed only if the behavior is covered by a better deterministic test.

Never normalize repeated reruns as the standard way to make CI green.

## Final principle

**Tests are executable evidence that the implementation satisfies MONDE's contracts in realistic conditions. Coverage is a floor; semantic correctness is the goal.**
