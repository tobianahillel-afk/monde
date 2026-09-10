# GitHub Control Plane

Status: Accepted  
Canonical: Yes

Git is MONDE's durable design and intent store. GitHub is the live control plane for pull-request state, checks, review threads, security results and merge eligibility. Neither replaces the other.

## Root-of-trust model

A change is merge-eligible only when the stable `MONDE / Merge Gate` succeeds on the exact pull-request HEAD. Repository YAML must never claim that a historical run proves a later SHA.

Meta-governance paths (`.github/`, `tools/governance/`, `schemas/registry/`, governance scripts) are A3/A4-sensitive. Changes to them require explicit tracked work and stronger review because a pull request must not silently weaken the mechanism that judges it.

## CI lanes

The control plane separates deterministic governance, dependency review, CodeQL and a final live-state gate. The final gate is always present; internal lanes may be conditional. Required workflows must not disappear through path filtering.

The live gate verifies the expected HEAD, open/mergeable state and unresolved review threads. Draft pull requests defer live merge eligibility while still executing deterministic validation.

## Supply-chain rules

Third-party GitHub Actions use immutable full commit SHAs. Docker actions use SHA-256 digests. Governance Python dependencies are exact-version and artifact-hash locked. Checkout credentials are not persisted and workflow permissions use least privilege.

## Evidence model

`TEST-*` and `REVIEW-*` records define durable verification/review obligations. GitHub check runs, artifacts and review threads are executions of those obligations tied to a SHA. Do not create an infinite evidence loop by rewriting a registry record after every run merely to record the latest run number.

CI should emit machine-readable artifacts such as coverage, governance findings, transition findings, context manifests and live-gate results. GitHub is the source of truth for the current execution state.

## Merge policy target

WORK-0003 must configure, where the account/plan supports it: pull-request-only changes to `main`, required `MONDE / Merge Gate`, conversation resolution, no force-push/deletion, intentional visibility, secret/dependency/code scanning, and a single canonical merge strategy (squash preferred for agent-generated development history).

## Future GitHub facilities

Use reusable workflows as suites expand; merge queue only when parallelism justifies it; environments and OIDC for deployments; artifact attestations/SBOM for distributable artifacts; and agentic workflows only for non-deterministic assistance such as triage/research—not as the sole constitutional PASS/FAIL authority.
