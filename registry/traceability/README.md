# MONDE Traceability Registry

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

MONDE must be able to answer for every important behavior: why does this exist, what implements it, what proves it works, and what breaks if it changes?

The target trace is:

`PRODUCT GOAL → REQ-ID → CAP-ID → ADR/DESIGN → ENGINE/SCHEMA → WORK-ID → IMPLEMENTATION → TEST-ID → VALIDATION EVIDENCE → MONITOR/SLI`

## Bidirectional traceability

Traceability is not only requirement → code.

MONDE must support:
- forward trace: requirement to implementation/tests;
- backward trace: code/schema/model back to requirement/capability/rationale;
- impact trace: component to downstream dependents;
- evidence trace: result back to source/model/data versions;
- historical trace: current contract to superseded decisions/versions.

## Orphan rules

The following are defects unless explicitly justified:

- Accepted material requirement with no verification path;
- implemented major behavior with no requirement/capability/work rationale;
- capability marked DONE with no test/validation evidence;
- stable schema field with undocumented semantics;
- test whose protected requirement/contract is unknown;
- dependency not represented in work/architecture metadata;
- canonical doc contradicted by another accepted canonical doc;
- production monitor/SLO with no owner or protected behavior.

## Change-impact query

Before changing a stable concept, future tooling should be able to resolve:

`WHAT DEPENDS ON X?`

and return:
- requirements;
- capabilities;
- engines/components;
- schemas/APIs/events;
- models/features;
- experiences;
- work items;
- tests/golden cases;
- documentation/ADRs;
- monitors/SLOs;
- data reprocessing/migration needs.

## Matrix target

A generated traceability matrix should eventually contain rows such as:

| Requirement | Capability | Component | Contract | Work | Tests | Evidence | Status |
|---|---|---|---|---|---|---|---|
| REQ-... | CAP-... | ENGINE-... | SCHEMA-... | WORK-... | TEST-... | VAL-... | ... |

The matrix should be generated from registries rather than manually duplicated where possible.

## Validation targets

Governance CI should eventually detect:
- broken IDs;
- orphan Accepted requirements;
- orphan DONE capabilities;
- cycles where prohibited;
- stale references to superseded contracts;
- duplicate aliases without canonical mapping;
- work items changing a contract without listing it;
- test files not mapped to protected requirements for critical areas;
- changed critical requirements without corresponding test review.

## AI navigation use

Traceability is also a context router. An AI continuing existing work should follow only the relevant chain rather than load the entire repository.

Example:

`WORK-0172 → CAP-042 → ENGINE-EVIDENCE → SCHEMA-CLAIM → ADR-0031 → tests/evidence`

This gives minimal sufficient context while preserving cross-component correctness.

## Historical rule

Do not delete traceability because an artifact is superseded. Preserve historical relationships and mark current/superseded status so a past commit or forecast can be reconstructed.