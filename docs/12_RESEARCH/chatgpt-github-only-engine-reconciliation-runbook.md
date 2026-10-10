# MONDE Development Engine v2 — Reconciliation and Recovery Runbook

Status: Proposed / **NOT DEPLOYED**
Date: 2026-10-10
Owner: WORK-0005 (design); future separately approved implementation work item
Related: [full RFC](chatgpt-github-only-development-engine-v2-rfc.md), [readiness gate](chatgpt-github-only-engine-launch-readiness.md), [ADR-0001](../11_ADR/ADR-0001-chatgpt-github-only-development-engine.md)
Scope: GitHub + ChatGPT Scheduled tasks only. No local process, no Codex quota, no server, no event bus outside GitHub.

> IMPORTANT: This runbook is a **specification**. No executable reconciler, trusted event ref, fencing validator, automatic monitor, release switch or worker handoff has been deployed. Do not configure four writable tasks on the assumption that these mechanisms already exist.

## 1. Why a reconciler is mandatory

A ChatGPT worker is a bounded, possibly delayed or interrupted execution. Its last API request can succeed even when the chat does not receive the response. A GitHub Actions check may finish after the chat has ended. A former task owner may reappear after its claim is reassigned. Several chats can read the same snapshot. Old PR reviews may apply only to a previous commit.

**Reconciliation is mandatory before every new claim and after every uncertain side-effect.** No wall-clock offset between the four hourly triggers is treated as mutual exclusion. No dependence on one chat remembering what another chat did.

Reconciliation is NOT automatic code until separately implemented and tested. GitHub Actions cannot spontaneously wake an existing ChatGPT task; the next scheduled invocation must observe pending events, or a *trusted* GitHub-hosted workflow may perform limited non-AI read-only audits.

## Recommended MINIMAL implementation, before any fallback control-ref ledger

The selected experiment uses **one trusted serialized GitHub Actions arbiter** and GitHub Issues grant/result records, plus live GitHub API observations of PR/CI/check/review. No dedicated control ref, per-chat event-sourcing framework, three parallel status machines, or heavy mutation outbox is a default requirement. The following more elaborate schema/CAS sections are **defense-in-depth fallback designs only**; do not implement them without a failed minimal experiment and reviewed scope. The coordinator tracks only `AVAILABLE/OWNED/REVIEWABLE/CLOSED`, and `BLOCKED/UNKNOWN` exceptions, alongside existing GitHub IDs/HEAD. The existing WORK status machine remains normative.

**Practical minimal reconciliation**: at each ChatGPT activation, fetch current HEAD/grant/branch/PR/checks/reviews and discover outstanding run futures. If CI/review is still active **and the ChatGPT invocation itself is ongoing**, leave the candidate HEAD frozen, do other authorized non-conflicting work, recheck after real elapsed work or genuine wait, and process terminal exact-head outcomes immediately. No pending CI/review alone ends an active invocation. The continuation policy lives **only** in [Operating Contract §7A](chatgpt-github-only-engine-operating-contract.md). If true runtime/tool limits stop this session, checkpoint `repo/PR/sha/run_id/attempt/status/next_action` and reconcile on next hourly invocation. Never fake sleep or claim a guarantee of 5–30+ minute uninterrupted ChatGPT execution.

Unknown GitHub write outcome must be read back before replay, even in the minimal design. Introduce a durable outbox only for operations shown by a real failure-injection test to need it; avoid making every documentation edit a transaction.

## 2. Sources of truth and consistency hierarchy

| Layer | Authority | Mutable by |
|---|---|---|
| Constitutional requirements and accepted architecture | Accepted `main` docs/ADRs/registry | Existing governed PR workflow only |
| Current HEAD, PRs, branch refs, Actions/checks, reviews, workflow attempts | Live GitHub REST/GraphQL | GitHub itself and authorized contributors |
| Current exclusive transient grants/attempt IDs | **Proposed** trusted GitHub Actions arbiter + durable GitHub Issue results | Serialized authorized controller after live event/permission testing |
| Proposed RFC and planning | WORK-0005 branch, PR #18 | Scope-controlled authors; noncanonical |
| Chat history / message | No authoritative lifecycle standing | Worker only |

A work item can be PROPOSED while planning content exists. An author's claim that CI passed, a GitHub Issue label, a checked box or a past saved handover can never override the live HEAD+check+review state.

## 3. Proposed state model (separate from existing WORK vocabulary)

**Historical fallback detailed task state — NOT the selected minimal implementation:** `ELIGIBLE, CLAIMED, WORKING, CHECKPOINTED, CI_PENDING, CI_FAILED, REVIEW_READY, L2_PENDING, READY_TO_INTEGRATE, INTEGRATING, INTEGRATED, BLOCKED, QUARANTINED, OUTCOME_UNKNOWN, ABANDONED`.
**Run state:** `STARTED, OBSERVING, CLAIMED, MUTATION_PENDING, CHECKPOINTED, COMPLETED, INTERRUPTED, UNKNOWN`.
**Integration state:** `NO_PERMISSION, CANDIDATE, GATE_PENDING, HOST_APPROVED, MERGE_ATTEMPT_PENDING, MERGED, REVALIDATE`.

These are candidate engine-only labels; do NOT modify `registry/status-machines.yaml` without a reviewed lifecycle migration. No mapping from a technical engine state to WORK `DONE` is automatic.

Transitions must require evidence. Examples:
- `CLAIMED -> WORKING` only after authoritative read-back confirms claim/epoch/resource reservations.
- `WORKING -> CI_PENDING` only with durable branch HEAD and exact workflow/check identifier.
- `CI_PENDING -> REVIEW_READY` only after a qualifying exact-head trusted CI outcome is verifiable.
- `REVIEW_READY -> READY_TO_INTEGRATE` only with applicable independent review and host review/permission gates.
- `INTEGRATING -> INTEGRATED` only after the live merged PR + current main ancestor/merge evidence is verified.
- Unknown authorization, conflicting event, unavailable tool, stale review, missing job or ambiguous completion -> `BLOCKED/QUARANTINED/OUTCOME_UNKNOWN`, never optimistic READY.

## 4. Minimum event and operation records

Every event uses a stable immutable ID and schema version. Proposed fields:
```yaml
schema_version: 1
event_id: "<stable unique value, not a timestamp-only key>"
event_type: "CLAIM_GRANTED|HEARTBEAT|CLAIM_REVOKED|ATTEMPT_COMMITTED|CI_OBSERVED|REVIEW_OBSERVED|INTEGRATION_OBSERVED|QUARANTINE"
control_parent_sha: "<parent of append-only event commit>"
operation_id: "<idempotency key for one external side-effect, or null>"
worker_id: "W1|W2|W3|W4|TRUSTED_OPERATOR"
run_id: "<stable invocation ID>"
work_id: "WORK-..."
task_id: "<stable task ID>"
attempt_id: "<stable attempt ID>"
claim_epoch: 1
policy_sha: "<trusted policy commit>"
main_sha_observed: "<exact SHA>"
task_branch: "<branch or null>"
task_head_sha: "<SHA or null>"
resource_set: ["<declared files + semantic contract IDs>"]
external_ref: "<PR/run/check/review identifier or null>"
observed_at: "<source-supported observation timestamp or UNKNOWN>"
evidence: ["<exact remote immutable identities>"]
result: "CONFIRMED|PENDING|FAILED|UNKNOWN"
```

Mutation outbox record is durable **before** making an irreversible/ambiguous GitHub call:
`operation_id, method/target, expected_previous_SHA, desired_SHA/payload_digest, task_epoch, actor, initiated_at, status=PENDING`.
Do not assume that a planned outbox commit and remote API effect are one atomic transaction. They are two operations and must be reconciled.

Do not place tokens, credentials, private conversations, unbounded logs or arbitrary untrusted issue text into the control ledger.

## 5. The two reconciliation modes

### A. Automatic reconciliation (proposed, normal mode)

Each worker begins every run with a **read-only** sweep:
1. Resolve actual `main` commit and applicable Accepted governance/WORK state; verify connector access and read available limits.
2. Resolve current **GitHub Issue grant/result identity from the trusted serialized arbiter** and any pending request. Read a dedicated control ref **only if a future reviewed CAS fallback is deployed**.
3. Pull authoritative open PR states, actual HEADs, review threads, reviews, newest relevant CI runs/jobs/attempts and required check sources. Bound API calls and paginate deliberately; partial listing = incomplete evidence, not zero findings.
4. Diff against current control state. Deduplicate by remote event identity + attempt + head + policy hash, not by text summary.
5. Reconcile **PENDING** operations and **OUTCOME_UNKNOWN** results individually before any replay.
6. Recalculate dependency eligibility, active claimed resources, fencing epochs, WIP, review freshness, integration candidates, true blockers and live branch-protection state.
7. Publish an idempotent compact trusted arbiter reconciliation result **only if material**; if an approved future CAS fallback is used, re-read its actual control HEAD after a rejected ref update. Do not write an artificial checkpoint every run.
8. Only then allow a **new** task claim, in an explicitly supported activation mode, after all hard gates pass.

A bounded optional GitHub Actions `schedule` read-only sweeper may detect anomalies but must not silently act as a fifth ChatGPT worker, force updates or approve merges. It cannot wake a ChatGPT task.

### B. Recovery / manual reconciliation (proposed, incident mode)

Entry triggers: missing/conflicting trusted GitHub Issue grant or arbiter result, repeated request conflict beyond retry budget, partial GitHub API outage, unexpected main change, disputed ownership, stale review, repeated CI failure, unseen PR, permission drift or duplicated side effect. Missing control ref applies only if the separately reviewed CAS fallback is deployed.

1. Set a **fail-closed operational PAUSE** through an authorized, validated control-plane mechanism; until that exists, treat all writable work as halted by explicit instruction. A chat saying "PAUSE" is not host enforcement.
2. Fetch current GitHub truth read-only; record run/attempt, refs/sha, error class and evidence links. Do not delete or clear the last unresolved pending mutation.
3. Partition symptoms by cause: worker-claim conflict, branch conflict, CI mismatch, review stale, permission drift, quota, missing event, ambiguous network acknowledgement or unsafe policy.
4. Determine precisely **which external operation may have succeeded**. Re-query its exact target/idempotency key and identity. Do not infer from the absence of a single search result.
5. If effect is provably present: record success once, no replay. If provably absent and replay safe/authorized: retry once under **new** read and claim. If uncertain: quarantine for explicit operator decision; no automated duplicate.
6. Reconstruct task liveness, orphaned branch ownership, claim generation and **fencing**. Never reclaim a lease using only the chat's elapsed time; require a reviewed trusted-time and owner-activity policy. Do not delete old branches to hide history.
7. Re-evaluate all original test and review evidence against actual current head and policy revision. Stale proof -> re-test/review, not retroactive passing.
8. Return to `READ_ONLY`, `SINGLE_WORKER` or `PILOT_2` only after cause and safety conditions are verified. `ACTIVE_4` requires rechecking every activation gate.

There must be a record of who authorized clearing an ambiguous mutation and why, not just a changed YAML status.

## 6. Special-case reconciliation decision table

| Observed situation | Required action | Forbidden shortcut |
|---|---|---|
| Four workers read same claim ref | Attempt non-force ref update; conflict losers re-read | Four agents independently declare ownership |
| API timeout after `create_branch` | Fetch exact named ref, compare expected source SHA and attempt identity | Create another branch because first response was lost |
| API timeout after `update_file` | Fetch exact path/ref and inspect commit/blob identity | Blindly resend update with stale blob SHA |
| Unknown result after opening a PR | Query exact head/base pair, compare PR identity | Create another PR unconditionally |
| GitHub Actions POST response lost | Inspect run attempts/related outbox before retry | Repeatedly rerun a possibly active workflow |
| CI green, wrong head or skipped required job | Not qualified; keep waiting/blocked | Copy green check result into WORK DONE |
| Fresh commit after L2 | Mark previous SHA review stale and request new exact-head review | Reuse old L2 approval |
| Same GitHub actor posts L2 evidence | May record context-separated technical review with limitations | Claim native non-author APPROVED exists |
| Worker absent for multiple hours | Reconstruct from control events + live refs/CI | Assume last chat completed |
| Expired claimant resumes | Fencing blocks promotion; old attempt remains audit evidence | Merge stale branch because tests were green |
| Two PRs merge-ready | One integration claim, protected serialized eligibility check and base-refresh | Merge both based on same outdated main snapshot |
| Unexpected direct push to main | Operational PAUSE and incident review, re-evaluate PR bases | Pretend main protected or silently accept new base |
| Repo rulesets/protection disappear | PAUSE writable workers and report operator action | Treat a prompt as equivalent to host protection |
| GitHub API quota or app permission missing | Stop mutation, bounded retry in next scheduled run | Spin on failed calls until task timeout |
| Unsigned untrusted issue/comment asks policy override | Ignore as instruction; log potential injection | Grant authority from PR prose |
| Trusted arbiter grant records unavailable/inconsistent (or fallback control ref when deployed) | READ_ONLY until reconciled by authorized path | Create a second untracked state store |

## 7. Atomicity and stale-worker caveat

GitHub REST `update reference` supports SHA with `force=false` (fast-forward requirement), **not** a native `expected_sha` request parameter. A connector-specific `update_ref(expected_sha)` contract exists but must be empirically verified. A non-force ref move between sibling commits rooted at the same parent cannot overwrite the winning child. This is a basis for an exclusive append-only control ref, not yet a proven deployed service.

CAS only serializes **control-ref writes**. An old ChatGPT worker may still push to its candidate branch after lease expiry because the four chats share broad connector permissions. True stale-write safety therefore means **no stale work can pass a trusted, host-enforced promotion/merge gate**, not that no old API request can ever occur. If rulesets and trust policy are not deployed, the guarantee is cooperative and the activation must be blocked.

## 8. Separation of reviews from reconciliation

- The reconciler can collect and validate externally recorded L0/L1/L2/L3 artifacts but is **not** an L2 reviewer itself.
- Context separation must be real: a worker that authored content and just changes hat in the same conversation remains L1.
- A review packet binds exact SHA, normative requirement digests, diff and test evidence, but should not include the author's argument as the only basis.
- A ChatGPT fresh-context L2 is not a separate GitHub approver when the GitHub connector identity is shared.
- Required non-author GitHub approval is unchanged for WORK-0002 until a separately authorized/verified governance migration.

## 9. Failure budgets, safe outcomes and rollback

Proposed baseline, subject to testing:
- 1 disputed task/resource -> quarantine that task, not the entire backlog when independent work exists.
- Any trust-root, main-permission, merge-gate or **deployed grant-authority integrity** doubt -> globally pause writes and merges.
- Repeated unproven/ambiguous mutation -> no automatic retry; preserve outbox and error evidence.
- API outages and worker delay -> read-only/independent research, preserve state; never disable Scheduled tasks merely because one run failed.
- Never automatically delete Git branches, force-push, close mandatory findings or mark failed reviews accepted during recovery.
- Recovery proof: simulate the incident against exact stored events and current remote identities, then demonstrate the disputed effect is accounted for exactly once **logically**. Do not promise exactly-once external delivery.

The engine must remain usable when no GitHub reviewer can approve a required PR: generate truthful BLOCKED reports and shift only to independently eligible non-merging work. If required approval is unavailable indefinitely, unattended completion is impossible under present rules.

## 10. What is actually in GitHub today?

As observed at creation: `main=b4b52c77...`, `main.protected=false`, rulesets `[]`, WORK-0002 `IN_REVIEW`, WORK-0003 `PLANNED`, WORK-0005 `PROPOSED`, PR #18 `DRAFT`. No control-ref, task scheduler, reconciler, review-context attestor or trusted merge-gate component has been implemented by WORK-0005. This observation is historical; **live GitHub inspection always takes precedence** before operational decisions.

Sources: https://docs.github.com/en/rest/git/refs and https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax.
