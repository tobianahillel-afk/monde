# MONDE Capability Registry

Status: Accepted  
Canonical index contract: Yes

## Purpose

Every validated MONDE capability receives a stable immutable identifier (`CAP-001`, `CAP-002`, ...). The registry prevents functionality from being forgotten, duplicated under a new name, or incorrectly marked complete.

## Capability lifecycle

Recommended statuses:

- `PROPOSED` — idea captured but not yet accepted into product scope.
- `PLANNED` — accepted capability, not implementation-ready.
- `READY` — dependencies/specification sufficient to schedule.
- `IN_PROGRESS` — implementation work active.
- `PARTIAL` — useful subset exists but capability contract is incomplete.
- `IN_REVIEW` — implementation claims completion and is under review.
- `DONE` — Definition of Done satisfied and evidence recorded.
- `DEPRECATED` — retained historically but should not be used for new work.
- `CANCELLED` — intentionally removed from planned product scope; ID is never reused.

## Immutable ID rule

A CAP ID is never reused or renumbered after assignment.

Renaming a feature does not create a new capability unless the semantics are materially different.

When a capability is superseded, keep both records and link `supersedes`/`superseded_by`.

## Required traceability

Each capability should eventually resolve this chain:

`CAP-ID → canonical docs → engines → schemas/contracts → dependencies/reuse → work items → implementation → tests → observability → status`

A UI screen or code file alone does not prove a capability is implemented.

## Duplicate-prevention protocol

Before creating a capability:

1. search capability names and synonyms;
2. search related engines/lenses/experiences;
3. search active/planned work items;
4. determine whether the request extends an existing CAP ID;
5. create a new ID only when semantics are genuinely distinct.

## Completion rule

`implementation_status: DONE` is insufficient on its own.

A capability is product-level `DONE` only when applicable:

- implementation complete;
- tests complete;
- documentation complete;
- dependencies satisfied;
- required data/source coverage exists;
- security/risk review complete;
- real-system validation complete;
- user experience/API exposure behaves as specified;
- Definition of Done satisfied.

## Initial inventory task

Before substantive implementation, MONDE must perform a canonical inventory of **all previously validated capabilities** from project history, deduplicate them semantically without deleting validated scope, assign stable CAP IDs and place them in this registry.

Use `_TEMPLATE.yaml` for individual entries until a generated registry/index is introduced.
