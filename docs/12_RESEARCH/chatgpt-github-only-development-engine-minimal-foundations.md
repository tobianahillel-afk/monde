# MONDE — Minimal development operating model (GitHub-native)

Status: PROPOSED — design cut, not deployed, not approved, not an L2 review
Date: 2026-10-11
Scope: WORK-0005 / ADR-0001 / draft PR #18
Constraint: four ChatGPT Scheduled tasks + connected GitHub plugin + GitHub-hosted Actions; **no local machine, external daemon or paid external AI reviewer**.

> **One-sentence architecture:** preserve MONDE's existing normative WORK/REQ/ADR/Review system, use GitHub Issues as operational task cards, one trusted `issue_comment`-driven GitHub Actions arbiter for *mutually exclusive* assignment and basic reconciliation, branches/PRs for actual implementation, and native GitHub Actions/branch protection for tests and integration. ChatGPT does the reasoning and coding, Actions does only deterministic bookkeeping/testing.

## 0. Six non-negotiable invariants (short enough for every worker)

**I1. One authority per fact.** Accepted MONDE registers/ADRs on main own normative meaning, requirements and WORK lifecycle. GitHub refs/PR/Actions own current code, CI and review facts. One serialized GitHub Actions controller owns transient task grants. Issue labels/comments are *operational projections*, not competing WORK status machines.

**I2. No two workers own conflicting changes at once.** Every scoped task declares affected files and semantic/contract resources. One arbitrated grant per conflicting resource. Workers write on task-specific branches, never `main`. A branch commit can exist after a lease expires, but an old attempt is never allowed to satisfy merge eligibility.

**I3. No false acceptance.** Exact-head qualifying CI, required review policy, current normative digest and GitHub host authorization must be verified before merge. Same-chat hat switch only L1; separate ChatGPT conversation/context can give context-attested technical L2, not an independent GitHub-account non-author APPROVED review. Current required non-author review is a hard, unresolved blocker for fully unattended A3/A4 completion.

**I4. Recover from GitHub alone.** Each run starts by reading authoritative live state and reconciling stale/pending grants and GitHub checks. Timeout/lost mutation reply → inspect exact remote effect first, never blindly repeat. Ambiguous external effect → isolated quarantine. No ChatGPT memory or wall-clock simultaneous-start assumption.

**I5. Risk-tiered work.** Small work gets small scope/read-before and appropriate existing DoD requirements; foundation/auth/policy/world semantics get more extensive review. No new constitutional downgrade: risk-tiering must be approved as an explicit change before differing from current Accepted gate rules.

**I6. Optimize MONDE, not the engine.** Build a minimum safe end-to-end path, measure accepted product work/week and review lead time, then stop adding orchestration features without measured gain.

## 1. Reuse map — do not install a second platform

| Need | Already solved by | What MONDE would add |
|---|---|---|
| Spec, domain semantics, decisions | Existing `docs/`, `registry/`, AGENTS and templates | Nothing new; optional small Spec Kit checklist phrases, **not** `specify init` or a new constitution |
| User-visible task cards / dependency relations | GitHub Issues, sub-issues, blocking dependencies | Link each scoped issue to one canonical WORK/task and acceptance criteria |
| Allocation and collision avoidance | GitHub Actions concurrency + `actions/github-script` (Octokit API) | **Small custom `arbitrate(request,snapshot)`**: choose compatible task, grant/fail, one idempotency ID |
| Recovery / delayed CI | Live GitHub issue comments, PRs, refs, check runs, workflow runs | **Small custom `reconcile(snapshot)`**: expire grants carefully, mark blocked/unknown, refresh candidates |
| Development isolation | Git branches/PRs and GitHub plugin create/update/commit | Branch naming + a small permissible write-set check |
| L0/L1/L2 and review evidence | Existing Review Council, GitHub PR reviews/comments | One short, exact-SHA review packet; L2 from a truly different chat |
| Tests/security | Native GitHub Actions, current `monde-stale-green-bootstrap.yml`, standard open-source validators | Small trusted `monde-dev-ci.yml` only if existing WORK-0002 integration doesn't already provide tests; add actionlint/zizmor/Ruff as needed |
| Enforcement | Native GitHub branch protections/rulesets | Admin WORK-0003 configuration, proven required check source, no force/delete; **cannot be enforced just by prompts** |
| Human dashboard | GitHub Issues filters and Projects | Optional filtered view, never a custom frontend |

Official references: https://github.com/actions/github-script ; https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows ; https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax ; https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies .

**Explicitly not in v2:** Gas Town, Beads/Dolt, Temporal, OpenHands, mini-SWE-agent, Redis, a generic event-sourcing framework, full distributed CAS client per chat, new dashboard, universal agent SDK, second truth registry, duplicate spec tree, Codex credit dependency, paid third-party AI reviews.

## 2. Minimal runtime: only two proposed GitHub workflows

1. **`monde-dev-dispatch.yml`**, trusted, placed on `main` only via approved integration:
   - triggered by typed `issue_comment: created` on **one designated non-PR command issue** (optionally `schedule` for reconciliation sweep; delayed trigger is acceptable). A comment from the GitHub-connected ChatGPT is the proposed request channel, **not proved until live test**.
   - workflow-level shared `concurrency.group: monde-dev-dispatch`, `queue: max`, `cancel-in-progress: false`; no exact FIFO assumption, handle queue saturation.
   - minimal `GITHUB_TOKEN` permissions `contents: read, issues: write`; NEVER `contents: write`, PR merge, Actions admin, secrets access or privileged checkout of untrusted PR code.
   - parse one **structured strict command**, fixed allowlisted issue/actor, validated worker ID W1..W4, request ID and work/task ID; *GitHub actor is the only authenticated principal*, W1..W4 are coordination labels and NOT identity isolation. Ignore injected prompts. Do not evaluate issue text as JavaScript/shell.
   - read canonical task readiness/read-before, open grants, declared file + semantic resource conflicts and real GH state; grant at most one owner per resource. Record request idempotently in immutable issue comment result with attempt ID/epoch/lease and link to work; check resulting remote effect.
   - on `schedule`, re-evaluate missed/unknown requests and reconcile check/PR facts. The runner is **not** an AI fifth worker and cannot awaken ChatGPT on demand.
2. **`monde-dev-ci.yml`**, conventional `pull_request` tests with required-check metadata and exact SHA; first determine whether existing WORK-0002 CI can be reused instead of introducing even this workflow. Limit token permissions, ensure trusted job names and no candidate-owned privileged scripts.

This is the complete intended control plane. The controller can use `actions/github-script` and a small pure helper, with test fixtures on GitHub runners. No external server and no ChatGPT API key.

**Critical exception:** `issue_comment`-triggered workflow must already exist on default branch to run; a workflow authored only in draft PR #18 is not a deployed dispatcher. GitHub's built-in `GITHUB_TOKEN` suppresses many recursive triggers; replies from the Action should only be read by future ChatGPT invocations, not treated as triggers for new Actions.

## 3. Two or three small custom functions only

- `choose(snapshot,request)`: deterministic eligibility + resource exclusion + score; no stateful ML planner, no genetic optimizer. Bias toward completing `IN_REVIEW`/blocked integration before opening new WIP. Initial WIP cap: 2 feature writers, 1 integration candidate, 1 trust-root writer.
- `reconcile(snapshot)`: idempotency/dedupe, user-visible grant truth, CI/head/review freshness, orphan/expired recovery, unknown effect quarantine. Return structured actions, not unbounded actions.
- `check_eligibility(pr,policy)`: narrow protected-head evidence and non-author approval gate; **the actual protection must be enforced by GitHub**, not trusted solely because this function says PASS. This function might remain a read-only report if existing WORK-0002 gates fully cover it.

Keep scripts in a tiny `.github/scripts/monde-dev/` directory **only in a separately authorized implementation WORK**. Script LOC target is a budget hypothesis, not a security ceiling. No new database, queue engine or custom state machine unless a test proves native artifacts insufficient.

## 4. One simple task contract, not a second sprawling schema

Human/ChatGPT-readable task, on one GitHub issue linked to canonical WORK:
```yaml
work: WORK-XXXX
task: Tn
goal: "One observable deliverable"
depends_on: ["WORK-YYYY/Tm"]
write_resources: ["src/module.py", "contract:EvidenceV1"]
done_when: ["targeted tests pass", "required review is valid"]
base_sha: "<observed git commit SHA>"
```
Operational grant is separate: `request_id, worker_label, task, attempt_id, epoch, lease, resource_set, status, evidence_refs`. Never duplicate WORK's `DONE` authority in issue labels.

Simplified operational phases are: **AVAILABLE → OWNED → REVIEWABLE → CLOSED**, with **BLOCKED/UNKNOWN** exceptions. `OWNED` does not mean code merged, `REVIEWABLE` does not mean approved, and `CLOSED` should reflect proven downstream acceptance. Do not redefine accepted registry status machines without review.

## 5. One worker execution, continuously useful

1. Read current `main`, AGENTS, WORK/task scope, claims/PR checks and latest issue arbitration outcomes; reconcile before any mutation.
2. If holding a valid grant, resume. Otherwise submit one typed claim request. If result is not yet available, do read-only eligible research/review preparation; no conflicting writes.
3. On grant, use a task branch and make the smallest reviewable change; update only normative artifacts actually affected. Add targeted tests and publish PR/review packet.
4. When CI is pending, checkpoint exact HEAD and continue immediately with another compatible *authorized* task if the invocation remains active.
5. Independent W2/W3/W4 can carry out L2 technical cold-read on the immutable SHA; the same author chat swapping hats cannot. Native GitHub different-account approval remains separate.
6. Mark actual completion only from GitHub proof; report one concise handover comment, not a new source commit merely to copy a green status.
7. If no grant/review capacity exists, return a truthful blocker; do not invent work to keep four agents busy.

Four tasks use same nominal `:00` hour; no time offsets are used as locks. They do not run continuously; an event triggered during a finished ChatGPT task becomes visible at its next scheduled activation.

## 6. Failure modes must be covered, but not by a giant framework

| Failure | Minimal safe response |
|---|---|
| Two simultaneous claims | Serialized arbiter, one grant; deterministic idempotency ID |
| Event lost / queue at max | Next periodic scan discovers unmet request; retry safely if no grant |
| Action did something but response lost | Re-fetch exact comments/ref/PR before retry, quarantine ambiguous outcome |
| ChatGPT starts late / misses run | Use live GitHub state and resume, never assume hourly presence |
| CI pending longer than chat | Check exact SHA/run attempt next run; no false green |
| Expired worker resumes old branch | May preserve branch but may NOT merge stale attempt; host gating required |
| Same actor fakes L2 or command W2 | Treat as context-attested only, not authenticated different GitHub identity |
| Required native non-author approval absent | Block relevant merge and focus other eligible work |
| Main unprotected / trusted CI missing | **No unattended integration**; read-only/sandbox until fixed |
| Malicious issue body/PR code | Never execute untrusted command as code; low-token permissions |
| Large irrelevant docs/status rewrite | Narrow WORK scope, single normative authority, defer projections |

## 7. Reality checks before selecting this architecture

**Test T0 — actual ChatGPT connector authorization:** Can a scheduled ChatGPT worker read the repo, post a comment on a designated issue, create a scoped branch/PR, and fetch check results without interactive approval? Observe, don't assume.

**Test T1 — event delivery:** Does a real connector-originated issue comment trigger a workflow on `main` with the expected authenticated actor? Reconcile when absent or delayed.

**Test T2 — four-way claim:** Four same-snapshot requests, two conflicting resources, duplicate request IDs, one interrupted Action. Zero conflicting grants after reconciliation.

**Test T3 — blocked integration:** Old head, fake green, missing non-author approval, unprotected main and stale grant all result in no automated merge.

**Test T4 — resumed progress:** Skip an entire ChatGPT hourly slot while CI completes, then prove the next worker resumes without chat memory or source commits.

**Test T5 — one product slice:** A real tiny MONDE work item is specified, coded, CI tested, independently reviewed under applicable policy and merged with legitimate GitHub authority.

**Stop/go:** If T0 or T1 fails, do not deploy the Actions-comment dispatcher. Compare the former per-worker Git ref CAS option or a strictly sequential single-worker mode, not yet another platform. Full four-writer launch still requires the hard gates in [launch readiness](chatgpt-github-only-engine-launch-readiness.md).

## 8. Time budget / scope freeze

The **smallest proof** (T0 + T1 + typed request/reply + synthetic task) is an indicative **4–12 focused engineering hours**, excluding GitHub approval/setup and ChatGPT scheduling. A carefully bounded deterministic allocation/recovery pilot adds **~12–35 h**; independent native approval and existing WORK-0002/0003 debts are outside this budget and may block real production indefinitely. These are planning guesses, not observed runtime metrics or committed deadlines.

Do not build the entire distributed framework based on hypothetical failures. Handle only API/CI events and recovery states that actually appear in the pilot; preserve hard trust/approval invariants. Once the first legitimate MONDE product slice is integrated, prioritize product throughput over further scheduler features.

## 9. Which existing tools actually belong in the small stack?

**Core mandatory reuse:** GitHub Issues native dependencies/subissues, PR/check runs, GitHub Actions concurrency, `actions/github-script` Octokit, current work/ADR registers, GitHub branch rulesets. **Quality on demand:** existing WORK-0002 validator, actionlint and zizmor for workflow risk, Ruff for actual Python source, Hypothesis only for race/property tests. **Not a runtime:** Spec Kit; use its specification/bug-fix/idea assessment *ideas* only and never initialize a competing project tree.

**Not yet deployable:** This document is a proposal within draft PR #18. No arbitration workflow, trusted queue, scheduled ChatGPT task, enforceable claim or L2 non-author identity has been installed by it.

External references:
- https://github.com/actions/github-script
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/actions/concepts/security/github_token
- https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies
- https://github.com/github/spec-kit
