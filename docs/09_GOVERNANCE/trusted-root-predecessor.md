# Trusted executable provenance predecessor (WORK-0002)

**Status: CANDIDATE / NOT ACCEPTED.** This is an independent default-branch predecessor proposal for the two critical REVIEW-0094 findings, not an accepted security gate.

## Trust model

On `pull_request_target`, GitHub starts the workflow from the pull request's **base/default branch**. The trusted job checks out **only** that exact base SHA. It never checks out, imports, or executes candidate code. Using a read-only GitHub token, it compares the complete protected executable/source set at the current PR head against `registry/trust/approved-governance-v1.json` from that approved base checkout. It also requires the candidate's trust-root files to be byte-identical to base.

The manifest currently proposes **161 exact Git blob identities** (SHA + mode), including `requirements/governance-ci.txt`, all governance validators, bootstrap scripts, workflow definitions, and other project-owned executable/configuration files. New, missing, changed or symlinked protected executables fail closed. Documentation and mutable governance registry data remain untrusted inputs, not executable authority.

The dependency-lock blob was originally introduced on PR #2. Its inclusion in this predecessor **does not make it trustworthy by itself**. Only a separately authorized, meaningful, fresh independent review of this predecessor and its pinned source, followed by guarded merge into `main`, can establish that approval provenance. This same requirement applies to every approved validator hash: reviewers must inspect source semantics, not merely compare digests.

## Limits and further integration

The trusted attestation workflow itself is read-only and does **not** yet establish an enforceable branch-protection rule or an independent head-commit required check; these remain subject to WORK-0003/reviewed control-plane design.

REVIEW-0095 must ensure the actual trusted validator execution comes from an approved default-branch source tree, or an exact content-identical verified source with an unbypassable approved guard. It must not execute the candidate's validators as authority merely because a candidate-owned workflow says they are trusted.

When legitimate protected code changes, the base manifest must be independently re-reviewed/updated before the candidate can obtain trusted attestation. The candidate may change ordinary registry data without changing executable code.

No PR #2 review thread or risk is considered resolved by creating this predecessor.
