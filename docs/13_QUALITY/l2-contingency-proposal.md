# Independent L2 contingency and blocked-resource recovery — proposal

Status: **DRAFT — not accepted, not an approval shortcut**  
Scope: MONDE repository development governance / WORK-0002 / [issue #15](https://github.com/tobianahillel-afk/monde/issues/15)  
Prepared: 2026-10-09  
Normative sources remain `AGENTS.md`, `docs/13_QUALITY/review-council.md`,
`registry/status-machines.yaml` and `registry/acceptance-authority.yaml`.
No assurance rule changes until this proposal receives independent approval.

## Problem and intent

Independent L2 reviews have repeatedly been blocked by exhausted Codex review quota.
An exhausted provider is a **resource availability failure**, not a review decision.
The objective is to continue finding a **legitimate** reviewer without lowering the
level of assurance, fabricating completed review evidence, or bypassing the existing
GitHub exact-head approval gate.

This is one application of a more general development-engine discipline:
**when a task is blocked by unavailable resources, search for equivalent
independently verifiable routes before treating the entire work item as impossible.**

## General blocked-resource procedure

1. Classify the blocker: provider quota, rate limit, provider outage,
   missing entitlement, tool permission, missing data, unmet prerequisite,
   execution environment or material security risk.
2. Record the failed attempt's immutable artifact/commit, time, provider,
   actual error or evidence, impact and **which acceptance obligations remain**.
   Do not label an unavailable resource as a test failure or negative review
   unless a reviewer actually found a defect.
3. Search for a substitute that satisfies the *same* requirements:
   independence, capability, access, security, provenance, cost/limits,
   auditability, exact-head binding and lifecycle evidence.
4. Reuse an already **authorized** substitute first. For a new GitHub App,
   external provider or spending commitment, **request explicit owner action**;
   neither an agent nor a PR comment can silently install it, grant permissions
   or authorize paid usage.
5. Execute only the supported portion of the workflow. Preserve the remaining
   blockers and all security gates; never mark a review, test or WORK item
   complete because a fallback was merely selected.
6. Capture the exact outcome and evidence. If no equivalent route is
   available, remain `IN_REVIEW` / `BLOCKED` as applicable; continue safe
   independent work, but do not resolve protected threads or merge.
7. Do not request the same quota-exhausted provider in a rapid retry loop.
   One controlled retry after a documented reset is reasonable; repeated
   denials are not proof of successful execution.

## L2 alternative matrix (availability must be rechecked before use)

| Route | Suitable use | Required qualification |
| --- | --- | --- |
| **Codex GitHub review** | Primary when quota exists | Actual fresh review on exact HEAD, not a quota reply |
| **CodeRabbit GitHub App** | Candidate independent AI reviewer; public MONDE repository has a possible free-OSS route, subject to provider limits | Owner-installed GitHub App; independent code/context analysis; validate the actual provider review and all required hats |
| **Qodo GitHub App** | Candidate provider with a free developer tier | Owner-installed App; verify current entitlement, scope and individual output |
| **GitHub Copilot code review** | Alternate where an eligible paid Copilot license or organization billing is available | Account entitlement and budget; ensure actual exact-HEAD review |
| **Qualified human reviewer** | Fully independent code/security/governance reviewer | Not PR author; fresh context and accountable GitHub identity; explicit hats, findings and decision |
| **Another authorized model/agent in a fresh context** | Additional falsification when external reviewing can be provisioned | Distinct reviewer context and evidence; must not recycle author reasoning or auto-approve its own output |

Provider availability is **not** evidence of review eligibility. An API response,
GitHub bot comment, generic "no issues" summary or an author's second reasoning
pass is not automatically an L2 `APPROVE` record.

Provider snapshot as of 2026-10-09:
- CodeRabbit states free code reviews for public open-source repositories
  with rate limits: https://kb.coderabbit.ai/articles/8856795235-how-do-i-activate-coderabbit-pro-for-my-open-source-project
- Qodo's GitHub Marketplace listing advertises a free developer offering:
  https://github.com/marketplace/qodo-merge-pro
- GitHub Copilot code review requires eligible paid plan or organization-sponsored
  usage: https://docs.github.com/en/copilot/concepts/agents/code-review
- **Do not recommend consumer Gemini Code Assist on GitHub**: its consumer
  GitHub integration was retired on 2026-07-17:
  https://developers.google.com/gemini-code-assist/docs/deprecations/consumer-code-review

## Proof obligations for every alternate L2

A substitute qualifies only after all checks below:

- **Artifact:** GitHub repository, PR, immutable reviewed commit SHA, base revision,
  exact file/diff scope, requirement revision/digest when acceptance depends on it.
- **Reviewer:** real GitHub/external provider identity and source URL/ID;
  independent fresh context; no author impersonation, sockpuppet or copied
  self-review represented as independent work.
- **Roles:** explicit mandatory hats from the accepted review-council contract;
  roles absent from a provider's output need *additional* eligible independent
  coverage, not a guessed "covered" checkbox.
- **Review contents:** actual code, contracts, tests, prior blocking findings,
  hidden trust boundaries, regression/evidence adequacy and adversarial failure
  cases; no reliance on the author's claims alone.
- **Decision:** recorded `APPROVE`, `APPROVE_WITH_FOLLOWUP`,
  `CHANGES_REQUIRED` or `BLOCKED` with precise evidence. Quota/timeout
  becomes `UNAVAILABLE` operationally and **no review outcome**.
- **Exact-head freshness:** stale reviews on old SHAs do not silently qualify
  a newer candidate. Re-read live HEAD immediately before promotion or merge.
- **Authority:** follow `registry/status-machines.yaml` and
  `registry/acceptance-authority.yaml`. Any requirement-acceptance
  cold-read TEST remains a distinct eligible evidence contract.
- **Merge gate:** an independent narrative L2 and a **trusted non-author
  GitHub exact-head `APPROVED` review** are distinct checks. A bot that
  posts only `COMMENTED` reviews cannot automatically satisfy an
  `APPROVED` requirement; a human/other eligible actor must separately
  satisfy it if the gate demands it.
- **Closed findings:** each prior PR thread remains unresolved until its
  actual corrective evidence was independently examined and the project's
  closure authority permits resolution. Do not batch-resolve solely because a
  new provider produced a favorable summary.

## Immutable reviewer packet

Provide an alternate reviewer with **read-only** input, not broad write tokens:

| Required field | Value or link to provide |
| --- | --- |
| Repo and PR | `tobianahillel-afk/monde` / exact PR number |
| Frozen head | Complete 40-character Git commit SHA |
| Base | Complete 40-character target-base SHA |
| Work and assurance | `WORK-0002` / A3 where applicable |
| Review | Exact `REVIEW-*` lifecycle record and status |
| Requirements | Exact IDs plus normative digests if qualifying acceptance |
| Findings | Live unresolved GitHub review-thread IDs, *complete* set |
| Read-before | `AGENTS.md`, `PROJECT_STATE.md`, active WORK, linked REQ/RISK/TEST and relevant workflows |
| CI | Exact run IDs, job status, coverage, mutation evidence and limitations |
| Hats | All six required WORK-0002 review hats; add any specialized role required by scope |
| Scope exclusions | No WRE, CMDR, other product projects or unintended implementation work |

Sample review instruction:

> Review this exact immutable MONDE PR HEAD independently from a fresh context.
> Read the full diff, all linked contracts and every live material review thread.
> Challenge security, architecture/reuse, V&V, performance/SRE, red-team and
> traceability assumptions. For each material finding include severity, file/line,
> reproduction or concrete adversarial evidence. State exactly which hats were
> exercised. Do not treat green CI or the author's explanation as approval.
> Never approve a changed head without a new exact-head review.

## Separation from the present trusted-root blocker

**REVIEW-0094 is still a negative independent review.** PR #2 cannot be
approved merely because an alternative L2 provider becomes available.

Its P1 findings require a **separately independently approved default-branch
validator/dependency trust root**. A lock file whose SHA exists only in the PR
candidate's history is not an approved base lock; trusted validators executed
from the candidate checkout are not trusted. Track that prerequisite under
[issue #15](https://github.com/tobianahillel-afk/monde/issues/15).

The present proposal neither installs a provider nor activates a bypass path
in workflows. It changes no acceptance policy, GitHub permission, status
machine, required check or external-integration behavior. A subsequent
independent review must accept the operational plan before canonical adoption.
