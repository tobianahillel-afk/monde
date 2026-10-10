# RFC — MONDE Development Engine v2: ChatGPT + GitHub only

Status: Proposed — research/engineering specification, **not Accepted**
Date: 2026-10-10
Work: WORK-0005
Tracking: https://github.com/tobianahillel-afk/monde/issues/17
Base reviewed for discovery: main b4b52c77fbf05eda65e8f0e951959da70e7edbe7

## 0. Hard platform and assurance constraints

MONDE is developed exclusively with four independent ChatGPT Scheduled task conversations, the **GitHub connector**, the GitHub repository and **GitHub-hosted Actions**. No user-controlled PC, shell, persistent host, external coordinator, independent paid Codex reviewer, Temporal, Beads/Dolt service, OpenHands server or Gas Town service may be required. GitHub-hosted runner compute may execute tests, validators and simulations, **not an autonomous ChatGPT L2 session**. GitHub Actions workflows cannot secretly call paid models or Codex; AI reasoning occurs in the four ChatGPT conversations.

The four scheduled tasks have the same nominal hourly trigger (exact_schedule; Europe/Paris), equivalent capabilities and different worker identifiers W1..W4. The ChatGPT scheduler does **not** promise simultaneous start, fixed duration, nonstop execution, or permission-free GitHub writes. Calls may require approval, be skipped, fail or hit quotas. A task is a bounded activation, not a daemon.

**Identity limitation:** all four conversations may act as the same GitHub user/app. `worker_id` is a logical claim, not a cryptographically independent security principal. Other ChatGPT contexts can provide separate-perspective L2 *analysis*, but they cannot fabricate distinct GitHub authors/approvers. GitHub authors cannot approve their own PRs. Existing WORK-0002/A3 exact-head, non-author collaborator approval remains mandatory unless the repository owner explicitly approves a safe reviewed governance change. Therefore completely unattended A3/A4 completion is **not guaranteed** under the current identity constraints. Never lower the bar silently.

## 1. Mission, ownership and non-goals

Optimize useful **accepted merged MONDE product increments per wall-clock time**, not generated LOC, worker uptime or count of branches. Preserve one World Model, evidence/provenance/temporal/uncertainty invariants and the canonical work hierarchy `PHASE → LOT → SUBLOT → WORK → TASK → RUN → PR → REVIEW → MERGE`.

Owner of normative truth: `main` Constitution + accepted ADRs + `registry/` + `docs/`. Owner of volatile GitHub evidence: GitHub PR, review, action-run/check, ref and API state. Proposed operational coordination: **one dedicated append-only control ref**, separate from `main`, that stores compact task reservations, event IDs and checkpoints; never edit historical decisions in place. Issues/subissues/projects are view/projection, not a second transaction authority.

Do NOT write a custom Git hosting system, CI queue, full task tracker UI, agent SDK, code-review model, test framework, GitHub merge queue, or duplicate document corpus. Use GitHub Actions, native PR reviews, requirements work records, shared action workflows, CodeQL, Dependabot and existing templates first. GitHub native merge queue is not available for a public personal-owned MONDE repository; integration must be serialized and protected under available branch/ruleset settings.

Beads, Gas Town, OpenHands, mini-SWE-agent and Temporal are **not installable as the required runtime** under this zero-host user constraint. Their concepts can inform a later redesign, but do not add their services to MONDE.

## 2. Five small v2 engines

### 2.1 Documentation + specification router
- Reuse `README.md`, `AGENTS.md`, `docs/00_START_HERE.md`, `registry/`, `docs/10_ROADMAP/`, `docs/11_ADR/`, `docs/13_QUALITY/`. Do not install Spec Kit over the existing constitution.
- Per work: scope/non-scope, read_before (only relevant files), dependencies, reusable components, owners/contracts, atomic acceptance criteria, tests, risk, known uncertainty, finite next action, rollback and completion proof.
- Development may switch roles in one run without inventing new sessions. For long work, commit small stable checkpoints on one authorized attempt branch and store SHA/evidence.
- Distinguish normative docs (reviewed, immutable in accepted scope), volatile run events and projections. Generate concise PROJECT_STATE projections from canonical WORK + current GitHub data, never rewrite a reviewed exact HEAD only to copy CI outcome.
- Canonical documents never treated as Accepted unless cold-read and the applicable review/lifecycle gates are genuinely met.

### 2.2 Priority allocator
Input: canonical task DAG and current operational snapshot; candidate tasks, exact prerequisites, file and **semantic** write sets, priority, criticity, review need, dependencies, max WIP, cost and expected unlock.
Hard filter: unauthorized/blocked/stale tasks, failed required dependency, contract incompatible, colliding active reservation, missing input decision, unknown external permission, budget unavailable.
Choose a compatible set of up to four distinct tasks maximizing expected critical-path reduction, downstream unlock and accepted deliverability minus rework/integration/review cost. Pure deterministic function; compare against FIFO on replayed actual WORK-0002 history and synthetic adversarial fixtures. Weights must be measured, not invented.
Workers are role-fluid (DISCOVER/RESEARCH/EXPERIMENT/DECIDE/BUILD/FIX/TEST/VERIFY/L1/L2/REVIEW_PREP/TRIAGE/INTEGRATE/DOCUMENT). **No fixed W1=author/W2=reviewer assignment**.

### 2.3 Atomic claim + fencing
Read authoritative control ref sha A, calculate an allocation, create one event commit B with sole parent A. Update control ref with `force=false` and expected_sha=A when supported; concurrent siblings cannot both fast-forward. Loser re-reads; never retry against stale state or `force=true`. This property must be proved against the actual GitHub connector before relying on it.
Persist claim_id, owner_worker, task_id, attempt_id, lease deadline, monotonic generation/fencing epoch, base SHA, allowed file/semantic sets, policy epoch and mutation_id. Use trusted GitHub observations for expiry as far as possible; local chat timestamps are not authority.
A stalled/expired worker can leave a task branch, but no stale attempt is promoted or integrated: CI/merge eligibility recomputes against current authoritative fencing token, policy and HEAD. If connector cannot enforce a server-side lease or trusted promotion gate, classify protection as **cooperative**, never as a hard security guarantee.
Disjoint tasks can both claim; overlapping semantic contracts or shared canonical YAML/Markdown owners cannot. One security/trust-root writer at a time. Prefer work-set reservation over a global execution lock.

### 2.4 GitHub event reconciliation / CI futures
Push a small authorized task branch -> GitHub Actions runs asynchronously -> record exact SHA + run_id + run_attempt + workflow/job/check source + policy version as a future. Worker can release writing claim after a durable checkpoint and continue on another independent task; task still pending.
Next worker reconciles pending runs against GitHub: success -> VERIFY_READY only if qualifying trusted source, failure -> FIX_READY, skipped/cancelled/stale/unprovable -> BLOCKED or RETRY_ELIGIBLE according to reviewed rules. A raw green check never equals acceptance.
External writes with lost ACK: mark OUTCOME_UNKNOWN, inspect authoritative ref/check/PR using idempotency key **before** retry; do not duplicate commits, workflow reruns or review requests.
Scheduler/task states are *proposed internal v2 states*, NOT silently added to existing `registry/status-machines.yaml`. Add explicit reviewed transitions/migration if adopted.

### 2.5 Review council / guarded integration
In an author run: perform tests and L0/L1; prepare review packet anchored to exact immutable SHA: work/requirements, actual diff, tests and failures, threat model, question checklist; do not include author's persuasive explanation as primary evidence.
A different ChatGPT Scheduled task / different conversation / fresh prompt, with read-only first phase, reviews exact SHA and all required hats, tests and counterexamples. That can be L2 **context-separated evidence** if genuinely fresh and authoring-separated, not merely the author switching persona. Cross-model or Codex credits are not required for technical L2; avoid same worker reviewing its own work even on another activation.
Record reviewer_worker, fresh_context assertion, review_source, reviewed_sha, reviewed norm digests, tests/evidence, findings, outcome and limitations. Because shared GitHub identity cannot cryptographically establish context separation, grade as context-attested rather than hard-verified unless a verifiable independent identity/evidence mechanism is added.
L3 requires multiple genuinely independent contexts and additional adversarial scrutiny; multiplying hats in one chat remains L1. Any material code change invalidates prior exact-head L2.
**Do not equate L2 evidence with GitHub's APPROVED review by a non-author.** Where WORK-0002 or repository policies require an actual non-author collaborator review, integration stays BLOCKED until that separately valid approval occurs. A change to this process requires a dedicated reviewable governance proposal with security impact, owner authorization and live host enforcement.
Integration: at most one integration claim; current main SHA, head SHA, green correct-source required checks, active fencing token, authorized writes and accepted reviews; merge with expected head SHA and re-check main. No direct main edits; no force push.

## 3. Immediate continuous work within one invocation

Example for worker W1:
```
READ LIVE STATE → RECONCILE → CLAIM TASK-A
  RESEARCH → SPECIFY/DECIDE → IMPLEMENT → SELF-TEST → L1 → PUSH
  CI_PENDING exact head → DURABLE CHECKPOINT → RELEASE task writer
  choose next eligible task (perhaps TEST / DOCUMENT / RESEARCH)
  if L2 evidence appears while still active, validate origin and proceed to next authorized phase
  end: verified run report; no artificial commit
```
W2 independently picks L2 on TASK-A as soon as it becomes READY, including in the same hour if actually running. It need not wait a scheduled hour *by rule*, but no real-time wake-up is guaranteed. W1 cannot manufacture W2's fresh-context review inside W1's own uninterrupted chat.

## 4. Exact task decomposition contract and example

Each work item is divided by deliverable and acceptance gates, not by time or agent personality. A TASK declares:
`task_id, objective, assumptions, depends_on, priority, risk, expected_input_sha, file_write_set, semantic_write_set, read_before, tests, completion_evidence, budget, rollback, state`.

Example initial separation:
- A / WORK-0002 trust-root (one exclusive writer): finish independently authorized review or record P1 root-cause reset; no v2 scope.
- B / WORK-0003 protection analysis (read-only until admin settings route confirmed).
- C / WORK-0005 scheduler research/spec simulation (isolated docs branch).
- D / WORK-0004 capability inventory research only where existing dependencies permit.
Tasks A and C may overlap on `PROJECT_STATE.md` in their drafts; allocator must guard shared canonical documents and avoid integration conflict. Immutable review fields carry source/revision, not just human labels.

## 5. Repository implementation layout (proposal, not created)
```
docs/12_RESEARCH/chatgpt-github-only-development-engine-v2-rfc.md  # this noncanonical RFC
docs/11_ADR/ADR-0001-chatgpt-github-only-development-engine.md     # proposed decision
registry/work-items/WORK-0005.yaml                              # proposal/spec owner
engine/dev/allocator.py                                         # only after policy approval
engine/dev/claims.py
engine/dev/reconcile.py
engine/dev/review_packets.py
tests/dev/test_allocator.py
tests/dev/test_claims_property.py
tests/dev/test_reconcile.py
.github/workflows/monde-dev-engine-validation.yml             # untrusted candidate tests
.github/workflows/monde-dev-engine-trusted-gate.yml             # only once accepted on main
```
No full separate governance platform. Keep implementation code outside `.github/trusted` unless actual secure trust ownership requires otherwise.

## 6. Reuse matrix
**NOW**: GitHub Git refs/commits/PRs/Issues/Actions/Artifacts, current work registers, templates, Python unittest+coverage, CodeQL existing, dependency checks already configured.
**SCOPED CI TEST**: actionlint + zizmor (workflow correctness/security), Ruff (Python lint), Hypothesis (concurrency property/model tests), Pyright optionally if benefits are demonstrated. Pin versions and use controlled permissions.
**NOT REQUIRED**: Gas Town, Beads runtime/Dolt, Temporal, OpenHands, mini-SWE-agent, Docker, local caches, Redis, paid reviewer services, new dashboard.
**OPTIONAL FUTURE**: GitHub Projects as human projection, broader static analysis when real product code appears, event-triggered ChatGPT tasks only if verified supported and consistent with four-task limit.
Spec Kit may inform checklist templates, never replace existing MONDE specification precedence.

## 7. Mandatory test matrix before four-worker activation

T01 four starts on same SHA with four independent eligible tasks; 4 distinct claims, zero duplicate.
T02 four starts with only two conflicting write/semantic resources; at most compatible owners.
T03 same Git ref parent, two incompatible children; non-force CAS rejects one and it re-reads.
T04 old worker persists after reclaim; old SHA/fencing cannot be promoted/merged.
T05 ambiguous POST/update acknowledgement; reconciliation prevents replay.
T06 CIDAG prerequisite not satisfied; successor not runnable.
T07 checked-in code touched undeclared contract even under different paths; scope violation.
T08 API rate-limit/connector approval pause; durable resume with no mutation storm.
T09 ChatGPT task absent for hours; subsequent task can recover from GitHub alone.
T10 CI finishes after worker ends and a newer attempt starts; stale check never authorizes.
T11 check spoof/skipped job/candidate-owned untrusted validator; fail closed.
T12 reviewer changes hats within same conversation: classify L1, never L2.
T13 distinct fresh ChatGPT context, no author reasoning, exact SHA: eligible L2 technical evidence; **not** GitHub non-author approval.
T14 review quota exhausted, independent reviewer unavailable: preserve BLOCKED but keep independent tasks moving.
T15 two ready PRs compete for main: serialized integration; second rebases/rechecks before eligibility.
T16 docs state derives current live PR/CI facts instead of replaying stale `PROJECT_STATE.md`.
T17 exhausted WIP budget: workers do VERIFY/RESEARCH, not spawn branches.
T18 malicious issue/PR/CI-log prompt injection: no change to policy/credentials/authorities.
T19 no external reviewer actor for A3/A4 required approval: integration stays blocked; no fake approval.
T20 scheduled task starts late/overlaps next hour: lease/fence safe and no time-based mutual exclusion.

Acceptance for the controller: **0 unauthorized merges, 0 lost authoritative claim writes, 0 double owner claims for colliding tasks**, exact proof replayable, independent L2 truthfulness and demonstrably faster accepted integration than single-worker baseline. Transient stale branches or a missed hourly invocation are not always preventable; their effects must be safe.

## 8. Deployment sequence (hard-stop checkpoints)

G0 **Review current truth:** freeze WORK-0002 scope; verify PR #14, exact L2 state and native branch protection; present owner-accessible WORK-0003 settings checklist. Do not merge untrusted candidate.
G1 **Decide L2 authority migration:** maintain separate L0/L1/L2/L3 definitions and review evidence. Document policy impact of removing Codex *dependency* without weakening GitHub's non-author approval rule. User authorization required for any significant governance rule change.
G2 **Accept spec/ADR only after independent cold read:** do not prematurely mark `WORK-0005` READY/DONE or upgrade policy.
G3 **Pilot pure scheduler with generated fixtures in GitHub Actions:** runs with one worker, 100% meaningful coverage target, no live mutable resources.
G4 **Implement proof-of-CAS in isolated control branch:** live 4-way race, fail-closed errors, fencing, GitHub connector permissions; trust-root and main protection prerequisites.
G5 **Add reconciliation + CI futures + review packet exporter:** passive read-only first, fault injection, real GitHub Actions runs.
G6 **Two-worker end-to-end** on independent low-risk scoped docs/code; measure actual merge and review delay.
G7 **Four-worker trial** under simultaneous nominal schedule, limited WIP and with rollback to one worker; no L2 fabrication, no host protection bypass.
G8 **Product priority:** immediately after minimum viability, work on MONDE's lawful source → evidence → temporal ledger → query → Console/Globe vertical slice, rather than growing the orchestration platform.

## 9. Operator/run report (compact and verifiable)

For every bounded invocation record `worker_id, run_id, observed_start, initial_main_sha, control_epoch, claimed_work/task, input/base/head sha, files actually changed, test names/outcomes, CI run attempt and proof, review source/outcome, API errors, mutation_ids, blockers, next precise step, observed_end`. Do not claim that an unavailable timestamp or test was observed. Do not add unbounded prose to the historical log. A task that only changes role remains the **same agent execution**, so a same-run hat switch can never be independent L2.

## 10. Risks that could invalidate this RFC
1. ChatGPT task and app permissions may require explicit interactive approval, preventing unattended push/merge.
2. GitHub same-account reviews cannot meet author≠reviewer host rule; high assurance needs an independent actor or an explicit governance choice.
3. Self-stated `worker_id`/fresh_context cannot prove a second ChatGPT context cryptographically.
4. Personal-account `main` currently unprotected; admin changes are outside the current GitHub connector's supported operations.
5. An unverified CAS implementation can corrupt operational task assignment.
6. GitHub Actions cannot wake or spawn a ChatGPT Scheduled task by writing a file, and CI is not an LLM reviewer.
7. Four tasks on an eligible ChatGPT plan consume a limited active-task budget; other tasks may be affected by account limits.
8. Treating work histories from branch-local stale documents as current could deadlock progress.
9. Too much documentation/validation overhead can prevent MONDE product increments; periodically measure critical path and remove duplicative steps after reviewed risk evaluation.

These are blockers/assumptions to **test**, not claims that the final engine already works.
