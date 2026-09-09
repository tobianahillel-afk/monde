# MONDE Review Council

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

AI systems are strong at producing coherent local answers and weaker at noticing omitted constraints, hidden assumptions, cross-document conflicts and failure modes outside the active frame. MONDE therefore uses explicit review "hats" so important work is evaluated from multiple independent perspectives.

A role is a review perspective, not necessarily a separate person. For high-risk or foundational changes, use separate human/agent contexts where practical to reduce correlated blind spots.

## Core review roles

### Product / User Value Reviewer
Checks:
- real user/problem value;
- scope and non-goals;
- duplicated capabilities;
- UX consistency;
- whether complexity is justified.

### System Architect
Checks:
- boundaries and responsibilities;
- reuse before invention;
- dependency direction;
- contracts/interfaces;
- evolvability and reversibility;
- consistency with ADRs and modular architecture.

### Data & Epistemic Reviewer
Checks:
- Observation/Claim/Evidence/Estimate separation;
- provenance and lineage;
- temporal/spatial semantics;
- uncertainty/calibration;
- source independence;
- missingness/revision semantics;
- leakage between Observed, Estimated and Simulated worlds.

### Domain Scientist / Subject-Matter Reviewer
Checks:
- domain assumptions;
- scientific plausibility;
- confounders;
- causal interpretation;
- measurement validity;
- appropriate baselines and external reality.

### Verification & Validation Reviewer
Checks:
- requirements are testable;
- acceptance criteria are complete;
- edge/failure cases;
- test portfolio sufficiency;
- test independence;
- real-system validation;
- regression risk.

### Security Reviewer
Checks:
- trust boundaries;
- authn/authz;
- secrets;
- SSRF/file/parser/browser/plugin risks;
- abuse paths;
- tenant/visibility isolation;
- supply-chain/dependency security.

### Privacy / Policy Reviewer
Checks where relevant:
- visibility and data-scope inheritance;
- minimization/retention;
- sensitive/high-risk capability classification;
- consent/authorization assumptions;
- downstream disclosure risk.

### Performance / SRE Reviewer
Checks:
- latency/throughput/resource budgets;
- bounded memory/storage/compute;
- scaling characteristics;
- retries/backpressure/idempotency;
- availability/degradation/recovery;
- SLO/SLI observability.

### ML / Model Science Reviewer
Checks:
- dataset splits and leakage;
- baselines;
- evaluation metrics;
- calibration;
- robustness across domains/regimes/languages;
- drift;
- reproducibility;
- model promotion/backtest evidence.

### Red Team / Skeptic
Attempts to falsify the proposal by asking:
- what assumption is most likely wrong?
- what adversarial input breaks this?
- where can false confidence arise?
- how could evidence be misleading?
- what simpler explanation exists?
- what happens if every dependency partially fails?

### Documentation / Traceability Reviewer
Checks:
- canonical location;
- terminology consistency;
- requirement/capability/work/ADR links;
- read-before routing;
- stale or orphan docs;
- handover sufficiency;
- examples match current semantics.

### Operations / Incident Reviewer
Checks:
- how failures are detected;
- operator actions;
- rollback/replay/reprocessing;
- forensic/audit evidence;
- incident containment;
- dependency outage behavior.

## Required hats by artifact class

| Artifact/change | Minimum required reviews |
|---|---|
| Product capability spec | Product, Architect, V&V, Documentation |
| World-model semantic change | Architect, Epistemic, V&V, Documentation |
| Data/source connector | Data/Epistemic, V&V, Security, Operations |
| Browser/channel acquisition | Security, V&V, Operations, Performance |
| Model/forecast/detector | Model Science, Domain Scientist, Epistemic, V&V |
| Storage/distributed architecture | Architect, Performance/SRE, Operations, Security |
| Authentication/permissions | Security, Privacy/Policy, V&V, Operations |
| High-risk capability | Security, Privacy/Policy, Red Team, Product, Epistemic |
| Foundational canonical doc | Architect, V&V, Documentation, relevant domain role |
| Major UI/Globe experience | Product, Architect, V&V, Performance, Accessibility/UX as applicable |

## Review independence levels

### L0 — Self-review
Author checks its own work. Required for everything; never sufficient for material work.

### L1 — Perspective-separated review
Same agent/session performs explicit independent hats sequentially and records findings.

### L2 — Context-separated review
A new agent/context reviews without relying on the author's chain of reasoning. Preferred for foundational specifications and important PRs.

### L3 — Multi-reviewer/adversarial review
Multiple independent reviewers/agents plus red-team review. Required target for constitutional, security-critical, high-risk and major production architecture changes.

## Review output contract

Each review records:

- artifact/commit/work item reviewed;
- role/hats used;
- review independence level;
- findings by severity;
- assumptions challenged;
- tests/evidence requested;
- unresolved questions;
- decision: `APPROVE`, `APPROVE_WITH_FOLLOWUP`, `CHANGES_REQUIRED`, `BLOCKED`.

A critical finding cannot be closed only by changing prose; the reviewer verifies the correction/evidence.

## Severity

- `R1 CRITICAL` — could invalidate truth/security/core architecture or cause severe production failure.
- `R2 MAJOR` — material correctness, reliability, scalability or maintainability issue.
- `R3 MODERATE` — meaningful issue that should be fixed or explicitly tracked.
- `R4 MINOR` — clarity/local quality improvement.

## AI-specific anti-bias rules

1. Do not let the same generated explanation count as both implementation evidence and review evidence.
2. Reviewers should inspect source artifacts/diff/tests, not merely the author's summary.
3. For critical decisions, ask at least one reviewer to assume the proposal is wrong and find why.
4. Include omission search: "what important category did this specification not discuss?"
5. Include duplication search across synonyms and adjacent modules.
6. Include dependency inversion search: "is this component rebuilding a responsibility owned elsewhere?"
7. Include false-confidence search: "what result could look correct while being semantically wrong?"
8. Prefer executable/observable evidence over persuasive narrative.

## Completion rule

A work item cannot claim review complete until all required hats for its risk/artifact class have a recorded outcome and all blocking findings are resolved or explicitly accepted through the appropriate governance path.