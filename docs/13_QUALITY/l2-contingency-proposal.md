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

## Hard zero-cost rule for MONDE

**Maximum additional spending: €0.** A fallback must remain free for the
public MONDE repository beyond trials, introductory credits or temporary offers.
No subscription, payment card, usage billing, premium AI model/API tokens,
paid runner, paid storage, automatic overage or paid upgrade is permitted.

- **CodeRabbit public-repository plan is first choice**: the provider states
  that GitHub public repositories receive free pull-request reviews indefinitely,
  subject to fair-use/rate limits. Never switch to a paid seat or usage option.
- **Qodo for Open Source is conditional**: its standard trial is not a permanent
  free plan. Use only after the provider confirms this repository qualifies
  for the free OSS program; public visibility alone may not prove eligibility.
- **Copilot Free does not include Copilot code review**. Exclude paid Copilot
  licenses, organization-billed review and subscription upgrades.
- Standard GitHub-hosted Actions runners are free on public repositories,
  but deterministic CI, SAST or an author-controlled model cannot by itself
  supply independent L2 or trusted non-author GitHub APPROVED evidence.
- Self-hosted PR-Agent/open-source tooling is only a €0 route when all model
  inference, hardware, storage, credentials and hosting incur **no new
  charge**; model/API access must not require a paid key. A same-author
  self-review never qualifies as independent L2.
- If a provider exhausts its free quota, record `UNAVAILABLE` and stop.
  Never silently move to trial, pay-as-you-go or paid usage.
- A newly installed GitHub App still requires explicit owner action and
  least-privilege access to the MONDE repository alone.
- MONDE is public, but it has no top-level LICENSE file at this snapshot.
  Do not assert eligibility for every formal OSS sponsorship program without
  checking the vendor's actual terms.
- Provider terms can change: revalidate €0 entitlement before relying on
  an alternative.

**This cost rule changes no review assurance level, requirement-acceptance
authority, branch protection or exact-head merge gate.**

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
4. Reuse an already **authorized, demonstrably €0** substitute first. A new
   GitHub App or external provider needs explicit owner action and permission
   review; paid usage is prohibited, even if technically available.
5. Execute only the supported portion of the workflow. Preserve the remaining
   blockers and all security gates; never mark a review, test or WORK item
   complete because a fallback was merely selected.
6. Capture the exact outcome and evidence. If no equivalent route is
   available, remain `IN_REVIEW` / `BLOCKED` as applicable; continue safe
   independent work, but do not resolve protected threads or merge.
7. Do not request the same quota-exhausted provider in a rapid retry loop.
   One controlled retry after a documented reset is reasonable; repeated
   denials are not proof of successful execution.

## L2 alternatives, in zero-cost priority order

| Route | €0 eligibility and limits | What it can prove |
| --- | --- | --- |
| **Codex GitHub review** | Use only the already available quota at no extra charge; on exhaustion record UNAVAILABLE, never buy credits | Eligible fresh exact-head independent L2 only when an actual review is returned |
| **CodeRabbit public GitHub review** — preferred fallback | Vendor advertises perpetual free PR reviews on public repositories, subject to rate/fair use; owner installs on MONDE only | Independent evidence **if** the actual output covers the full required diff, findings and hats; bot COMMENTED is not an eligible trusted non-author APPROVED |
| **Qodo for Open Source** | €0 only for projects that qualify for its OSS program; ordinary Qodo plans have no permanent free tier | Possible independent supplemental or L2 evidence after provider eligibility and exact-head review are proven |
| **Qualified volunteer reviewer** | €0 if an independent person willingly reviews at no charge | Can satisfy review hats and, if actually authorized/eligible, separate GitHub approval requirements |
| **Public GitHub Actions with open-source scanners** | Standard public runner €0; avoid paid API/model, premium extensions or chargeable services | Automated reproducible verification **only**, not independent L2 by itself |

**Provider terms confirmed 2026-10-09:**
- CodeRabbit official public-repository free plan:
  https://www.coderabbit.ai/pricing
  https://kb.coderabbit.ai/articles/8856795235-how-do-i-activate-coderabbit-pro-for-my-open-source-project
  App: https://github.com/marketplace/coderabbitai
- Qodo has **no permanent standard free tier**, but a separate eligible OSS route:
  https://www.qodo.ai/pricing/
  https://www.qodo.ai/solutions/open-source/
- Copilot Free **does not include GitHub Copilot code review**:
  https://docs.github.com/en/copilot/concepts/agents/code-review
- Standard hosted GitHub Actions runners are free for public repositories:
  https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Consumer Gemini Code Assist GitHub review integration was retired; do not
  present it as a free current alternative:
  https://developers.google.com/gemini-code-assist/docs/deprecations/consumer-code-review

**Execution order:** first verify CodeRabbit €0 public entitlement, obtain
owner installation on just MONDE, then collect a SHA-pinned reviewer report.
If CodeRabbit cannot cover all required hats / findings, supplement with only
another confirmed-€0 independent reviewer. If none qualifies, retain
`IN_REVIEW` / `BLOCKED` instead of inventing an approval.

A generic "no issues" bot comment or author-directed prompt is **not**
automatic L2 approval. A review that does not inspect all relevant open threads
and evidence must record the uncovered obligations. Likewise, an L2 review
does not replace the independent GitHub exact-head APPROVED merge gate.

## Proof obligations for every alternate L2

A substitute qualifies only after all checks below:

- **Artifact:** GitHub repository, PR, immutable reviewed commit SHA, base revision,
  exact file/diff scope, requirement revision/digest when acceptance depends on it.
- **Cost:** exact repository-specific entitlement confirmed at €0 without
  temporary trial, paid API keys, billing, overage or card.
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
