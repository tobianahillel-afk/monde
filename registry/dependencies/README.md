# Dependency Registry

Status: Accepted

This registry prevents duplicate implementation and unsafe continuation of partially completed work.

## Dependency kinds

Use explicit typed relations:

- `DEPENDS_ON` — cannot function or be completed without target.
- `REUSES` — must use an existing component rather than duplicate it.
- `IMPLEMENTS` — implementation realizes a capability/contract.
- `EXPOSES` — component exposes a contract/API/schema.
- `CONSUMES` — component consumes a contract/data product.
- `BLOCKS` — completion blocks downstream work.
- `SUPERSEDES` — replaces a previous component/decision.
- `VALIDATES_WITH` — requires a test fixture/service/environment.
- `DOCUMENTED_BY` — canonical specification.

## Required dependency record

Every non-trivial reusable component should eventually have a record containing:

```yaml
id: DEP-XXXX
subject: "component-or-work-item-id"
relation: REUSES
target: "component-id"
why: "Why this dependency exists"
contract: "Interface/schema/behavior relied upon"
read_before:
  - path/to/canonical/spec.md
introduced_by: WORK-XXXX
status: ACTIVE
```

## Rules

1. Dependency declarations are directional and typed.
2. Work items must copy the dependencies relevant to their execution into `depends_on`/`reuses`.
3. If a component is superseded, downstream dependency records must be reviewed.
4. Agents must search this registry before introducing an equivalent component.
5. Circular dependencies require explicit architectural review.
6. Hidden runtime dependencies are defects.
7. A dependency on a concrete implementation where a stable contract should exist is an architecture smell and should be reviewed.

## Read-before graph

Dependency records may include `read_before` paths. This makes the dependency graph also a **documentation routing graph**: an agent following a dependency knows which canonical files explain it.
