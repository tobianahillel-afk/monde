# RFC — MONDE Development Engine v2: ChatGPT + GitHub only

Status: Proposed — research/engineering specification, **not Accepted**

> **CURRENT WORKER AUTONOMY + TECH BASELINE:** [Operating contract and technology decisions](chatgpt-github-only-engine-operating-contract.md) sets role switching, automatic decisions, research/technology comparison, review separation, documentary change discipline, open-source test stack and dependency pinning. Proposed until independent review; no workflow deployed.

**CURRENT SIMPLIFICATION / READ FIRST:** [Minimal foundations: GitHub-native four-worker engine](chatgpt-github-only-development-engine-minimal-foundations.md) is the preferred low-complexity experimental architecture, linked by Proposed ADR-0001. It reuses Issues, native issue dependency/subissue views, a tiny trusted `actions/github-script` dispatcher, standard CI and existing MONDE registries. Sections below describing per-worker Git-control-ref CAS, a large event-sourcing ledger or fifteen detailed machine states are **fallback research alternatives**, NOT a mandatory implementation plan. Do not implement all alternatives or create competing status authorities. All accepted rules remain in force. First empirical gate: ChatGPT Scheduled GitHub connector→issue-comment webhook→default-branch Actions dispatcher.
Date: 2026-10-10
Work: WORK-0005
Tracking: https://github.com/tobianahillel-afk/monde/issues/17
Base reviewed for discovery: main b4b52c77fbf05eda65e8f0e951959da70e7edbe7

**Critical-path simplification audit:** [risk-ranked audit, central GitHub Actions allocator experiment and effort estimates](chatgpt-github-only-engine-critical-path-audit.md). **Do not freeze a bespoke per-worker CAS architecture before empirically comparing the much smaller trusted single-writer GitHub Actions dispatcher.** All architecture options remain Proposed. 

**Launch readiness: NOT_READY (design only).** Read [15 activation gates and startup mode policy](chatgpt-github-only-engine-launch-readiness.md) and [automatic/manual reconciliation contract](chatgpt-github-only-engine-reconciliation-runbook.md) **before** suggesting, creating or activating four write-capable scheduled tasks. Every listed engine is proposed; as of this draft, there is no implemented control-ref scheduler, automatic reconciliation, trusted integration switch or actual worker coordination. "Frozen" means an accepted exact-SHA contract only; this RFC and ADR are **not frozen/Accepted**.


## 0. Hard platform and assurance constraints

**BOOTSTRAP DECISION (2026-10-11):** development of the v2 engine itself is performed **interactively**, on explicit user messages in this GitHub-connected ChatGPT conversation; it is NOT delegated to four Scheduled tasks. Those four Scheduled ChatGPT tasks will be created/used **only in controlled tests after the code and applicable authorizations are ready**, then operated as workers only after a distinct user launch decision. Future routine MONDE product development targets four independent Scheduled task conversations, the **GitHub connector**, the GitHub repository and **GitHub-hosted Actions**. No user-controlled PC, shell, persistent host, external coordinator, independent paid Codex reviewer, Temporal, Beads/Dolt service, OpenHands server or Gas Town service may be required. GitHub-hosted runner compute may execute tests, validators and simulations, **not an autonomous ChatGPT L2 session**. GitHub Actions workflows cannot secretly call paid models or Codex; AI reasoning occurs in the four ChatGPT conversations.

The four scheduled tasks have the same nominal hourly trigger (exact_schedule; Europe/Paris), equivalent capabilities and different worker identifiers W1..W4. The ChatGPT scheduler does **not** promise simultaneous start, fixed duration, nonstop execution, or permission-free GitHub writes. Calls may require approval, be skipped, fail or hit quotas. A task is a bounded activation, not a daemon.

**Identity limitation:** all four conversations may act as the same GitHub user/app. `worker_id` is a logical claim, not a cryptographically independent security principal. Other ChatGPT contexts can provide separate-perspective L2 *analysis*, but they cannot fabricate distinct GitHub authors/approvers. GitHub authors cannot approve their own PRs. Existing WORK-0002/A3 exact-head, non-author collaborator approval remains mandatory unless the repository owner explicitly approves a safe reviewed governance change. Therefore completely unattended A3/A4 completion is **not guaranteed** under the current identity constraints. Never lower the bar silently.

## 1. Mission, ownership and non-goals

Optimize useful **accepted merged MONDE product increments per wall-clock time**, not generated LOC, worker uptime or count of branches. Preserve one World Model, evidence/provenance/temporal/uncertainty invariants and the canonical work hierarchy `PHASE → LOT → SUBLOT → WORK → TASK → RUN → PR → REVIEW → MERGE`.

Owner of normative truth: accepted Constitution, ADRs, `registry/` and `docs/` on `main`. Owner of volatile GitHub evidence: GitHub PR, review, action-run/check, ref and API state. **Selected for the next prototype: one trusted serialized GitHub Actions Issue-comment arbiter**, with strictly parsed requests and bot-authored response comments on one designated Issue. **No Git control-ref ledger or second status database.** The ref-CAS approach in §2.3 remains fallback-only research and MUST NOT be implemented beside the selected arbiter.

Do NOT write a custom Git hosting system, CI queue, full task tracker UI, agent SDK, code-review model, test framework, GitHub merge queue, or duplicate document corpus. Use GitHub Actions, native PR reviews, requirements work records, shared action workflows, CodeQL, Dependabot and existing templates first. GitHub native merge queue is not available for a public personal-owned MONDE repository; integration must be serialized and protected under available branch/ruleset settings.

Beads, Gas Town, OpenHands, mini-SWE-agent and Temporal are **not installable as the required runtime** under this zero-host user constraint. Their concepts can inform a later redesign, but do not add their services to MONDE.

## 1A. IMPLEMENTATION-READY DESIGN FREEZE — proposed, NOT an Accepted ADR

**Use this section as the next implementation PR's contract.** It freezes *author-side technical choices only*, not existing repository governance or launch permission. Build interactively when the user says to code. **Do not create or run any Scheduled task while building**; Scheduled ChatGPT W1–W4 are exclusively later controlled test subjects until the user separately approves launch. Nothing below authorizes changing `main`, bypassing WORK-0002/3 or marking this PR Accepted.

**Exactly four proposed executable/configuration files for the prototype** (new scoped implementation WORK/PR, not this draft PR; one of these is read-only PR test CI):
- `.github/workflows/monde-dev-dispatch.yml`: one serialized GitHub Actions event adapter, with `issue_comment: created` (non-PR designated command Issue) and `workflow_dispatch` for a manual reconciliation/fixture test. Constant `concurrency.group: monde-dev-dispatch`, `queue: max`, `cancel-in-progress: false`. Checkout **trusted default-branch source only**; pin reviewed immutable full action SHAs; `permissions` limited to `contents: read, issues: write, checks: read, actions: read, pull-requests: read` where actually required. Do not run PR-controlled commands, install from a PR, inject Issue text into shell or give `contents: write`.
- `.github/scripts/monde-dev/controller.cjs`: a **single** CommonJS module loaded by `actions/github-script`, using its provided Octokit client. Export pure `parseRequest`, `normalizeResources`, `choose`, `reduceEvents`, `reconcile` plus a small `run` adapter. Keep GitHub API I/O at the boundary and logic deterministic; no external package, framework, database, worker daemon or second trust ledger.
- `.github/scripts/monde-dev/controller.test.cjs`: Node's built-in `node:test` + `assert/strict` with synthetic REST fixtures, real four-way conflict cases and negative security/recovery cases.
- `.github/workflows/monde-dev-ci.yml`: a **separate, unprivileged** `pull_request`/manual verification workflow for these implementation paths, doing JS syntax + `node --test`, and workflow security checks where available. `permissions: contents: read`; zero issue-write/secrets/privileged token in the PR test job. Its green badge is candidate evidence, not a replacement for approved merge-source checks. Reuse an already proven suitable trusted CI job instead and omit this file only after actual proof.

**First-run constant configuration** is held in trusted workflow code (not user comments or candidate branches): allowlisted command Issue number **TBD_REAL_ISSUE_ID** (must be an actual new non-PR GitHub Issue), allowed authenticated GitHub actor(s) **TBD_REAL_ALLOWED_ACTOR** from verified live event, `MODE=TEST_ONLY`, expected default-branch repository identity, policy revision. These values are external observations, NOT architectural choices for the model to invent. Workflow refuses work until configured and reviewed.

### One typed request / one signed-by-origin *logical* answer

One GitHub Issue **comment**, no embedded shell or markdown instructions. Body consists of an exact first-line marker `MONDE_DEV_V1` and one JSON object on the second line; maximum **4 KiB**, reject additional material or unknown fields. Schema for `CLAIM`:

```json
{
  "v": 1,
  "op": "CLAIM",
  "request_id": "uuid-or-unique-opaque-id",
  "worker": "W1",
  "work": "WORK-0006",
  "task": "T1",
  "base_sha": "40-hex-commit-sha",
  "resources": ["path:.github/scripts/monde-dev/", "contract:dev-grants"]
}
```

Also accept `RELEASE` (`request_id,worker,work,task,grant_id,epoch,observed_head`) and `STATUS` (`request_id,worker,work,task`). `STATUS` only reads current GitHub facts and does not create/release a grant. All commands carry `v=1` and strict schema; `request_id` deduplicates retries and is unique within authenticated request provenance. **Actor identity comes from GitHub's signed event, never the `worker` string**. W1–W4 are coordination labels; all may share a single GitHub principal. Unknown `op`, malformed ID, extra keys, unauthorized actor, wrong Issue or PR comment → reject/fail closed.

`resources` are canonical **exclusive names**, e.g. `path:src/geo/`, `path:src/geo/tile.py`, `contract:GeoTileV1`, `registry:shared`, `trust:actions`, `integrate:main`. Normalize `path:` as repository-relative POSIX, reject `..`, absolute paths, empty components, control characters and ambiguous separators. Conflict when resource tokens are equal or path namespace/prefix overlaps; reject ambiguous shorthand and never infer that two different file paths imply disjoint shared contract ownership. Task eligibility must be read from existing current WORK/accepted `read_before`, `depends_on`, `status` and scoped rights; command claims cannot override them.

**Bot response** is a distinct Issue comment with marker `MONDE_DEV_RESULT_V1` and machine-readable JSON: `request_id,event_comment_id,worker,work,task,outcome,grant_id,epoch,resources,observed_base_sha,workflow_run_id,workflow_run_attempt,reason,created_at`. Outcomes `GRANTED|DENIED|NO_CHANGE|BLOCKED|UNKNOWN|RELEASED`; no client can turn a refusal into grant by editing a comment. Confirm result author is expected GitHub Actions identity and cross-check run/repo when authoritative; bot comments are durable **operational evidence**, not cryptographic independent worker identities. Do not store secrets or private Project chat content.

### Event reduction and safety invariants

1. Parse the actual single incoming comment from event payload only if the repo, Issue, GitHub actor and event type match the trusted allowlists.
2. Fetch **all** relevant Issue comments with pagination, reconstruct only trustworthy request/result events, and compare each request's exact ID and **current** canonical task status. Missing pages, inconsistent bot results, ambiguous API failure or unknown remote mutation outcome → `UNKNOWN/BLOCKED`, never issue speculative grants.
3. Under GitHub Actions **serialized concurrency**, derive active grants deterministically from verified results; reject duplicate request IDs unless the earlier result matches exactly (idempotent replay); reject overlapping file or semantic resources. Multiple non-conflicting grants W1–W4 are allowed. No fairness/FIFO guarantee is assumed.
4. Publish one durable result and **read it back**. If publishing ACK is lost, re-list by request/event ID before retrying; if still ambiguous, quarantine. Response comments have no authority to mark normative WORK `DONE`, auto-approve a PR or alter protected branches.
5. `RELEASE` only for the matching **current** `grant_id + epoch + worker + task`, with expected observed branch HEAD checked when relevant. No **time-only** automatic reassignment: stale worker may still have connector write permission. A stalled grant is BLOCKED/QUARANTINED until a controlled authorized recovery with independent host verification; mere chat elapsed time is not a lock or a credential.
6. Every worker rereads the grant and target branch HEAD before mutation and after uncertain writes, works only in its owned branch/resource set, and freezes candidate HEAD during exact-head CI/review. No automatic merge, force push, native self-approval or direct `main` edit. **Cooperative collision prevention is not hard per-chat authentication** under one shared GitHub account.

**Modes:** `TEST_ONLY` is the **deployed starting mode**. Synthetic claims/fixture conflicts may be recorded, but no task gets product branch-write authorization or integration from this controller. Transition to four real write-capable workers is a separate reviewed change after T0–T5, WORK-0002/3 host gates and user launch consent. Interactive authoring on isolated branches can continue through pre-existing authority independently of this test mode.

## 1B. CODE-FIRST IMPLEMENTATION CHECKLIST + test oracle (freeze candidate)

**Build on user requests in this conversation, in one separate scoped implementation branch.** No Scheduled task for routine coding, no code pushed to `main` outside the host approval process. The *future* four worker prompts are prepared but inactive. No UI, SQLite, Docker, Redis, workers SDK or paid AI model.

**Implementation order / coherent commits:**
1. **E0 — static pure functions + fixtures.** Implement strict schema parsing/normalization, resource overlap, canonical WORK eligibility, grant state reducer, request idempotence; unit-test with `node --test` before any webhook. Completion: four disjoint requests all granted; four claims on same resource at most one granted; unchanged duplicate returns prior result.
2. **E1 — GitHub REST adapter (mocked).** One paginated Issue-comment reader, trusted result filter, controlled result writer with readback; no hidden network in pure core. Mock missed page, HTTP 403/429, timeout after write, duplicate events, wrong author/repo/issue. Completion: never publish conflicting grants or falsely report an ambiguous write as success.
3. **E2 — read-only CI + trusted event workflow on isolated PR.** Run candidate JS tests on PR with no issue-write privilege, lint/action-security check as available. Review workflow trust boundaries before any production deployment; avoid `pull_request_target` execution of candidate code.
4. **E3 — authorized default-branch test deployment.** Only through independent applicable review and GitHub host permissions; create the real command Issue/config. `MODE=TEST_ONLY` is mandatory. Verify actual `issue_comment` triggers Actions on default branch and bot result correlates to event.
5. **E4 — four-worker concurrency tests.** Synthetic W1..W4 simultaneous nonconflicting and conflicting requests, delayed/absent/comment API response, stale attempt, manual reconciliation, review of scope handovers. Then *only after user approves the test schedule*, create/run four Scheduled ChatGPT tasks for a bounded test, not for V2 development.
6. **E5 — promotion decision.** Review actual event delivery, user account permissions, source of checks, acceptance authority and WORK-0002/3 host settings. If any missing, stay `TEST_ONLY` / `BLOCKED`, document concrete GitHub evidence and let the interactive developer fix it. Full ACTIVE_4 use requires a later explicit decision.

**Unit/adapter acceptance vectors** (all must be observable, not a green badge guessed by ChatGPT):

| ID | Input/event | Must be true |
|---|---|---|
| AT-01 | Four different WORK/TASK and disjoint resources, same starting snapshot | Four distinct non-overlapping GRANTED results |
| AT-02 | Four concurrent CLAIMs on same exclusive path or shared semantic contract | At most one current effective grant on any resource |
| AT-03 | Same request ID delivered twice/out-of-order | Exactly one effective result; reread existing result, never double allocate |
| AT-04 | Same request ID with different payload/actor | BLOCKED conflict, no trust in the replacement |
| AT-05 | Wrong Issue, PR comment, unknown actor, forged worker W2 | No authorized mutation; worker label is not authentication |
| AT-06 | Shell/markdown injection, path traversal, extra JSON keys, oversized command | Strict rejection; no user text evaluated as executable code |
| AT-07 | WORK missing/unready, dependency not accepted, contract ownership uncertain | DENIED/BLOCKED; no grant based on comment's own claims |
| AT-08 | API pages incomplete, transient 403/429, lost mutation ACK | UNKNOWN and readback/backoff; no blind replay or second grant |
| AT-09 | Matching RELEASE vs mismatched epoch, grant ID, SHA or actor/worker | Only current matching grant released; stale attempt rejected |
| AT-10 | One worker disappears; another starts; current grant unproven | Quarantine, no time-only automatic takeover or false merge eligibility |
| AT-11 | CI still running, completed on old HEAD, skipped, untrusted source | Candidate remains pending/blocked; continue other eligible work |
| AT-12 | CI complete on current HEAD, valid tests, review incomplete | No false acceptance; integration still blocked by review authority |
| AT-13 | Existing REVIEW/TEST covers unchanged scope versus changed contract | Reuse analysis, inspect delta or full review as needed; stale formal approval never reused |
| AT-14 | Four actual test workers request disjoint vs conflicting tasks | Successful readback/handover, no duplicate reservation; no unapproved code merge |
| AT-15 | Bot response self-triggers new issue_comment event | Ignore as request; prevent recursive write/notification storm |
| AT-16 | Repository `main` lacks branch protections or native non-author approval | No unattended integration, irrespective of ChatGPT reviewer opinion |

**Definition of Done for an implementation PR:** real code + built-in tests; manual/CI results attached to exact SHA; all applicable existing governance/Review Council/authority gates; short developer handover, source/actor validation, four-way verified test evidence, no unexpected comment duplication, all trust incidents recoverable or fail-closed. **No experiment may silently promote `TEST_ONLY` into full write-capable mode.**

**Review memory is not a second product:** existing `WORK.review_plan`, `REVIEW-*`, `TEST-*`, PR threads and exact HEAD own scoped coverage; preserve tested and untested surfaces plus invalidation conditions. Prior review knowledge may be reused, but formal current-head approval requires fresh evidence where the Accepted rules say so.

## 2. Five functional responsibilities (analysis lenses, **not five custom engines**) 

**Current target:** only one trusted GitHub Actions arbiter using existing GitHub Issues/PR/CI, plus small `choose`/`reconcile` helpers and optional read-only `check_eligibility`. The control-ref CAS/event-sourcing detail in 2.3 is **historical FALLBACK architecture**, not the selected implementation path. See [one canonical worker operating contract](chatgpt-github-only-engine-operating-contract.md) for pending-CI behavior and conditional phases.

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

### 2.3 Atomic claim + fencing — FALLBACK ONLY

Prefer the trusted GitHub Actions serialized allocator with durable Issue-request/grant records. Only investigate the following per-chat ref-CAS plan if the tested GitHub Actions dispatcher cannot satisfy claims safely; never build both as mandatory components.
Read authoritative control ref sha A, calculate an allocation, create one event commit B with sole parent A. Update control ref with `force=false` and expected_sha=A when supported; concurrent siblings cannot both fast-forward. Loser re-reads; never retry against stale state or `force=true`. This property must be proved against the actual GitHub connector before relying on it.
Persist claim_id, owner_worker, task_id, attempt_id, lease deadline, monotonic generation/fencing epoch, base SHA, allowed file/semantic sets, policy epoch and mutation_id. Use trusted GitHub observations for expiry as far as possible; local chat timestamps are not authority.
A stalled/expired worker can leave a task branch, but no stale attempt is promoted or integrated: CI/merge eligibility recomputes against current authoritative fencing token, policy and HEAD. If connector cannot enforce a server-side lease or trusted promotion gate, classify protection as **cooperative**, never as a hard security guarantee.
Disjoint tasks can both claim; overlapping semantic contracts or shared canonical YAML/Markdown owners cannot. One security/trust-root writer at a time. Prefer work-set reservation over a global execution lock.

### 2.4 GitHub event reconciliation / CI futures

The normative candidate recovery details live in the [reconciliation/runbook proposal](chatgpt-github-only-engine-reconciliation-runbook.md). Its **automatic** and **incident** modes, two-phase mutation outbox, disputed operations, isolated quarantines, global trust pause and recovery proof are required deployment tests, **not present runtime functionality**.
Push a small authorized task branch -> GitHub Actions runs asynchronously -> track exact SHA + run_id + run_attempt + workflow/job/check source + policy version as a future. **Do not stop merely because CI is running.** While the worker invocation actually remains live, continue safe non-conflicting granted tasks or scoped read-only research/review prep; recheck exact-head CI after genuine elapsed time/useful tool work, and process a terminal result immediately when available. Keep the candidate HEAD frozen. A writing claim can be released or replaced **only through the approved arbiter's task/lease policy**: checkpointing alone does not authorize another writer to edit that branch. If the runtime cannot remain active, store a durable future pointer and reconcile next hourly activation.
Next worker reconciles pending runs against GitHub: success -> VERIFY_READY only if qualifying trusted source, failure -> FIX_READY, skipped/cancelled/stale/unprovable -> BLOCKED or RETRY_ELIGIBLE according to reviewed rules. A raw green check never equals acceptance.
External writes with lost ACK: mark OUTCOME_UNKNOWN, inspect authoritative ref/check/PR using idempotency key **before** retry; do not duplicate commits, workflow reruns or review requests.
Scheduler/task states are *proposed internal v2 states*, NOT silently added to existing `registry/status-machines.yaml`. Add explicit reviewed transitions/migration if adopted.

### 2.5 Review council / guarded integration
In an author run: perform tests and L0/L1; prepare review packet anchored to exact immutable SHA: work/requirements, actual diff, tests and failures, threat model, question checklist; do not include author's persuasive explanation as primary evidence.
A different ChatGPT Scheduled task / different conversation / fresh prompt, with read-only first phase, reviews exact SHA and all required hats, tests and counterexamples. That can be L2 **context-separated evidence** if genuinely fresh and authoring-separated, not merely the author switching persona. Cross-model or Codex credits are not required for technical L2; avoid same worker reviewing its own work even on another activation.
Record reviewer_worker, fresh_context assertion, review_source, reviewed_sha, reviewed norm digests, tests/evidence, findings, outcome and limitations. Because shared GitHub identity cannot cryptographically establish context separation, grade as context-attested rather than hard-verified unless a verifiable independent identity/evidence mechanism is added.
L3 requires multiple genuinely independent contexts and additional adversarial scrutiny; multiplying hats in one chat remains L1. Any material code change invalidates prior exact-head L2.
**Do not equate L2 evidence with GitHub's APPROVED review by a non-author.** Where WORK-0002 or repository policies require an actual non-author collaborator review, integration stays BLOCKED until that separately valid approval occurs. A change to this process requires a dedicated reviewable governance proposal with security impact, owner authorization and live host enforcement.
Integration: at most one integration claim; current main SHA, head SHA, green correct-source required checks, **current authoritative Actions grant generation/attempt** (or fencing token only if the CAS fallback was selected), authorized writes and accepted reviews; merge with expected head SHA and re-check main. No direct main edits; no force push.

## 3. Immediate continuous work within one invocation

Example for worker W1 (select **only required** engineering phases; work continues within the SAME session when available):
```
READ LIVE STATE → RECONCILE → CLAIM TASK-A
  A(scope) → [B(research) if material unknown] → [C(decision) if needed]
  → [D(build) if deliverable includes code] → E(verify) → PUSH
  CI_QUEUED/IN_PROGRESS → TRACK EXACT-SHA FUTURE → KEEP CANDIDATE HEAD FROZEN
     ↳ DO USEFUL ALLOWED WORK (other VALIDLY CLAIMED branch, review prep, research)
     ↳ RECHECK CI/REVIEW AFTER USEFUL WORK OR ACTUAL WAIT (never fake sleep)
  CI_TERMINAL → VALIDATE ACTUAL JOBS/HEAD/SOURCE → FIX/REVIEW/INTEGRATE IF AUTHORIZED
  if runtime exhausted/no eligible action: DURABLE CHECKPOINT → NEXT HOURLY RECONCILE
```
Pending CI/review **alone does not justify terminating** a still-running invocation. Conversely, no prompt can guarantee that ChatGPT stays executing until an arbitrarily long GitHub job finishes. See the operating contract §7A.
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

## 5. Minimal repository implementation layout — preferred proposal, NOT CREATED

**Do not implement the historical multiple-`engine/dev/` CAS services or two parallel "trusted/untrusted" workflow stacks from older sketches.** The first pilot is a small existing-GitHub-native addition and must use an authorized separate implementation WORK/PR, not this documentation PR:

```text
.github/workflows/monde-dev-dispatch.yml   # one default-branch Issue-comment arbiter, after accepted/reviewed deployment
.github/scripts/monde-dev/controller.cjs   # one locally loaded JS module, pure core + Octokit adapter
.github/scripts/monde-dev/controller.test.cjs # node:test 4-worker/race/unknown-effect tests
# optional: one ordinary PR CI workflow if existing WORK-0002/CI cannot provide verified required checks
```

One command Issue, existing WORK/REQ/ADR registry, GitHub PR/CI/reviews and required GitHub Rulesets remain the platform. Exact files, language and action SHAs are finalized **only after T0/T1 connector/event proof**; this list is a small sketch, not a demand to implement every file. Protected promotion must rely on real GitHub host gates. No local server, model API or second status registry.

## 6. Reuse matrix
**NOW**: GitHub refs/commits/PRs/Issues/Actions/Artifacts; existing MONDE registries/templates and an intentionally narrow bootstrap workflow on `main`. Other current candidate-PR checks (including CodeQL on PR #2) are **not automatically trusted default-branch integration gates**. Prefer a `controller.cjs` loaded by pinned `actions/github-script` and tested via native `node --test`, subject to the actual hosted runner/runtime and an independent review. Reuse Python only where tested compatibility with already accepted MONDE governance materially reduces cost.
**SCOPED CI TEST**: actionlint + zizmor (workflow correctness/security), Ruff (Python lint), Hypothesis (concurrency property/model tests), Pyright optionally if benefits are demonstrated. Pin versions and use controlled permissions.
**NOT REQUIRED**: Gas Town, Beads runtime/Dolt, Temporal, OpenHands, mini-SWE-agent, Docker, local caches, Redis, paid reviewer services, new dashboard.
**OPTIONAL FUTURE**: GitHub Projects as human projection, broader static analysis when real product code appears, event-triggered ChatGPT tasks only if verified supported and consistent with four-task limit.
Spec Kit may inform checklist templates, never replace existing MONDE specification precedence.

## 7. Mandatory test matrix before four-worker activation

T01 four starts on same SHA with four independent eligible tasks; 4 distinct claims, zero duplicate.
T02 four starts with only two conflicting write/semantic resources; at most compatible owners.
T03 serialized Actions arbiter: four simultaneous conflicting and non-conflicting Issue requests yield exactly one grant per overlapping resource; if fallback CAS is chosen instead, test same Git-ref-parent sibling commit rejection.
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

G0 **Interactive implementation only:** user directs every development iteration here, on a separately scoped branch/PR. No scheduled-task development or activation until dedicated tests. Confirm WORK-0002/PR #14 state, independent native review and WORK-0003 branch protections; these remain host acceptance blockers. Do not merge untrusted candidate.
G1 **Decide L2 authority migration:** maintain separate L0/L1/L2/L3 definitions and review evidence. Document policy impact of removing Codex *dependency* without weakening GitHub's non-author approval rule. User authorization required for any significant governance rule change.
G2 **Accept spec/ADR only after independent cold read:** do not prematurely mark `WORK-0005` READY/DONE or upgrade policy.
G3 **Pilot pure scheduler with generated fixtures in GitHub Actions:** runs with one worker, 100% meaningful coverage target, no live mutable resources.
G4 **Prove preferred minimal trusted GitHub Actions arbiter** with one default-branch issue_comment trigger, serialized conflicting grants, readback/reconciliation and four synthetic requests; connector permissions and host protection proof. **Per-worker control-ref CAS is an explicit fallback only if this experiment fails**, subject to a new reviewed decision.
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
5. An unverified Actions arbiter grant protocol (or unverified CAS fallback if selected) can corrupt operational task assignment; no claim mechanism is operational until actual connector and concurrency tests pass.
6. GitHub Actions cannot wake or spawn a ChatGPT Scheduled task by writing a file, and CI is not an LLM reviewer.
7. Four tasks on an eligible ChatGPT plan consume a limited active-task budget; other tasks may be affected by account limits.
8. Treating work histories from branch-local stale documents as current could deadlock progress.
9. Too much documentation/validation overhead can prevent MONDE product increments; periodically measure critical path and remove duplicative steps after reviewed risk evaluation.

These are blockers/assumptions to **test**, not claims that the final engine already works.
