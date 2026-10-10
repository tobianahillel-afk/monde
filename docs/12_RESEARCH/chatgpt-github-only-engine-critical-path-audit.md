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

## G2. Four Scheduled tasks: quantitative, falsifiable throughput forecast

**Measured current source-tree baseline** from GitHub recursive tree at `main=b4b52c77...`: 74 Python files (~897,544 bytes); 46 are `test_*.py` files (~646,895 bytes), 28 are other `.github/scripts/` CI/governance scripts (~250,649 bytes). These are **file counts and byte sizes**, NOT a counted number of code lines. **No Python product runtime source outside `.github/` appears in the current tree.** Historical governance files/CI should not be misreported as implemented MONDE World Model product code.

**Nominal capacity:** 4 eligible hourly ChatGPT tasks × 24 hours = **96 nominal scheduled activations/day**, if all four are indeed installed and the scheduler keeps every hourly slot. **Not** 96 guaranteed completed executions, continuous work, four different GitHub accounts, 96 approved merges or unlimited context/tokens. At current official product settings, Plus has up to **5 active Scheduled tasks**, so four workers may crowd out other scheduled tasks. Actual account slots and permissions must be inspected.

**Productivity model** (hypothetical inputs; rolling 7/30-day measured output eventually replaces them):

`Net accepted functional product LOC/day = nominal activations/day × P(actual useful run) × P(unique production-code LOC eventually accepted | useful run) × net new accepted product LOC per such run`.

Here “net accepted product LOC” counts non-generated non-vendored functional code once on an actually approved merged main, excluding test scripts, config and Markdown, mass renames, refactors without new net code, failed branches, unmerged PRs, deletions and duplicate code. A day with six candidates and no approvals yields **zero accepted product LOC that day**; long-window accounting credits actual merged outcomes only. Output can be negative for worthwhile simplification, so assess delivered capabilities separately.

| Scenario | P(useful run) | P(code actually accepted) | LOC per successful code run | Model result/day | Interpretation |
|---|---:|---:|---:|---:|---|
| Constrained startup | 0.35 | 0.08 | 20 | **~54** | Lost/paused runs, research, heavy governance and limited review capacity |
| Working baseline | 0.60 | 0.15 | 35 | **~302** | Mixed research/build/review/documentation, bounded WIP, native approvals available |
| Favorable steady state | 0.75 | 0.25 | 55 | **~990** | Proven task/grant/CI/review integration and frequent small mergeable product slices |

All input fractions and LOC per run are **illustrative assumptions**, not user/account measurements or statistically valid confidence bounds. Real effective output could be **0** indefinitely while required native GitHub non-author approvals are unavailable. No honest claim of 1,000+ LOC every day is possible before measured runs.

For planning only, round the scenarios to **0–60**, **150–400**, and **500–1,000 net accepted product LOC/day**, respectively, *conditional on valid merge flow*. 2 active writers + 1–2 review/research roles may beat 4 simultaneous coders because L2, checks and integration remain bottlenecks. Workers are role-fluid, so this is a WIP cap, not permanent roles.

**Product scale arithmetic (not an estimated MONDE final size)**:
- At ~300 accepted product LOC/day: a 5,000-line isolated prototype takes ~17 productive calendar days, 20,000 lines ~67 days, 100,000 lines ~333 days; research, documentation and experimental failures can increase time.
- At ~1,000/day: 5,000 lines 5 days, 20,000 lines 20 days and 100,000 lines 100 days; *this assumes unusually healthy continuous integrations*.
- A historical discussion estimated ~1.0–1.4 million future runtime LOC for full-scope MONDE, but this is **not verified against a final canonical detailed capability inventory**, and MUST NOT be treated as a target. OSS reuse, model adapters, owned-vs-vendored code, functions reused across engines and deferred capabilities make gross LOC a poor size measure.

### Delivery forecasts — what can start when?

- **MONDE product blueprint documentation:** can start **now** as controlled read-only research and separately governed WORK-0004 capability-family documentation; four production writers are *not* prerequisites. Historical conversation fragments need source-confidence and owner confirmation before normative acceptance.
- **Single-worker isolated Actions dispatcher event test:** **~4–12 focused engineering hours** for T0/T1 after approved workflow access, not a fixed calendar duration. Can be attempted in a safe test scope without all production launch gates.
- **One-worker usable narrow branch/CI/reconcile pilot:** **~20–60 focused engineering hours** including rough exploration and real connection issues (planning hypothesis).
- **Four-worker guarded, recoverable system:** **~60–160 focused engineering hours** including progressive pilots and fault tests **plus** already outstanding WORK-0002/0003 authorization debt, real user-admin settings and non-author approval strategy. Could take **~2–8 calendar weeks if all access/reviews are available**, longer if GitHub/ChatGPT grants or merge authorities remain blocked. These are not guaranteed estimates.
- **First real product code:** can be proposed/experimented on an isolated branch as soon as a precise approved slice, task ownership and safe authorization exist; **actual merge** waits for the existing required GitHub independent approval, trusted CI and main protection. Do not delay all product research until four-worker completion.

**Measurement plan**: for 7 and 30 calendar days capture nominal/successful/paused invocations, minutes of substantive tool interaction when observable, authoring/research/review/time distribution, net merged product LOC (classify source tree), functional acceptance count, PR age, reviewer wait, root-cause retries, CI outcome, API quotas, and incident recovery; do not present costless four-worker scheduling as a guaranteed performance multiplier.

Official constraints sources:
- https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

## G3. LLM/plugin operational friction and *non-measured* time-loss estimates

**Do not describe unobservable model internals as facts.** This is a black-box input→GitHub-tool→observable-action model. The model receives its task instructions and available connected tools, asks for explicit GitHub resources, then creates/checks remote changes. It does **not** automatically inherit all old project conversations or possess a continuously running process between Scheduled invocations. Retrieved GitHub comments/CI logs are untrusted text. A PR metadata lookup is not equivalent to reading a patch.

### Rough loss mechanisms (ranges are hypotheses, not measured percentages)

| Mechanism | Hypothetical share of a bounded run affected | Why it can dominate | Intervention / estimated relative reduction of that mechanism |
|---|---:|---|---|
| Reorientation and repeated document reads | **10–25%** | WORK/read_before plus giant specs, tool calls and stale PROJECT_STATE | 3-tier fetch & scoped WORK digest; **30–60%** fewer avoidable re-reads if routing correct |
| Overdocumentation and status-mirroring | **5–20%** | Same PR/CI/run outcome recopied in WORK, progress, roadmap and PROJECT_STATE | one canonical owner + only material checkpoints; **30–70%** reduction of duplicated status updates |
| Fix→CI→L2→HEAD-rewrite loops | **15–40%** | New commit invalidates exact-head test/review, findings chase unstable design | phase freeze, narrow PR, 2-repeat root-cause trigger; **15–45%** fewer repeated cycles in the target class |
| Duplicate investigation/architecture choice | **5–20%** | Next Scheduled chat repeats choices without accepted ADR/source/evidence | decision digest, stop-search/revisit criteria; **20–50%** fewer redundant research steps |
| Claim collisions / conflicting canonical files | **0–20%** | Four same-snapshot workers, shared docs/semantics and no host-enforced grant | single serialized trusted arbiter + WIP cap; **50–90%** reduction in the duplicate-work component *if proven* |
| Awaiting CI, approvals and app tool permissions | **5–30%**, possibly **100% blocked** | Real external latency/host requirement; no amount of prompts grants second GitHub identity | async CI checkpoint + independent eligible tasks lowers idle time, **but cannot remove actual approval wait** |

These ranges **overlap**, have no empirical frequency base and MUST NOT be added to 100%. Their proposed percentage reductions are *engineering targets/sensitivity hypotheses*, not observed improvement claims. For any individual run, actual loss may be zero or total. A single missing required non-author approval can set delivered accepted code to zero indefinitely.

### One transparent illustrative accounting, NOT a benchmark

Out of a synthetic 100 units of available effort:
- **before**: 45 units on useful engineering+testing, 15 orientation, 10 repeated status/doc tasks, 15 avoidable repeat/review churn, 5 collisions, 10 externally waiting.
- **after under optimistic but testable assumptions**: 66 units on useful engineering+testing, 8 orientation, 5 repeated status/doc tasks, 9 repeat/review churn, 2 collisions, 10 externally waiting.
- This is **+21 points** in useful-work share, or about **+47% relative useful throughput per unit of agent effort** (`66/45−1`), **not** +47% daily code merged. Acceptance bottlenecks can entirely erase that hypothetical throughput improvement.

A conservative time-saving aspiration for the **avoidable** (not fixed security/approval) overhead is **~15–35% less wasted engineer effort in pilot runs**, to be measured and revised. Do not assert a globally achievable percent without real data.

### Experimental measurement during 1, 2, 4-worker pilots

Sample at least **20 actual completed or interrupted activations** across 1–2 workers, then another sample during a safe four-worker pilot; small samples do not provide precise statistical confidence. Record (only observable events):
1. Invocation/run success, pause/approval, actual observed tool operations, file bytes retrieved, unique paths and repeated reads.
2. GitHub action/PR/check/head IDs and when they were first/last observed; no fabricated elapsed think-time.
3. Candidate PR age, revision count, exact-head proof invalidations, failure root-cause categories, reopened findings and duplicate work.
4. Time-to-first-valid grant, number of disputed claims, discovered missing/obsolete tasks and reconciliation success.
5. Work classified as research, decision, docs, code/tests, review or incident based on **actual deliverables**, not model's unverified self-reported thinking duration.
6. Fully accepted product increments (and net merged production LOC as a secondary KPI) per calendar week.

Compare **matched work classes**, not a difficult four-worker science sprint against trivial one-worker formatting. Evaluate baseline vs pilot under the same acceptance and protection policy; stratify by risk and account for long merge/review lags. Collect median and p90/p95 only if sample size supports them. Do not claim a statistically significant speedup from one demo.

### Minimum viable behavior changes before more infrastructure

- Default worker cold-start should require a scoped manifest, not a 60k-character document dump each hour. The operating contract should be a **reference** and a short indexed worker prompt should control navigation.
- Allow role switches **within** one invocation. `RESEARCH → DECIDE → BUILD` does not wait for a new hourly trigger. L2 requires a separate real authoring context and native GitHub approval as independently required.
- On second *same-root-cause* material failure: repro + 3 alternatives + mini engineering decision, then return to eligible code. No generic architecture council.
- Stop research at sufficient credible evidence; stop refactor absent proven benefit; freeze exact candidate HEAD for CI/review; checkpoint and stop on real permission/approval blockade.
- If the process itself generates multiple large research documents per small operational rule, treat **document growth as a measurable regression** and consolidate/update existing accepted references rather than adding another standalone framework.

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
