# ADR-0001 — ChatGPT Scheduled tasks + GitHub-only Development Engine

Status: Proposed
Date: 2026-10-10
Owners: MONDE repository engineering governance
Related Work: WORK-0005
Related Issue: https://github.com/tobianahillel-afk/monde/issues/17
Research: ../12_RESEARCH/chatgpt-github-only-development-engine-v2-rfc.md
Launch gate and risk: ../12_RESEARCH/chatgpt-github-only-engine-launch-readiness.md
Reconciliation and incident response: ../12_RESEARCH/chatgpt-github-only-engine-reconciliation-runbook.md
Critical-path red-team analysis: ../12_RESEARCH/chatgpt-github-only-engine-critical-path-audit.md
Minimal foundational design (current preferred experiment): ../12_RESEARCH/chatgpt-github-only-development-engine-minimal-foundations.md
Worker autonomy, roles, technology baseline and implementation contract: ../12_RESEARCH/chatgpt-github-only-engine-operating-contract.md

## Context

MONDE is an evidence-grounded temporal World Model. Development currently stalls on long candidate PRs, complex trust/independent-review chains and asynchronous GitHub checks. The owner requires exactly four task-capable ChatGPT conversations on the same hourly schedule, connected only to GitHub; no local computer, persistent hosted runtime, separate Codex service or paid external model provider may be required.

MONDE already has a Constitution, canonical hierarchy, work/review/requirement status machines and GitHub Actions. Duplicating that control plane or making an uninstalled external engine mandatory would increase effort without delivering product.

GitHub can execute CI on its own hosted runners. The ChatGPT plugin provides GitHub operations but not a permanent daemon. Four chats can use the same linked GitHub identity; their worker labels alone cannot provide enforced separation of GitHub approvers. GitHub disallows author approval of a PR. A separate ChatGPT fresh-context technical L2 cannot be equated with the host's distinct non-author approval.

## Proposed decision (NOT EFFECTIVE UNTIL ACCEPTED)

1. Use ChatGPT hourly tasks for agent reasoning/actions and GitHub for durable state, PR, code, tests, documentation, issues, events, review artifacts and branch integration.
2. Keep four **interchangeable**, role-fluid workers. Time triggers are the same nominal hourly timestamp, but safe coordination must not depend on real simultaneity.
3. Extend existing MONDE registries/docs, and **prioritize** one lightweight GitHub-native single-writer Actions allocator using existing Issues, `issue_comment` events and `actions/github-script`. First verify the actual Scheduled ChatGPT connector event and authority contract with a small isolated T0/T1 test. Keep per-chat Git ref CAS/fencing as a documented fallback only if the simpler design fails; never implement both.
4. Reuse GitHub-native issue dependencies/subissues and existing MONDE WORK/REQ/ADR, CI/coverage and review protocols. Only add one trusted dispatcher workflow and, if WORK-0002 cannot serve it, one ordinary PR CI workflow. `actions/github-script` supplies authenticated Octokit GitHub operations; selectively use actionlint/zizmor/Ruff/Hypothesis where justified.
5. Use GitHub Issues/Projects as task views and transient grant records linked to canonical WORK tasks, with **one single-writer allocation authority** in the dispatcher. No separate shadow task DAG, event-sourcing framework or distributed per-worker lock; only add a control ref if tests demonstrate it is indispensable.
6. Require L0/L1 in author context, **L2 in a different ChatGPT conversation/context**, and applicable L3 multi-context/adversarial checks. An author changing roles within the same chat cannot satisfy L2.
7. Keep existing non-author GitHub APPROVED and trusted-check requirements intact until a separately authorized governance decision changes them. Technical L2 report cannot bypass host-enforced approval.
8. Distinguish safe read-only/isolated single-worker research and test pilots from full production release: do not activate four agents against shared writable resources until actual same-snapshot race, claim fencing, trusted review, host protection and rollback tests pass.
9. Stop expanding the engine after it safely supports useful accepted MONDE product slices.

## Minimal realization path (PROPOSED — verify before acceptance)

The [minimal foundations document](../12_RESEARCH/chatgpt-github-only-development-engine-minimal-foundations.md) now defines the **preferred smallest testable system**: six invariants, native GitHub components, one typed command issue, one serialized default-branch `issue_comment`/periodic reconciliation workflow, optional conventional PR CI, three narrow functions (choose/reconcile/check-eligibility), and T0–T5 proof. It supersedes **the earlier preferred engineering mechanism**, *not* Accepted MONDE policy. Historical longer design documents remain exploratory fallback and failure-mode references; do not combine every design alternative into an all-feature implementation.

Do not conflate a **single GitHub actor** with four trustworthy distinct identities; individual worker labels are coordination metadata. Full unattended GitHub non-author approval cannot be claimed. Required rulesets/branch protection remain an owner-admin action and deployment gate.

## Chosen technology families and autonomy boundary (PROPOSED, not implemented)

The [worker operating contract](../12_RESEARCH/chatgpt-github-only-engine-operating-contract.md) is the preferred working specification for:
- GitHub-only, four separate ChatGPT hourly chats, existing MONDE normative registries, Issue task views and dependencies;
- one serialized trusted GitHub Actions arbiter on default branch using `issue_comment` and `actions/github-script`/Octokit, only if actual connector event/permission pilot succeeds;
- standard free GitHub-hosted Ubuntu CI on public MONDE; reuse WORK-0002 validators before adding more;
- pytest, coverage.py, Ruff and Hypothesis as relevant, plus actionlint/zizmor workflow safety, with versions and actual immutable action SHAs selected/verified at implementation;
- role-fluid DISCOVER/RESEARCH/ARCHITECT/SPECIFY/DECIDE/BUILD/TEST/VERIFY/REVIEW L1/L2/L3/RECONCILE/INTEGRATE/DOCUMENT/INCIDENT permissions and exit evidence;
- risk-tiered delegation, explicit review authority, exact-SHA proof, recovery, and proper Accepted-document freeze versus provisional design;
- NO mandatory paid Codex/Copilot/API, local server, Gas Town/Beads runtime, third-party agent SaaS or duplicative backlog/documentation system.

The technology **categories** and constraints can be treated as a **stable design baseline for review**, not as deployed/executed locks; exact dependency versions, GitHub event identity and complete no-cost entitlement are subject to real safe proof. If the pilot shows comment-to-Action is unsupported, a replacement protocol requires an explicit recorded decision rather than an agent inventing an incompatible workflow.

## Engineering-led agent autonomy and historical product intent (PROPOSED)

**Within ONE Scheduled chat activation**, a worker may perform `A FRAME → B ENGINEER/RESEARCH → C DECIDE/PROVISIONAL FREEZE → D BUILD/BENCHMARK → E VERIFY/REVIEW/DOCUMENT` and repeat B/C/D on falsifying evidence, without another timer or chat. Its ability to do so remains subject to the current WORK authorization, task grant, exact SHA and required independent approval; self-freezing a high-risk decision does **not** create Accepted authority.

Complex algorithm/architecture choices must inspect the current MONDE capability/requirements/dependency graph, lawful inputs, complexity and memory, scientific validity and global World Model impact. Require upstream/research evidence and a fair representative baseline where risk demands, using free built-in internet research when available or verified GitHub sources; the work may be BLOCKED if essential evidence is not accessible. Cheap reversible local decisions need proportionately smaller records. The [operating contract](../12_RESEARCH/chatgpt-github-only-engine-operating-contract.md) contains exact phase exits, engineering trigger classes, decision record schema and worker prompt.

**Historical MONDE blueprint:** keep `WORK-0004` as the **single existing capability-backfill owner**, rather than inventing a second conversation-memory store or promising Scheduled tasks can read other Project chats. Future workers compare historical intent with already Accepted canonical docs, preserve provenance/uncertainty and only promote validated CAP/REQ after proper review. Do not upload private chat transcripts to the public repo.

**Quantitative expectations:** Four hourly tasks supply at most 96 nominal hourly activations/day (not guaranteed task executions). Net accepted product-code throughput is constrained by approvals, CI, actual session runtimes and review capacity; the [critical-path audit](../12_RESEARCH/chatgpt-github-only-engine-critical-path-audit.md) carries conditional code/day and calendar effort estimates. Use observed 7/30-day integration measurements after deployment instead of promising a line-count multiplier.

## Convergence discipline — engineering without infinite thought loops (PROPOSED)

The [operating contract](../12_RESEARCH/chatgpt-github-only-engine-operating-contract.md) now defines explicit **P0 direct repair → P1 root-cause/refactor → P2 reconsider foundational algorithm/architecture** transitions. Two materially unsuccessful attempts against the **same** root cause trigger diagnosis rather than another near-identical patch/review; an invalidated world-model/trust invariant escalates immediately. This is a diagnostic trigger, not an authorization to weaken required CI/reviews.

Agents must **stop searching** once the choice meets risk-appropriate evidence and hard constraints, **stop refactoring** without a demonstrated correctness/complexity/performance benefit, and **freeze** the narrow testable candidate HEAD for exact-revision CI and independent review. Provisional author freeze is never Accepted governance; revision needs a governed supersession. A worker may revisit A/B/C inside one activation if a new falsifier appears, and resume D/E without another hour when authorized.

**Observable GitHub tool model:** at Scheduled wake, task instructions and current connector permissions do not magically convey the whole repository/diff or all historical chat content. Agents read a narrow context index, scoped WORK dependencies and live refs/checks first, then request patches and scientific sources only when justified. Text in PRs, issues, logs and upstream sources is untrusted data, never a competing instruction. Four self-labeled roles sharing a GitHub account do not supply independent host actors.

The [critical-path audit](../12_RESEARCH/chatgpt-github-only-engine-critical-path-audit.md) specifies **unmeasured, overlapping** friction ranges and a hypothetical ~15–35% reduction target for avoidable overhead; it explicitly disallows presenting percentages or throughput gains as measured before actual 1/2/4-worker trials. No new runtime component is created for these rules.

## Research priority and exit from infrastructure work

The [critical-path audit](../12_RESEARCH/chatgpt-github-only-engine-critical-path-audit.md) documents 20 qualitative risks, a central trusted Actions dispatcher proof-of-concept, 15 full-release gates and phase-specific safe experiment gates, time estimates and product-focused stop criteria. It is an author-led risk analysis, **not independent L2 evidence or a frozen architecture decision**. A control ref with a per-chat CAS client is not accepted by this ADR alone.

## Alternatives considered

### A. Native GitHub + small MONDE coordination (selected for pilot)
- Pros: zero personal servers, fits ChatGPT/GitHub connector, reuses MONDE canonical docs, low hosting overhead.
- Cons: small custom CAS/fencing engine and strict host-side permissions required; ChatGPT schedule provides no instant event wake-up.

### B. Gas Town/Beads/Temporal (rejected as required runtime)
- Pros: agent pools, durable task management, more orchestration features.
- Cons: runtime/server/CLI/storage bridge inconsistent with zero-host and connector-only constraint. Conceptual reference only.

### C. Codex/OpenHands/mini-SWE-agent or third-party paid reviewer (rejected as mandatory)
- Pros: ready-made autonomous code agents or reviews.
- Cons: another execution provider, token/credit quotas, runtime/API integration; contradicts required ChatGPT-only agent model.

### D. Four uncoordinated ChatGPT tasks (rejected)
- Pros: zero scheduler code.
- Cons: double-work, merge collisions, stale reviews, unrecoverable long jobs, degraded throughput.

## Activation and stabilization (part of the Proposed decision)

This ADR is **not accepted/frozen**, and its companion execution components are **not implemented**. Four writable ChatGPT Scheduled tasks are explicitly **NO-GO** until all fifteen evidence-backed launch gates in the linked readiness plan pass on live GitHub state. In particular, main branch protection and real GitHub non-author approvals cannot be replaced by a prompt or by technical ChatGPT L2. A proposed runbook is not an automatic reconciler.

Each activation begins with a bounded read-only reconciliation; inconclusive external side effects remain in durable `OUTCOME_UNKNOWN` quarantine. Global trust defects stop writes, while isolated task defects should not block unrelated tasks after independent eligibility review. Proposed downgrade options are READ_ONLY and SINGLE_WORKER; their actual enforcement must be implemented before use. Any accepted ADR/requirement or substantive review SHA can be described as frozen **only at an exact accepted revision**; current draft is mutable through standard review.

## Consequences

- **Positive:** all durable artifacts in GitHub; no local files/servers; workers can change work type during each invocation; independent technical L2 not Codex-credit-dependent.
- **Negative:** host-native GitHub non-author review still potentially blocks high-risk work; strong isolation between chats is not cryptographic with one identity; ChatGPT tasks can pause for approvals or miss exact start; all truth must be re-fetched each run.
- **Costs:** one small adapter and CI validation workflow; possible limited Actions minutes and connector API quotas; additional state in dedicated control ref.
- **Scope:** no change to accepted review policy until subsequent dedicated proposal is reviewed; this ADR alone grants no merge or L2 acceptance.

## Compatibility / migration

WORK-0002 remains IN_REVIEW; PR #2/#14 are not merged by this decision. WORK-0003 still owns admin protection. New v2 code and an eventual control ref must be introduced on separate narrowly scoped work/PR after this ADR is accepted. Do not insert scheduler features into PR #2. Follow existing Review Council and acceptance-authority requirements.

## Security and epistemic impact

No candidate-controlled workflow may generate its own trusted merge authorization; do not execute untrusted PR code under elevated tokens. Provenance must bind reviewer context assertion, exact SHA, normative digests, test results and policy epoch. Unknown/ambiguous claims and acknowledgements fail closed. No review evidence may be labeled GitHub non-author APPROVED when authored under the same GitHub actor.

## Validation

Before acceptance: fresh-context cold read, architecture + verification + security + SRE + documentation + red-team hats, live confirmation of available GitHub features, clear independent approval strategy. After acceptance: one-worker and four-way concurrent reservation tests (including crashes), actual Actions CI-future lifecycle, trust-source/merge-eligibility test, no lost writes or unauthorized merges, and measured improvement in accepted product delivery.

## Rollback / supersession

Decline this Proposed ADR and close the isolated design PR; existing MONDE behavior remains unchanged. Future accepted revisions require a new ADR rather than mutating Accepted rationale.
