# MONDE Development Engine v2 — Critical path and anti-overengineering audit

Status: Research / **author-led red-team assessment, NOT independent L2 and NOT accepted policy**
Date: 2026-10-11
Owner: WORK-0005 / [draft PR #18](https://github.com/tobianahillel-afk/monde/pull/18)
Inputs: live repository snapshot (2026-10-11), current accepted MONDE governance, [v2 RFC](chatgpt-github-only-development-engine-v2-rfc.md), [readiness](chatgpt-github-only-engine-launch-readiness.md), [reconciliation](chatgpt-github-only-engine-reconciliation-runbook.md).
Mission: avoid making the development operating system harder, slower or more expensive than the MONDE product it is meant to develop. Zero local server, ChatGPT + GitHub connector + GitHub-hosted Actions only.

## A. Independent facts versus untested hypotheses

**Confirmed via repository API at audit:** `main=b4b52c77fbf05eda65e8f0e951959da70e7edbe7`, `protected:false`, rulesets `[]`; WORK-0002 IN_REVIEW / WORK-0003 PLANNED; PR #2 open with 298 commits/127 changed files; PR #14 open with 44 commits; PR #18 is DRAFT and at last inspection has 11 commits/7 files/+791 lines of mostly design documentation. A draft architectural specification is **not an implemented control plane**. Existing review independence process distinguishes L1 within one context and L2 fresh independent context; a shared GitHub actor cannot furnish a distinct non-author native approval.

**Observed failure pattern:** high revision counts and exact-head L2/CI loops in WORK-0002. They strongly suggest expensive review feedback; they do not alone establish poor code quality or provide a statistically valid probability of future failure. Existing `PROJECT_STATE.md` still documents historically old PR #5 as a future action, whereas GitHub live state is newer.

**Critical design hypothesis to test:** rather than write Git-ref transaction machinery in each ChatGPT task, run a **small, trusted single-writer allocator in GitHub Actions**. Four workers submit well-typed requests via supported issue comments or other verified GitHub event; Actions serializes writes and publishes attributable result. GitHub docs confirm `issue_comment` event and `concurrency.queue: max` capability, but actual ChatGPT connector author identity, event delivery, latency, authorization and no-local-host integration need a live safe dry run. Treat this as *candidate A*, not a proven deployed alternative.

## B. Risk register — rankings are qualitative engineering judgments, NOT calibrated statistical probabilities

| ID | Risk | Likelihood / consequence | Mechanism | Minimum mitigation and falsification test |
|---|---|---|---|---|
| P0-01 | **A3 non-author approval deadlock** | Very high / blocking | Four ChatGPT contexts can share one GitHub actor; independent technical L2 is not a native second account | Separate L2 evidence from approval authority; preserve existing required non-author approval. One actual PR/actor test; do not promise full autonomy if impossible |
| P0-02 | **Unprotected main / privilege bypass** | Current defect / critical | `main.protected=false`; worker prompt is not host enforcement, admin may bypass default rules | WORK-0003 settings through authorized admin, negative tests, current ruleset/branch enforcement readback before any auto merge |
| P0-03 | **Trust-root bootstrapping deadlock** | High / critical | WORK-0002/PR #14 demand independent exact-SHA proof before WORK-0003; adding 15 all-green gates before any prototype creates circular dependencies | Phase-specific gates: read-only/isolated tests allowed early; protect main before merge; separate WORK-0002 closure from narrow design prototype; explicit owner-approved precedent only, never false DONE |
| P1-04 | **Review–fix–CI infinite loop** | High / high | Every changed SHA invalidates exact-head proof and reviewed scope; same-author retries generate more findings | Freeze candidate after last material change; CI then fresh independent review; append run-status evidence to PR/issue (not tree); bounded failure budget => architecture/root-cause decision |
| P1-05 | **Overengineering distributed claims** | High / high | Four chats implement CAS, event-sourcing, fencing, expiry, outbox, GC and conflict merge themselves | Benchmark central **trusted Actions single-writer** arbitration FIRST; retain no-force Git ref CAS as fallback; only preserve hard security guarantees at merge boundary |
| P1-06 | **False ownership despite claim** | Medium-high / critical | Same permissioned GitHub actor can push after lease expiry; self-declared fencing cannot block API writes | Treat expired branches as untrusted candidates; protected main gate independently checks active epoch/head/allowed diffs; explicit cooperative vs host-enforced guarantee |
| P1-07 | **No CI from tool-issued changes** | Medium-high / high | GITHUB_TOKEN-created events usually do not trigger downstream workflows; `workflow_dispatch` checks may not qualify as PR required checks | Verify connector actor and events with isolated issue-comment+PR tests, use appropriate `pull_request` gates; never infer from workflow green alone |
| P1-08 | **Queue events lost/replaced** | Medium-high / high | Actions concurrency default has just one pending; `queue:max` buffers up to 100 but scheduling order is not guaranteed | Set appropriate `queue:max`, `cancel-in-progress:false`, stable idempotent request ID, scan all missed requests; queue saturation test |
| P1-09 | **Document-source duplication** | High / high | WORK YAML, issue labels, PROJECT_STATE, RFC, control ref and PR narratives all become competing status authorities | One canonical normative registry, one operational owner, GitHub live sources for checks, generated views; remove state-only HEAD rewrite |
| P1-10 | **Four agents increase WIP, not throughput** | High / high | Reviews / trusted merges form bottleneck: arrivals increase but service capacity does not | Hard cap 1 integration candidate + 1–2 open writers; prioritize FINISH > START; measure accepted merges per day and READY→MERGED latency |
| P1-11 | **Prompt/tool approval or connector gap** | Medium-high / blocking | Scheduled task may not have unattended GitHub write ability, consistent permissions, timely wake or required API surface | First run ONE read-only scheduled invocation; then a low-risk authorized write and event proof. No promises before observed runs |
| P1-12 | **Workflow injection / false-green** | Medium / critical | Untrusted issue comments, PR diff, workflows or scripts affect privileged Actions context or status reporting | Trusted default-branch workflows, narrow token permissions, schema validation, no untrusted code under elevated `pull_request_target`; verify check app/event/source |
| P1-13 | **Reconciliation complexity trap** | High / high | Trying to guarantee exactly-once delivery across GitHub API, workflow and chat lifetime is impossible as a primitive | Target idempotent logical outcomes, append an outbox only around real ambiguous side effects, bounded recovery; quarantine unknown rather than universal retry |
| P2-14 | **Documentary process tax** | High / medium-high | Tiny fixes require REQ/ASM/RISK/ADR/TEST/REVIEW/PROJECT_STATE edits; reviewers restudy huge context | Risk-weighted templates, 1 work record + 1 PR + targeted tests; ADR only crosscutting decision; concise generated handover, not full re-read |
| P2-15 | **Coverage as endless release block** | Medium / medium-high | 100% line/branch can be achieved on trivial mocks or be costly on defensive integration code | Keep coverage floor and reviewed justified exclusions; also invariant, mutation/fault and actual GitHub contract tests; no blanket full repository suite for every docs typo |
| P2-16 | **Review independence misclassified** | High / high | One ChatGPT changes persona from A to B in same conversation, then labels self-review L2 | L0/L1 in same invocation; L2 another fresh conversation with actual diff/requirements and reviewed SHA; label evidence as context-attested if same GitHub actor |
| P2-17 | **Time and quota misconceptions** | High / medium | 4× hourly triggers interpreted as uninterrupted agent-hours; delayed executions and model quotas prevent throughput guarantees | Per-activation budgets and checkpoints; allow 24h gaps/DST; track successful useful outcomes per wall-clock week, not number of invocations |
| P2-18 | **Requirements frozen too early** | Medium / high | Accept sprawling v2 state-machine/15 gates before feasibility tests; change requires costly ADR migration | Keep the RFC proposed until empirical 1-worker spike; freeze only invariants and accepted decisions at exact revision, not speculative implementation mechanisms |
| P2-19 | **Review scope amplification** | High / medium-high | A3 assigned to all changes, same six hats for small docs change, new reviewer always finds different nonblocking detail | Predeclare change class and risk; document appropriate independent hats; block only material/required findings; tracked low-risk follow-ups when policy permits |
| P2-20 | **MONDE product starvation** | High / very high opportunity cost | Development engine consumes most of agent time while data→evidence→temporal world→query products stay unimplemented | Define fixed engine timebox and acceptance cutline; first product vertical slice as top queue priority once minimal runner ready; pause engine scope growth |

## C. Candidate architecture comparison — prioritize experimental simplicity

### Candidate A — Trusted GitHub Actions serialized allocator (recommended **first experiment**)
Four ChatGPT contexts send strictly typed `CLAIM_REQUEST` messages, not free-form instructions, through an empirically verified GitHub app event (e.g. a dedicated issue's `issue_comment`). A **single trusted workflow on default branch**, concurrency group fixed and queue `max`, enforces author/token allowlist, schema, requests IDs, work DAG and conflicts, writes one durable authoritative grant/result. Workers poll a bounded number of times if still active, otherwise pick up grant at next scheduled invocation. Same trusted job or a separate narrowly-permissioned gate reconciles CI and prevents stale HEAD promotion.

Advantages: no ChatGPT participant implements a distributed lock; GitHub Actions acts as deterministic bounded computation, not a fifth AI reviewer or local machine. Risk: eventual wake-up, missing event, queue length/saturation, stuck job, actor/auth verification, privileged workflow compromise, evidence propagation delay. Cannot guarantee a same-hour review starts; can guarantee durable next-run visibility if the workflow and API behave as tested.

**Minimal proof steps** (no production work mutation): introduce trusted dispatcher only via protected reviewed PR; use separate synthetic sandbox issue; publish four competing structured requests; prove dedup, resource exclusion, unexpected-actor rejection, response-after-timeout, recovery sweep, `queue:max` behavior, auth and GitHub-token event constraints. If issue comment cannot reliably trigger or be authenticated, stop and compare candidate B.

### Candidate B — Dedicated append-only control branch + CAS per worker (fallback)
Four ChatGPT agents read authoritative control ref, create single-parent child event commits and advance via non-force Git ref update with connector-specific expected SHA; lose-and-reread on conflict. Copes with same-trigger workers without a central Actions process, but task writes, expired writers, leases, cleanup, event compaction and permission guarantees become more complex. Accept only after exact connector CAS tests and protected integration source.

### What NOT to add in v2
No Beads/Gas Town service, Temporal, Dolt, Redis, own merge queue, Github Projects as second state authority, universal workflow orchestrator, external Codex billing, standalone dashboard, generalized model router, elaborate AI personalities, continuously rewritten `PROJECT_STATE.md` and no full synthetic world benchmark as a prerequisite.

## D. Reduce the state machine and avoid recursive reviews

Minimum **operational** phases for v2 prototype: `UNCLAIMED → CLAIMED → CANDIDATE_READY → REVIEW_PENDING → MERGE_ELIGIBLE → DONE`, plus orthogonal `BLOCKED/UNKNOWN` and `attempt/head/epoch`. Detailed GitHub checks are **external observations**, not duplicated truth fields. Model cancellation, lease recovery and denial as evidence transitions rather than fourteen competing status labels. This is a proposal only; existing WORK lifecycle remains untouched.

Recommended bounded change process:
1. Plan one smallest acceptance slice and fixed `read_before`.
2. Research/BUILD/TEST, fix local defects, then **freeze substantive HEAD**.
3. Run required exact-head CI; obtain a different fresh-context L2 on the frozen artifact where policy requires.
4. If a material finding: patch, recompute only affected proofs, refreeze and re-review. If same root-cause cluster repeats after **two materially unsuccessful corrective attempts** (heuristic to validate), stop patch churn and trigger a focused architectural diagnosis; do not reset unrelated requirements.
5. Merge only after externally enforced eligible checks and separate non-author approvals where required; otherwise record blocker and work on independently eligible tasks.
6. Never commit a new summary just to say that the preceding exact-head validation succeeded.

## E. Phase-specific gates instead of a single 15-gate deadlock

Keep all 15 evidence gates as **full `ACTIVE_4` criteria**. Do NOT require them all to perform safe preliminary research:
- **G-R / READ_ONLY:** permission to inspect public docs/PRs and produce an isolated research proposal. No mutable claim or merge. Can start immediately.
- **G-S / SINGLE_SANDBOX:** verified connector permissions + isolated branch/issue + low-risk tests; no direct main, no trusted gate mutation, no promotion. May run before A3 architecture finalization if expressly scoped and not called production.
- **G-2 / PILOT_2:** trusted dispatcher or CAS test proof, actual GitHub protection, separate resource grants, bounded workflow test; no unattended high-assurance merge.
- **G-4 / ACTIVE_4:** all applicable full release gates, proven reconciliation, live approved policy + host authority, measured throughput and rollback.

This avoids assuming WORK-0002 must be DONE before it is possible to **research or test** the engine. It does not authorize merging an unprotected or unreviewed trust-critical component.

## F. Evidence strength and scientific measurements

Do not claim a numerical collision probability or throughput multiplier without a recorded trial. Use:
- **safety:** illegal double grants, stale-candidate promotions, lost acknowledged writes, unauthorized merges; target zero in controlled adversarial trials;
- **liveness:** 95th percentile request→grant, candidate READY→merged, independent review wait, recoverable interrupted run rate;
- **productivity:** genuinely merged and accepted product capabilities per day/week, reproducible regression count, repeated PR review cycles and A3 bottleneck;
- **cost:** ChatGPT invocations, GitHub API calls, Actions CPU minutes, percentage time reviewing/docs vs feature code.
- **experiment:** one-worker baseline; two-worker simultaneous controlled test; four-worker adversarial rehearsal; use same backlog/task classes and stable acceptance rules; no synthetic win can substitute for real end-to-end GitHub results.

Suggested trigger for reducing v2 scope (policy proposal): if **two consecutive weekly measurements** show no improvement in accepted MONDE capability throughput, or repeated P1 integration stalls, stop expanding the engine and perform a root-cause/simplification review. Do not abandon mandatory security controls.

## G. Effort estimates — scenario ranges, not measured predictions

Units below are **focused engineering hours**, not guaranteed elapsed ChatGPT hours; no scheduling overhead or reviewer queue included:
- Reconcile design + choose trusted GitHub Actions allocator vs CAS, focused ADR: **4–10 h**.
- Minimal deterministic task selector + existing WORK adapter + tests: **6–16 h**.
- Event trigger/grant control prototype and real permission proofs: **8–24 h** if Actions works; CAS/ref variant can be **20–50 h**.
- Bounded reconciliation (CI exact-SHA, ambiguous mutation, stale grant): **12–30 h**.
- Review packet / minimal independent-context technical L2 handover + actual authority checks: **6–16 h**; native non-author approval may require an unavailable distinct actor, so completion time is unbounded until resolved.
- 1/2/4 worker trials, faults, CI and fixes: **10–30 h**.
- Existing WORK-0002/PR #14 debt and WORK-0003 administrator protections are **outside these new-code estimates**; they can dominate elapsed time.

Totals based on independent rough ranges and overlapping tasks: **~45–125 focused hours for a deliberately minimal Actions-led engine**, perhaps **~80–220 hours** for a bespoke per-worker CAS/event-sourcing design. These are subjective pre-implementation planning intervals, not statistically calibrated confidence intervals. Real elapsed calendar time with hourly bounded ChatGPT tasks, human approval, delays and CI can vary widely: **roughly 1–3 weeks favorable, 3–8 weeks plausible, >8 weeks or indefinite if the independent approval gate cannot be satisfied**. Avoid interpreting four workers as 4 continuously productive full-time developers.

**Fastest path:** pilot 1 worker + existing canonical governance + read-only coordination first, then a central low-risk Actions dispatcher. Every skipped orchestration feature must preserve fail-closed main integration and required review authority.

## H. Concrete next decisions

1. **Hard architecture fork:** small trusted GitHub Actions allocator pilot vs CAS-per-chat. Bench both only if A fails or costs no more total work; do not implement both production solutions.
2. **Approval authority fork:** define how required native non-author approval is legitimately provided. Technical L2 via another chat alone is not enough where an actual different GitHub actor is mandatory.
3. **Governance simplification fork:** separate risk-tiered gates from endless author/review-driven HEAD mutations; accepted policy must be revised explicitly, never silently bypassed.
4. **Documentation authority fork:** stop copying volatile status into canonical docs; compact run records once per meaningful transition, references to live GH run/PR.
5. **Product cutoff:** freeze scope after a 1-worker end-to-end demo, protected merge checks and recovery proof; return to MONDE feature development as soon as safe.

## I. Official GitHub behavioral references

- REST Git ref fast-forward semantics: https://docs.github.com/en/rest/git/refs
- GitHub Actions issue_comment event (default-branch workflow): https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Actions concurrency `queue:max` and no dispatch-order guarantee: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- `GITHUB_TOKEN` event recursion restrictions: https://docs.github.com/en/actions/concepts/security/github_token
- Required checks and skipped/dispatch workflow incompatibilities: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- Protected branch/rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- Untrusted code on privileged workflows: https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target

**This is a critical analysis and test plan, not a completed L2 review, deployed scheduler, authorization to merge or accepted rewrite of current MONDE policy.**
