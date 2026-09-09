# MONDE Specification Quality Protocol

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

MONDE treats specifications as engineered artifacts, not prose notes. A specification can create defects long before code exists; therefore canonical documentation must be researched, decomposed, cross-checked, reviewed and validated with the same discipline as implementation.

The objective is that a new AI agent can safely extend MONDE without silently duplicating concepts, contradicting upstream semantics, omitting downstream consequences or turning assumptions into requirements.

## Canonical specification lifecycle

Substantial product, architecture, engine, data, model or experience specifications follow:

`DISCOVER → INVENTORY → REQUIREMENTS → DEPENDENCY/IMPACT → ASSUMPTIONS → OPTIONS → SPECIFY → EXAMPLES/COUNTEREXAMPLES → TRACE → REVIEW → VALIDATE → ACCEPT`

A document is not `Accepted` merely because it is detailed.

## Gate S0 — Discovery and inventory

Before writing a new specification:

1. search capability registry by name, synonyms and neighboring concepts;
2. search work items for overlapping active/planned work;
3. search canonical docs for existing semantics;
4. inspect relevant ADRs;
5. inspect dependency/reuse declarations;
6. identify upstream primitives/contracts and downstream consumers;
7. identify historical names or superseded concepts;
8. record what is being reused versus newly introduced.

The output is a short inventory section or linked work-item record.

### Duplicate-prevention rule

A new term is not evidence that a new concept is required. If two concepts have the same semantics, extend or alias the existing canonical concept rather than create a duplicate.

## Gate S1 — Atomic requirements

Specifications must translate intent into atomic, testable requirements where behavior is material.

Each requirement should state:

- stable `REQ-*` ID;
- requirement type;
- normative statement;
- rationale;
- source/decision provenance;
- capabilities/components affected;
- dependencies;
- acceptance/evidence method;
- status.

Requirements should distinguish:

- functional behavior;
- data/epistemic semantics;
- performance/resource constraints;
- security/privacy/policy constraints;
- reliability/availability constraints;
- observability/audit constraints;
- UX/accessibility constraints;
- compatibility/migration constraints.

Avoid compound requirements containing multiple independently fail-able obligations.

## Gate S2 — Dependency and change-impact analysis

Before changing a canonical concept, answer:

- What depends on this?
- What does this depend on?
- Which schemas/contracts represent it?
- Which capabilities reuse it?
- Which engines produce/consume it?
- Which experiences expose it?
- Which tests/golden cases encode current behavior?
- Which ADRs constrain it?
- Which data/source/model registries rely on it?

The work item records affected areas. High-impact changes require an explicit impact map.

### Blast-radius classes

- `LOCAL` — one component, no stable contract change.
- `CROSS_COMPONENT` — multiple internal components.
- `CONTRACT` — stable interface/schema/semantic change.
- `WORLD_SEMANTIC` — changes canonical world/evidence/time/identity semantics.
- `CONSTITUTIONAL` — changes a MONDE invariant.

`WORLD_SEMANTIC` and `CONSTITUTIONAL` changes require architecture + epistemic review and normally an ADR.

## Gate S3 — Assumption ledger

Any material uncertainty used to design the specification becomes an `ASM-*` record rather than hidden prose.

Examples:

- expected source update frequency;
- expected traffic volume;
- presumed browser behavior;
- expected model quality;
- assumed user workflow;
- assumed external identifier stability.

Each assumption declares:

- evidence;
- confidence;
- impact if false;
- validation method;
- expiry/review condition.

Critical assumptions must be validated before dependent work is considered production-ready.

## Gate S4 — Alternatives and decision quality

For durable architectural choices, document at least:

- chosen option;
- viable alternatives;
- reasons for rejection;
- expected benefits;
- costs/trade-offs;
- reversibility;
- migration path;
- uncertainty.

Use an ADR when the choice is durable, cross-cutting or expensive to reverse.

## Gate S5 — Complete behavioral specification

A canonical feature/engine specification should answer, where applicable:

1. What problem does it solve?
2. Who/what consumes it?
3. Inputs and preconditions?
4. Outputs and postconditions?
5. State transitions?
6. Temporal semantics?
7. Spatial semantics?
8. Provenance/lineage semantics?
9. Confidence/uncertainty semantics?
10. Missing-data semantics?
11. Identity/entity semantics?
12. Permissions/visibility?
13. Failure modes?
14. Retry/idempotency semantics?
15. Resource/latency expectations?
16. Observability requirements?
17. Security trust boundaries?
18. Backward compatibility/migration?
19. Examples and counterexamples?
20. How will correctness be verified?

Not every document needs every section; applicable omissions require a reason when the topic is material.

## Gate S6 — Examples, adversarial cases and counterexamples

Every important specification should contain enough examples to disambiguate semantics.

Also include counterexamples such as:

- same name but different entity;
- new evidence contradicting existing belief;
- out-of-order timestamp;
- stale/revised source;
- partial source failure;
- permission mismatch;
- duplicate/reposted evidence;
- missing value versus zero;
- inferred result incorrectly tempting promotion to observation;
- high load/resource pressure.

Examples become candidates for executable tests or MONDE Mini scenarios later.

## Gate S7 — Traceability

A material requirement should eventually be traceable through:

`PRODUCT GOAL → REQ-ID → CAP-ID → DESIGN/ADR → ENGINE/SCHEMA → WORK-ID → CODE/CONFIG → TEST-ID → VALIDATION EVIDENCE → OBSERVABILITY`

No important requirement should be orphaned from validation. No major implementation should exist without a requirement/capability/engineering rationale.

## Gate S8 — Cross-document consistency review

Before acceptance, search related documentation for:

- duplicate definitions;
- conflicting terminology;
- incompatible status values;
- stale references;
- contradictory defaults;
- mismatched units/time semantics;
- different names for the same primitive;
- incompatible dependency direction;
- examples that violate newer invariants.

A canonical change updates or explicitly supersedes affected documents in the same work item.

## Gate S9 — Review Council

Apply review roles from `docs/13_QUALITY/review-council.md` according to artifact risk.

At minimum, a substantive canonical specification requires:

- author/self-review;
- architecture/reuse review;
- verification/testability review;
- documentation/traceability review.

Data/world semantics additionally require epistemic review. Security-sensitive areas require security review. Performance-critical areas require performance/SRE review.

For critical artifacts, independent review should be performed by a different human/agent context where practical; the author should not be the sole approver of its own reasoning.

## Gate S10 — Cold-read resume test

A fresh reviewer/agent should be able to answer from repository state alone:

- what is being specified;
- why it exists;
- what is canonical;
- dependencies/reuse;
- unresolved assumptions;
- edge cases;
- how it will be tested;
- what downstream work is now possible.

If the reviewer needs hidden chat context, the specification is incomplete.

## Scientific quality rules

### Separate evidence, assumption, hypothesis and decision

Do not phrase design assumptions as established facts.

### Falsifiability

For model/detection/forecast claims, state what observation would show the claim/model is wrong or inadequate.

### Baselines

Performance/model claims require a baseline. `better` without comparator, metric and dataset is not a scientific result.

### Leakage prevention

Backtests/evaluations must respect temporal/data leakage boundaries. Information unavailable at prediction time must not enter historical evaluation.

### Reproducibility

Material experiments preserve dataset/version, cutoff, code SHA, configuration, model version, seeds where applicable and metrics.

### Negative results

Failed experiments and rejected architectural alternatives may be valuable. Record them when they prevent future agents from repeating expensive dead ends.

## Documentation validation targets

Governance CI should eventually check:

- valid front matter/status;
- referenced REQ/CAP/WORK/ADR IDs exist;
- canonical documents have owners/status where required;
- broken links/paths;
- duplicate IDs;
- unresolved placeholders in Accepted docs;
- traceability completeness thresholds;
- invalid status transitions;
- stale review dates for assumptions/risks;
- orphan accepted requirements;
- accepted capability with no canonical specification where required.

## Acceptance rule

A substantial document may move to `Accepted` only when its applicable specification gates have evidence. Detail volume is not a substitute for consistency, traceability or testability.