# MONDE Research Protocol for Specifications

Status: Accepted  
Canonical: Yes  
Last Updated: 2026-09-10

## Purpose

MONDE specifications will often depend on current external systems, standards, datasets, scientific methods and engineering constraints. AI agents must not silently fill these gaps from uncertain model memory. Research is an explicit phase with recorded questions, sources, dates, evidence and uncertainty.

This protocol applies when external factual verification would materially affect a specification or architectural choice.

## Step 1 — Research questions before browsing

Before searching externally, list the concrete questions that must be resolved.

Examples:
- What authoritative API/data source actually exists?
- What fields/update cadence/license/coverage does it expose?
- What protocol/standard version is current?
- What production constraints does the chosen database/runtime have?
- What benchmark/baseline represents current best practice?
- What failure modes are documented by maintainers/users?
- What historical data is available for backtesting?

Do not browse aimlessly and then build architecture around whatever was easiest to find.

## Step 2 — Source hierarchy

Prefer sources in this order depending on question type:

1. primary official specifications/documentation/standards;
2. source-provider datasets/API documentation;
3. peer-reviewed or authoritative scientific publications;
4. official implementation repositories/release notes;
5. high-quality engineering papers/technical documentation;
6. reputable independent analyses;
7. community reports/issues for failure modes and operational experience.

Community/anecdotal sources may reveal useful problems but should not silently override authoritative semantics.

## Step 3 — Freshness

For modern systems, APIs, laws, datasets, libraries and standards:
- record retrieval/research date;
- verify current version/status;
- distinguish publication date from validity/effective date;
- check deprecations/migrations;
- avoid adopting stale blog posts as current contracts.

## Step 4 — Triangulation

For material claims, seek corroboration or explain why a single authoritative source is sufficient.

Especially triangulate:
- performance claims;
- coverage claims;
- vendor marketing claims;
- causal/scientific claims;
- licensing/access assumptions;
- operational reliability claims.

## Step 5 — Extract facts into structured findings

A research note should distinguish:

- `FACT` — supported by cited/recorded evidence;
- `ASSUMPTION` — plausible but not yet verified;
- `HYPOTHESIS` — candidate explanation/design expectation;
- `DECISION` — choice made by MONDE;
- `OPEN_QUESTION` — unresolved.

Do not let source descriptions become design decisions automatically.

## Step 6 — Research note structure

For substantial research, create a note under `docs/12_RESEARCH/` or linked work artifact containing:

- research objective;
- questions;
- date;
- sources consulted;
- key findings;
- contradictions between sources;
- limitations;
- assumptions created/validated;
- architecture/product implications;
- rejected options;
- follow-up questions;
- evidence/citation links.

Research notes remain non-canonical until findings are promoted into Accepted specifications/ADRs/registries.

## Step 7 — Comparative evaluation

When choosing technology/architecture, compare options against requirements rather than preferences.

Possible dimensions:
- correctness/semantics;
- maturity;
- performance;
- scale;
- operational complexity;
- ecosystem;
- security;
- observability;
- cost;
- lock-in;
- migration/reversibility;
- licensing;
- developer/AI maintainability;
- reproducibility.

A technology does not win because it is fashionable.

## Step 8 — Evidence-to-decision linkage

A durable decision should show:

`research finding → requirement/constraint → option comparison → ADR/decision`

This lets future agents understand whether a decision remains valid when external conditions change.

## Step 9 — Adversarial source review

Ask:
- Could this source be outdated?
- Is this vendor marketing rather than measured evidence?
- Is the benchmark workload representative?
- Is the apparent consensus derived from one original source?
- Is there selection/publication bias?
- Does the claim hold in MONDE's expected scale/geography/domain?

## Step 10 — Prototype when documentation is insufficient

If critical behavior cannot be established from documentation, run a bounded experiment/spike rather than guess.

Examples:
- benchmark actual query shape;
- test real browser behavior;
- parse representative files;
- measure API limits;
- validate a schema against real source payloads.

Record as `EXP-*` where material.

## Research for data sources

For every significant data source investigate:
- authority/operator;
- exact observed semantics;
- coverage/geography;
- temporal range;
- update cadence/latency;
- identifiers/join keys;
- revisions/backfills;
- missingness;
- quality caveats;
- access method;
- rate limits;
- license/usage constraints;
- expected storage/processing cost;
- possible proxy uses and confounders;
- source independence/ancestry.

## Research for models/methods

Investigate:
- target task;
- current baselines;
- representative datasets;
- quality/calibration metrics;
- latency/resource profile;
- robustness/language/domain limits;
- known failure modes;
- reproducibility;
- licensing/deployment constraints.

## Research completeness check

Before promoting research into a canonical specification, ask:

- Did we verify the facts that could materially change the design?
- Did we search for contrary evidence?
- Are current versions/dates explicit?
- Are assumptions separated from evidence?
- Did we examine adjacent systems/functions for reuse?
- Does the decision remain testable/falsifiable?

## Final rule

External research informs MONDE; it does not become MONDE truth until findings are normalized into requirements, assumptions, ADRs or other canonical artifacts through review.