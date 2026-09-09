# MONDE Non-Functional Requirements & Quality Attributes

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

A function can be logically correct and still be unusable, unsafe or scientifically misleading. MONDE therefore treats non-functional requirements (NFRs) as explicit, testable requirements rather than implicit aspirations.

NFRs should use `REQ-*` records when material to a capability/component.

## Quality dimensions

### Correctness
- semantic correctness;
- deterministic behavior where promised;
- explicit handling of invalid/partial input.

### Epistemic integrity
- provenance completeness;
- Observed/Estimated/Simulated separation;
- calibrated uncertainty;
- temporal/data-vintage correctness;
- source independence.

### Performance
- p50/p95/p99 latency;
- throughput;
- batch completion time;
- interactive response budget;
- GPU/CPU utilization.

### Resource efficiency
- maximum memory/VRAM;
- storage growth;
- network I/O;
- cost per capture/document/video/query/entity update;
- avoidance of unbounded world-scale operations.

### Scalability
- expected cardinalities;
- horizontal/vertical scaling behavior;
- partitioning/sharding assumptions;
- degradation as world size grows.

### Availability and reliability
- availability objective;
- error budget;
- retry/recovery behavior;
- dependency failure tolerance;
- graceful degradation.

### Durability and recoverability
- RPO;
- RTO;
- replay/rebuild source of truth;
- backup/restore validation;
- corruption detection.

### Freshness
- expected source refresh interval;
- ingestion lag;
- serving lag;
- stale-data behavior;
- freshness confidence.

### Observability
- logs;
- metrics/SLIs;
- traces/lineage;
- alerts;
- diagnostic context;
- operator runbooks.

### Security
- confidentiality/integrity/availability;
- authentication/authorization;
- isolation;
- secret handling;
- supply-chain security;
- untrusted-input controls.

### Privacy / policy / visibility
- data scope;
- tenant/user/source visibility propagation;
- retention/minimization rules where applicable;
- policy enforcement at derived/cached outputs.

### Maintainability
- bounded component responsibility;
- complexity budget;
- testability;
- migration/versioning strategy;
- dependency hygiene;
- understandable ownership.

### Reproducibility
- deterministic/versioned inputs where possible;
- code/config/model/data provenance;
- replayability of important outputs.

### Explainability/auditability
- important results expose drivers, evidence, counter-evidence, uncertainty and version context;
- operators can reconstruct how a result was produced.

### UX and accessibility
For user-facing experiences:
- interaction latency;
- progressive complexity;
- keyboard/accessibility support;
- error/uncertainty communication;
- context preservation Console↔Globe.

## NFR contract example

A material NFR should specify:

```text
REQ-NFR-...
Metric: p95 latency
Scope: Entity 360 evidence query
Target: <value>
Measurement window: <window>
Load profile: <defined workload>
Environment: <reference environment>
Failure threshold: <value>
Verification: TEST/EXP IDs
```

Avoid requirements such as `must be fast` or `must scale` without a measurable definition.

## Budgets before optimization

For performance-sensitive work, define a budget before implementation where practical. Examples:
- maximum interactive latency;
- maximum processing cost per hour of video;
- maximum RAM per worker;
- target events/sec;
- source freshness target.

If the correct budget is unknown, create a benchmark/discovery work item rather than silently optimize toward an arbitrary number.

## SLI/SLO target model

Future `SLO-*` records should define:
- protected user/system outcome;
- SLI formula;
- target;
- measurement window;
- exclusions;
- alert thresholds;
- owner;
- linked requirements/capabilities;
- error-budget policy.

Examples:
- source ingestion freshness;
- World Generation publish lag;
- evidence retrieval availability;
- browser-acquisition success rate;
- stream processing delay;
- critical forecast pipeline completion.

## Performance correctness

Performance optimizations must not silently weaken:
- provenance;
- exact time semantics;
- permission enforcement;
- confidence/uncertainty;
- reproducibility.

Approximate computation is allowed only when the API/result explicitly states approximation semantics and associated error/quality bounds.

## Degradation contracts

For external dependency or overload failure, specify whether the system:
- retries;
- serves stale data with freshness warning;
- falls back to another source/model;
- reduces resolution;
- queues/defer work;
- returns partial/unknown;
- fails closed.

Silent incorrect success is not an acceptable degradation mode.

## Verification

NFR verification may require:
- benchmarks;
- load/soak tests;
- fault injection;
- chaos tests;
- real-engine integration;
- observability assertions;
- cost reports;
- model evaluation/backtests;
- recovery drills.

## Review rule

Every substantial engine/capability specification should explicitly consider these quality dimensions and either:

1. define applicable requirements/budgets, or
2. state why a dimension is not material at that stage.

This prevents AI-generated specifications from focusing only on functional happy paths.