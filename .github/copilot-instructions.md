# MONDE — GitHub AI instructions

Treat the repository as the durable source of truth and GitHub as the live control plane.

Before proposing or reviewing a change:

1. Read `AGENTS.md`, `docs/00_START_HERE.md`, and `PROJECT_STATE.md`.
2. Identify the active `WORK-*` and follow its `read_before`, dependencies, scope, assurance, tests, and review plan.
3. Prefer the generated `context-manifest.json` from MONDE Gate when available; expand from `MUST_READ` to `SHOULD_READ` and `ON_DEMAND` only as needed.
4. Search for existing capabilities, requirements, schemas, engines, helpers, ADRs and synonyms before introducing a new concept.
5. Never silently reduce an accepted/active work item's scope or acceptance criteria.
6. Treat `.github/`, `tools/governance/`, `scripts/governance*`, governance schemas, governance docs and quality contracts as meta-governance/root-of-trust changes requiring elevated review.
7. Do not infer merge readiness from committed YAML alone. Re-check the current PR head, checks, reviews and unresolved review threads.
8. Test definitions are durable registry objects; current execution results belong to SHA-bound GitHub checks/artifacts.
9. Preserve MONDE epistemic invariants: Observed ≠ Estimated ≠ Simulated; no source/time/provenance loss; no hidden uncertainty.
10. A green coverage number is not enough: challenge properties, failure modes, mutation survival, security, performance and omitted scope.

Never mark work DONE or recommend merge while any applicable hard gate is unknown, stale or failing.
