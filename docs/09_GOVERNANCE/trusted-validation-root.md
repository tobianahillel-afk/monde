# MONDE trusted governance validation root — proposed predecessor

Status: **PROPOSED / NOT YET TRUSTED**. Tracks **WORK-0002 / REVIEW-0095**.
This proposal is not an accepted ADR, an independent review approval, or a
merge-authoritative gate. **Do not resolve any of PR #2's material findings
on the strength of this proposal.**

## Why this predecessor exists

On 2026-10-08, independent Codex L2 for REVIEW-0094 exposed two P1 defects:

- `PRRT_kwDOUUI5ts6qkGa6`: the so-called pinned governance dependency
  lock blob was created on candidate PR #2, not an independently accepted
  default-branch history.
- `PRRT_kwDOUUI5ts6qkGbA`: the trusted validation job was invoking
  `tools.governance` code from the candidate checkout.

A SHA-1/SHA-256 digest is an *identity*, not an authority grant.
`pip --require-hashes` checks artifact integrity, not its independent
approval. A candidate-controlled source tree must never validate its own
right to merge.

## Proposed source snapshot and provenance

This predecessor copies the exact `tools/governance/` package,
`.github/scripts/governance_l2_{followup,gate,hardening}.py`, and
`requirements/governance-ci.txt` from PR #2 candidate
`2e2664ca8c9cb4f3eb81ea41a172da1ed7fbaf32`, **for independent
review**, not as a claim that the candidate is an approved authority.

These files become eligible trusted inputs **only after** a distinct
reviewer accepts this predecessor and the exact reviewed tree is merged
into the genuine default-branch history. No self-approval, status replay,
or same-PR authorization is allowed.

Any later change to this trusted source/lock requires another reviewed
default-branch change, rather than changing a candidate's SHA literal.

## Proposed runtime boundary

`.github/workflows/monde-trusted-governance.yml` is deliberately named
**Preflight** and **not** `MONDE / Merge Gate`. Its `pull_request_target`
definition lives on the target branch after the predecessor merges.
It only runs for pull requests targeting `main`.

It uses two disjoint checkouts:

1. `trusted/`: exact event `pull_request.base.sha` of the target repo.
2. `candidate/`: exact event `pull_request.head.sha` of the PR.

The trusted runner installs its Python dependencies from
`trusted/requirements/governance-ci.txt` before it checks out candidate
files. It runs only modules from `trusted/tools/governance`, with
`PYTHONPATH` restricted to the trusted checkout and its reviewed helpers.
The candidate tree is an **untrusted filesystem input**, never a Python
module directory or command source. Both checkouts disable credential
persistence. Job permissions remain read-only.

**Never** switch the working directory or Python module path to the
candidate checkout. Never run candidate `pytest`, mutation-smoke scripts,
shell snippets, package managers, pip installs or Git hooks in this job.

A base-rooted runner should not be treated as a final check before its
GitHub source, actual event behavior, isolation, and exact target-PR
binding have received independent review and real-system proof.

## Non-authoritative limitations and following work

- A `pull_request_target` workflow ordinarily has a base-associated
  Actions run; its green status **does not establish an exact-head
  merge-authoritative required status check**. PR #2's T11/final-gate
  contracts must be amended to bind the approved trusted result to
  the exact candidate HEAD, with fail-closed freshness and no
  candidate-controlled workflow bypass.
- Protecting required checks, branch settings, rulesets and administrative
  settings remains **WORK-0003**. The absence of independently enforced
  branch protections must be called out, not glossed over.
- The copied package is a large trust-sensitive code surface. Independent
  review must audit its imports, subprocess calls, dynamic loading,
  filesystem traversal, data parsing, symlink handling, Git subprocess
  environment, dependency wheels, review provenance, and all reviewed
  validators before any merge or trust promotion.
- Exact same-commit candidate tests are historical *functional* evidence,
  not independent supply-chain approval of the copied bytes.
- The successor on PR #2 must first merge this root predecessor into
  `main`, then integrate the new `main` with a two-parent merge,
  remove candidate-origin lock/source authority, run full regression
  and real-system proof, and obtain a new exact-head independent L2.
- Until then REVIEW-0095 stays open and the **104 unresolved PR #2
  threads remain unresolved**.

## Independent review gates for this predecessor

1. Check the complete diff and provenance from the source PR.
2. Treat every copied executable as untrusted until accepted.
3. Verify the preflight cannot import, run or install candidate-controlled
   Python, dependencies or shell fragments.
4. Test PR-head/base drift, malicious `.pth`/wheel proposals, malicious
   test/config files, unreadable sources, symlink attacks, forked PRs,
   event type changes and stale workflow/required-check authority.
5. Require a separate context/security review and exact reviewed-commit
   evidence before merge.
6. Preserve PR #2's 104 unresolved material threads throughout this
   predecessor's review.
