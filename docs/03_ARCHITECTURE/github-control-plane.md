# GitHub Control Plane

Status: Accepted  
Canonical: Yes

Git is MONDE's durable design and intent store. GitHub is the live control plane for pull-request state, checks, review threads, security results and merge eligibility. Neither replaces the other.

## Root-of-trust model

A change is merge-eligible only when the stable `MONDE / Merge Gate` succeeds on the exact pull-request HEAD. Repository YAML must never claim that a historical run proves a later SHA.

Meta-governance paths (`.github/`, `tools/governance/`, `schemas/registry/`, governance scripts) are A3/A4-sensitive. Changes to them require explicit tracked work and stronger review because a pull request must not silently weaken the mechanism that judges it.

A meta-governance change is not authorized merely because some A3/A4 work item also changed. The active changed work item must explicitly cover every sensitive path through `affected_paths`. Exact file declarations and trailing-slash directory prefixes are supported. A terminal or unrelated work item cannot authorize the change.

## CI lanes

The control plane separates deterministic governance, dependency review, CodeQL and a final live-state gate. The final gate is always present; internal lanes may be conditional. Required workflows must not disappear through path filtering.

The live gate verifies the expected HEAD, open/mergeable state and unresolved review threads. Draft pull requests defer live merge eligibility while still executing deterministic validation.

## Ordered-change validation

For pull requests, governance must reason about the actual ordered commit sequence as well as the final `base..head` tree. Candidate paths are the union of files touched across each adjacent commit pair, so an invalid intermediate transition cannot disappear simply because a later commit restores the original endpoint contents.

Review requirements are themselves part of the semantic work contract. Changing required hats or independence after a review makes that review stale. Purely administrative additions such as recording a completed review may remain freshness-neutral when they do not alter the reviewed obligations.

## Secret-history rule

Until squash-only merge is enforced by repository policy, secret detection must cover the PR commit range, not only the final checkout. A high-confidence credential introduced in an intermediate commit and removed later is still a governance failure because that commit may remain reachable under other merge strategies. HEAD scanning remains useful, but it is not sufficient by itself.

## Supply-chain rules

Third-party GitHub Actions use immutable full commit SHAs. Docker actions use SHA-256 digests. Governance Python dependencies are exact-version and artifact-hash locked. Checkout credentials are not persisted and workflow permissions use least privilege.

## Evidence model

`TEST-*` and `REVIEW-*` records define durable verification/review obligations. GitHub check runs, artifacts and review threads are executions of those obligations tied to a SHA. Do not create an infinite evidence loop by rewriting a registry record after every run merely to record the latest run number.

CI should emit machine-readable artifacts such as coverage, governance findings, transition findings, context manifests and live-gate results. GitHub is the source of truth for the current execution state.

## Review semantics

Review independence is ordered: L0 < L1 < L2 < L3. A work item declaring `L3` or `L3_TARGET` requires evidence at L3; an L2 review cannot satisfy it. The canonical approving outcomes are `APPROVE` and `APPROVE_WITH_FOLLOWUP`. Transitional legacy spellings may be accepted only for backward compatibility and must not replace the canonical vocabulary in new records.

## Merge policy target

WORK-0003 must configure, where the account/plan supports it: pull-request-only changes to `main`, required `MONDE / Merge Gate`, conversation resolution, no force-push/deletion, intentional visibility, secret/dependency/code scanning, and a single canonical merge strategy (squash preferred for agent-generated development history).

## Future GitHub facilities

Use reusable workflows as suites expand; merge queue only when parallelism justifies it; environments and OIDC for deployments; artifact attestations/SBOM for distributable artifacts; and agentic workflows only for non-deterministic assistance such as triage/research—not as the sole constitutional PASS/FAIL authority.
