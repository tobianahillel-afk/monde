# MONDE

> **MONDE — An evidence-grounded, temporal world model for observing, understanding, explaining, forecasting and simulating the world.**

MONDE is a long-term world-intelligence platform whose goal is to reconstruct the state, history, relationships, flows, uncertainty and plausible futures of the real world from heterogeneous evidence.

It combines official datasets, the open web, documents, channels, media, video/audio, geospatial and Earth-observation data, sensors and other authorized observation surfaces into one temporal, evidence-grounded World Model.

MONDE is not a collection of disconnected dashboards. Console, Globe, investigations, forecasts, scenarios, opportunity detection and World Scientist all operate on the same underlying World Model.

## Core epistemic rule

MONDE strictly separates:

- **Observed World** — what sources or sensors actually observed or asserted.
- **Estimated World** — MONDE's reconciled beliefs and probabilistic estimates.
- **Simulated World** — forecasts, scenarios and counterfactuals.

Nothing inferred becomes observed. Nothing important is published without provenance, time semantics, confidence and an explanation path.

## Repository purpose

This repository is the **canonical source of truth for the MONDE project**. It contains product specifications, architecture, capability registries, data/source definitions, model registries, engineering rules, ADRs, roadmap, quality gates and eventually implementation code.

The project is expected to be developed heavily by AI agents. Therefore repository state must be explicit, machine-readable and resumable without relying on chat history.

## Start here

**Do not begin implementation from this README alone.**

1. Read [`docs/00_START_HERE.md`](docs/00_START_HERE.md).
2. Read [`AGENTS.md`](AGENTS.md) before making any change.
3. Check [`PROJECT_STATE.md`](PROJECT_STATE.md) for the current development state.
4. Resolve the active work item and its `read_before`, dependencies and reuse declarations.
5. Read the MONDE Constitution before modifying semantics.

## Repository map

| Area | Purpose |
|---|---|
| `docs/` | Canonical human-readable product, architecture, engineering and governance documentation |
| `registry/` | Machine-readable registries: capabilities, work items, dependencies, progress, sources, models, engines |
| `schemas/` | Canonical schemas and contracts |
| `.github/` | PR/issue workflows and repository process automation |
| `PROJECT_STATE.md` | Fast resume point: current phase, lot, active work, blockers and next actions |
| `AGENTS.md` | Mandatory operating protocol for AI coding agents |

## MONDE engineering constitution — short form

- No fact without source.
- No fact without time.
- No state without validity.
- No inference without confidence.
- No history overwritten.
- Observed, estimated and simulated states remain distinct.
- Entity merges are reversible.
- Critical behavior is tested, observable and reproducible.
- Existing capabilities are reused before new ones are created.
- Every implementation change updates its work item, dependencies, tests and progress state.

See [`docs/09_GOVERNANCE/constitution.md`](docs/09_GOVERNANCE/constitution.md) for the canonical rules.

## Development state

MONDE is currently in **Phase 0 — specification and repository governance**. The immediate objective is to establish a complete, auditable product and engineering specification before substantial implementation begins.

## License

No open-source license is granted by this repository unless an explicit license file is added later.
