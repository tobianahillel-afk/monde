# MONDE Threat Modeling Protocol

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

Security review must be systematic and design-time, not a final scan. MONDE contains acquisition, parsers, browsers, models, multi-source data, potentially sensitive information and eventually multi-tenant access; every material trust-boundary change requires explicit threat modeling.

## Threat-model trigger

Perform or update a threat model when work changes:

- authentication/authorization;
- account/session/secret handling;
- browser/channel acquisition;
- URL fetching/network egress;
- file/document/archive parsing;
- model/tool/plugin execution;
- external callbacks/webhooks;
- tenant/private data;
- caching/derived visibility;
- privileged infrastructure;
- high-risk/sensitive capabilities;
- code/deserialization execution boundaries;
- public APIs or upload surfaces.

## Model structure

For each affected system identify:

1. assets to protect;
2. actors/roles;
3. data flows;
4. trust boundaries;
5. entry points;
6. privileged operations;
7. external dependencies;
8. abuse cases;
9. controls;
10. detection/recovery.

## Threat categories

Review at least:

- spoofing/identity confusion;
- tampering/data poisoning;
- repudiation/audit gaps;
- information disclosure;
- privilege escalation;
- denial/resource exhaustion;
- SSRF/network pivoting;
- path traversal/file parser abuse;
- malicious archives/documents/media;
- prompt injection/tool hijacking through untrusted content;
- dependency/supply-chain compromise;
- secrets/session theft;
- tenant/visibility leakage;
- cache poisoning/cross-scope cache reuse;
- provenance forgery/source impersonation;
- model/data poisoning;
- replay/duplicate/out-of-order event abuse;
- unsafe administrative/operator actions.

## Data poisoning and epistemic security

Security includes protection of MONDE's beliefs, not only infrastructure.

Threats include:
- forged sources;
- coordinated copies appearing independent;
- malicious metadata/timestamps;
- source compromise;
- adversarial documents targeting parsers/models;
- intentional entity-resolution collisions;
- false observations designed to manipulate estimates;
- MONDE output recirculated as independent evidence.

Controls should include provenance, source ancestry, confidence, quarantine, identity verification, anomaly checks and reversible belief updates.

## Browser/acquisition threat boundaries

Acquisition workers should assume every page/channel/file is hostile.

Design controls may include:
- sandboxed workers;
- restricted credentials;
- egress policy;
- download quarantine;
- safe file parsing;
- resource limits;
- browser/profile isolation;
- explicit authenticated scope;
- no trust transfer from page text into agent instructions;
- auditable navigation/actions.

## Threat-to-test traceability

Material threats become `RISK-*` and map to preventive/detective controls plus `TEST-*` verification where practical.

Example:

`RISK-SSRF → URL policy + network sandbox → TEST-SSRF-* → runtime egress telemetry`

## Abuse-case review

For each exposed capability ask:
- How could an authorized feature be misused?
- How could scope/identity be confused?
- How could derived data reveal more than source permission allows?
- How could a malicious source manipulate decisions?
- What happens if an agent follows hostile content instructions?
- What expensive action can be triggered repeatedly?

## Security assumptions

Unproven security premises become `ASM-*`, for example:
- "this source cannot return active content";
- "this connector always enforces tenant scope";
- "this parser is memory safe".

Critical assumptions require verification or compensating controls.

## Verification levels

Depending on risk use:
- static analysis;
- dependency/secret scanning;
- unit/property tests;
- integration boundary tests;
- adversarial fixtures;
- fuzzing;
- authorization matrix tests;
- sandbox/egress tests;
- real-system security validation;
- manual red-team review;
- penetration testing for exposed critical surfaces.

## Findings

Security findings use severity and status, link to affected work/risk/test records and cannot be dismissed only because exploitation was not observed in the happy-path test.

## Release rule

An unresolved critical security finding or unknown critical trust boundary is a non-compensable hard gate. The affected work cannot be `DONE` until resolved, explicitly risk-accepted at the correct authority level, or removed from scope.

## Continuous threat modeling

Threat models are living artifacts. When architecture/data flow/permissions change, update the model and regression tests. Security design history should remain traceable through Git, ADRs and risk records.