# MONDE Architecture Decision Records (ADR)

Status: Accepted  
Canonical: Yes

## Purpose

ADRs preserve **why** significant technical/product architecture decisions were made so future agents do not rediscover or reverse them accidentally.

## When an ADR is required

Create an ADR for decisions that are:

- difficult/costly to reverse;
- cross-cutting;
- contract/schema changing;
- security/trust-boundary changing;
- storage/compute/deployment architecture changing;
- constitutional/epistemic semantic changing;
- introducing a major dependency/service;
- replacing a previously accepted architecture;
- materially affecting data retention, lineage or permissions.

Do not create ADRs for trivial local implementation details.

## Naming

`ADR-0001-short-kebab-title.md`

IDs are immutable and never reused.

## Statuses

- `Proposed`
- `Accepted`
- `Rejected`
- `Superseded`
- `Deprecated`

## Template

```markdown
# ADR-XXXX — Title

Status: Proposed
Date: YYYY-MM-DD
Owners: optional
Related Work: WORK-XXXX
Related Capabilities: CAP-...
Supersedes: optional ADR-...

## Context

What problem/constraint requires a durable decision?

## Decision

What is being decided?

## Alternatives considered

### Alternative A
Pros / cons.

### Alternative B
Pros / cons.

## Consequences

Positive, negative and neutral consequences.

## Compatibility / migration

Existing contracts/data/behavior affected.

## Security / epistemic impact

Trust, provenance, temporal, uncertainty, privacy/permission implications.

## Validation

How the decision will be tested/benchmarked/verified.

## Rollback / supersession

How to reverse or replace this choice.
```

## Rules

1. ADRs describe decisions, not implementation diaries.
2. Accepted ADRs are canonical for the scope they decide.
3. Never edit an accepted ADR to hide that the decision changed; supersede it with a new ADR and update status/linkage.
4. Work items and PRs link relevant ADRs.
5. Canonical architecture docs reflect the current accepted state and reference relevant ADRs.
6. Constitutional changes require an explicit ADR that identifies affected invariant numbers.

## Bootstrap ADR backlog

The following decisions should be formalized before substantial implementation:

- modular monolith / initial process topology;
- canonical World Ledger/storage approach;
- Observed/Estimated/Simulated separation implementation;
- identifier strategy;
- PostGIS/H3 spatial strategy;
- capability ID immutability/registry contract;
- schema/versioning strategy;
- event/queue semantics;
- world-generation publication semantics;
- model registry/promotion semantics.
