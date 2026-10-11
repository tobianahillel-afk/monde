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

## G4. Bootstrap faster: one writer vs four premature writers vs 1+3 mixed

**Comparison assumes** same MONDE repo, same current accepted quality gates, current public GitHub Actions standard runner access, one shared GitHub actor across four ChatGPT chats, no paid API/Codex, and ability to use the connector in the actual Scheduled execution **not yet empirically proved**. Engineering hours are human-equivalent *focused task effort* (research, code, tests, review), **not measured ChatGPT runtime**; the current WORK-0002/3 backlog and human-admin/non-author approvals are separate and may dominate/invalidate calendar forecasts.

| Bootstrapping strategy | What it really entails | Added engineering effort to guarded 4-worker pilot (subjective planning band) | Relative calendar speed if reviewed tools available | Verdict |
|---|---|---:|---|---|
| **A — one writer first** | Manual GitHub task scope; one actual connector T0/T1 proof; implement and test arbiter once; gradually test 2/4 | **60–160 focused h** | Roughly **3–8 weeks** at intermittent bounded Scheduled-task productivity; not guaranteed | Safest default, predictable |
| **B — four unconstrained writer tasks NOW** | No tested allocator, no protected main, uncertain plugin approvals; collisions, stale heads, divergent designs/reviews | **70–220+ focused h**, possibly no legitimate merge | **Potentially slower than A; unbounded blocker** | **NO-GO** for write-capable workers |
| **C — one writer + up to three read-only researchers/reviewers** | One authorized scoped writer on actual GH branch; three chats examine independent WORK-0004 capabilities, contracts/algorithms and other-author L2 while writer builds arbiter | **55–145 focused h** across all contexts (research integration still costs); possible **20–45% shorter elapsed critical path** than A if independent review can be obtained | Roughly **2–6 weeks**, plus approval bottlenecks; 20–45% is hypothesis | **Preferred phased bootstrap**, not an asserted performance fact |
| **D — no controller, product research first** | One interactive/current authorized chat and 0 custom runtime code, WORK-0004 evidence inventory in parallel | **0 development-engine runtime hours** | Product research starts **immediately** | Best to begin MONDE documentation |

**More informative subtargets**: first read-only GitHub/Scheduled connector proof **~2–6 focused h** if permissions work; first event→default-branch Actions synthetic proof **~4–12 h** *once a reviewed workflow can be deployed*; basic 1-writer branch/CI/reconciliation pilot **~20–60 h**; four-writer trusted end-to-end **~60–160 h** including fault injection, not counting backlog/dependencies. These are overlapping stages: **do not add** the subtargets as separate costs to a quoted four-worker total.

**Why four writers do not quadruple engine speed**: engine code is a very small sequential trust-root component; work cannot be parallelized into four simultaneously independent implementations without extra cross-check/integration. Approval of `main`, actor identity, privileged workflow trust, T0/T1 event delivery, test fixture choice, and stable API schemas are *serial gates*. Parallelism pays most for **WORK-0004 historical product inventory, source checking, cold-read, technology research, independent tests**, not for four agents all rewriting `dispatcher.yml`.

**Early high-value run assignment example** (logical tasks, not authorized current production):
- Writer W1: connector proof and tiny Actions dispatcher only under accepted, scoped GitHub authority.
- W2: read-only GitHub checkout/branch-protection/API threat model and minimal test fixture critique.
- W3: WORK-0004 product capability family inventory and historical-source/provenance audit.
- W4: independent, different-chat cold-read of W1 candidate, or review of product/requirements gaps. Technical cross-chat L2 **does not create different native GitHub reviewer actor**.
- Rotate freely *after each completed task*; four fixed roles are a **temporary bootstrap handoff**, not permanent worker personalities.

**Capacity/account constraint verified as of 2026-10-11**: Plus currently allows up to 5 active Scheduled tasks (official help), and the account had 1 active scheduled Mariage OS task with previous MONDE task paused. Four MONDE tasks would use all remaining capacity. **Do not create all four just to verify connectivity**; one read-only Scheduled pilot first, and preserve existing tasks.

**Better still**: a GitHub PR event-triggered ChatGPT Work task is an officially supported feature for eligible connected GitHub/Work installations. It *may* eventually reduce review polling, but GitHub PR activity events are not a generic issue-comment command channel and it is **not** a proven free fifth independent L2/second GitHub actor. It would compete with active-task limits; therefore **not a v2 dependency**. Evaluate later only if a measured CI/review wait is bottleneck.

### Critical-path calculation rather than worker count theater

Elapsed delivery time is bounded by:
`T = serial setup/owner approval + max(parallel research, controller coding) + integration reviews/CI + fault-pilot + unknown tool waits`.
The critical serial steps cannot be accelerated by scheduling four ChatGPT workers on the same hour. Raw `4 × 24 = 96` nominal starts/day has no empirically established mapping to hours of effective code edits.

**After v2 activation (hypothetical)**: previously defined conditional **~150–400 net newly merged functional product LOC/day** is a middle scenario, **500–1,000/day** a favorable high-throughput integration scenario, and **0/day** is possible if the actual approval gate blocks merges. Distinguish high-quality validated tests, docs and reductions in owned code from new LOC. Review bottleneck/approval is often tighter than writer throughput; build an accepted product slice and measure 7/30-day actual outcomes before scaling.

**Documentation lead time**: product/WORLD blueprint research may start now **without four-worker control-plane or even four Scheduled tasks**. A bounded capability-family map and a first approved narrow vertical slice might take **~1–4 weeks** of concentrated, sourced work if old intent is accessible and independent review is available; the **exhaustive historical WORLD/MONDE capability inventory** could take **many additional weeks/months** and has no justified finite completion date before the full evidence/source census. Avoid gating *all* product implementation on every feature being documented: accepted contracts for the **specific slice** are enough where existing PHASE-0 rules allow implementation.

### What is still capable of making every time estimate meaningless?

**A. Host authority**: current `main.protected=false` and rulesets `[]`; no automatic unattended safe merge. Different ChatGPT contexts with one GitHub actor cannot satisfy native non-author review.

**B. Scheduler/plugin write actions**: official Scheduled docs say write actions can pause for human permission; existing installed plugin in this interactive conversation does not prove auto-permission in scheduled Work tasks.

**C. Historical sources**: four Scheduled tasks do not automatically access all private Project chats/files; WORK-0004 must canonize or mark inaccessible evidence, preserving private data.

**D. Artificial time pressure**: 5/10/30-min CI jobs can outlive ChatGPT session. Never end *voluntarily* merely because CI pending, but do not claim nonexistent persistent worker life; record exact future and resume. A Github PR Work event trigger may help a specific measured review gap, not replace full guarded integration.

**E. Output incentives**: a raw LOC target causes scaffolding, mock tests, duplication and parallel unused abstractions. Track accepted capability/throughput and regression first, net merged functional LOC second; avoid model-generated code that fails reproducibility or outside-bounds science checks.

## G5. Maximum deliverable code throughput — refine the old conservative baseline

**The prior ~150–400 net accepted product LOC/day is a conservative early operating scenario, NOT an inherent model output limit, maximum or production target.** It assumed substantial research/review and a low probability of a useful code contribution per hourly activation. A model may generate thousands of lines of text in an activation; text generation is not the hard engineering constraint. The actual constraining path is executable correctness, user-intended capability, exact-head CI, review, conflict-safe merge and stable maintenance.

**Sensitivity if integration/approvals actually work:** 12, 24 or 36 productive **eventually accepted code activations** among 96 nominal hourly starts, at 80/150/250 *unique net accepted product LOC* each, imply respectively **960 / 3,600 / 9,000 lines/day smoothed across the integration window**. These numbers are *unmeasured constructed input assumptions*. The upper illustration is not a validated forecast, and acceptance often occurs on bursts rather than steadily per calendar day. If host/native approval is blocked, actual merged accepted LOC stays at zero regardless of raw generated volume.

**Targets must be conditional:** a proposed **1,000–3,000 net functional accepted LOC/day exploratory target** after proving a stable flow is more ambitious than the old initial scenario and should be tested, not promised. **5,000–10,000/day** could appear for repetitive, well-specified adapters or short bursts with low coupling and reviews keeping pace, but it is not justified as a sustainable entire complex scientific World Model production rate. Generating 20,000 lines of stubs, tests, vendored code or schema bindings in one action does **not** mean 20,000 lines of working novel World Model capability.

**Levers ordered by practical value and zero extra infrastructure:**
1. fix the *native GitHub independent approver and protected main* serial trust gap. This dominates every LOC rate; no four-ChatGPT trick bypasses host identity.
2. reuse original code, scientific libraries and MONDE contracts instead of custom implementing entire subsystems. Reducing owned LOC is a success when behavior is equivalent and maintainable.
3. pre-contract independent vertical slices, static assignment first, and two active feature branches max until collision-free dynamic arbitration measured. Finish ready PR before making new PRs.
4. use connector-exposed `create_tree` + `create_commit` + `update_ref` to batch multiple relevant code/test/docs files into a coherent scoped commit **only when actual tool capability and ref safety verified**; avoid one-file-per-commit cascading CI/review invalidation. No unbounded mega-diff.
5. run cheap fast targeted feedback while building, **all Accepted-required checks at final frozen exact-head**; start independent fresh-context review preparation during CI.
6. keep short GitHub startup manifest, decision status and next action rather than full 84KB operational contract and repeated 50KB governance files each hour; GitHub live state is still mandatory.
7. use generators/templates for truly mechanical sections but account them separately from new product LOC; require deterministic regenerate+contract tests.

**Counterfactual tests on known project risks:**
- wrong/old CI head → no promotion; recheck actual run source/head; batch revisions to limit invalidations.
- repeated same-category review cycle → root-cause rearchitecture before another similar author patch; no weakening L2.
- missing non-author approval → stop affected integration and continue honest product research/other eligible work; do not falsify APPROVED.
- two workers overlap file/semantic contract → one gets no authorized grant, others remain on disjoint work.
- GitHub `403/429` secondary limit → honor `retry-after`/backoff; no burst mutation storm.
- 10/30-minute Action still running → productive related granted work and real rechecks while session active; exact future checkpoint after true limit.
- user intent untraced → consult accepted CAP/REQ then WORK-0004 retrieval, no speculative World Model side branch.
- large generated patch with weak/placeholder tests → reject for insufficient behavioral acceptance, independently derive adversarial tests.
- fully frozen design that performs poorly on real distribution → targeted benchmark and reviewed change, not forever tuning a faulty strategy.

**Why “ensure the blockers never happen” is not an implementable guarantee:** GitHub and ChatGPT service outages, human approval, rate limits, flaky dependencies and scientific unknowns are external. We can **prevent known unsafe side effects and bound recovery/rework**, not promise zero failures or 24h-per-day continuous ChatGPT reasoning. Any throughput target must include the number of accepted slices and unresolved risk, not just newly typed LOC.

## G6. ROOT CAUSE OF REJECTED CODE — live GitHub evidence and the smallest preventative controls

**2026-10-11 live audit, not a model guess:**
- `WORK-0001` is already **DONE**, not a task that can be meaningfully "paused"; `WORK-0002` is **IN_REVIEW**, `WORK-0003` is **PLANNED**, `WORK-0005` is **PROPOSED**. `main.protected=false`, repository rulesets `[]`.
- **PR #2** HEAD `2e2664ca8c9cb4f3eb81ea41a172da1ed7fbaf32`, **298 commits, 127 changed files**, ~22,080 lines added; **73 GitHub review submissions**, all `COMMENTED`, and **104 of 125 PR review threads currently unresolved** (may include outdated/nonblocking threads; not a count of verified current defects).
- **PR #14** HEAD `34e7b07ff5683f8128fafe0bf74810efe3a00373`, **44 commits**, **21 of 24 review threads unresolved** (same qualification); selected CI checks succeeded, but no native APPROVED reviews observed in its listed submissions.
- PR #2 check `Governance core / Deterministic governance` failed in Actions run **37849674798**, job **113560978657**, with **four registry reference errors** from `registry/work-items/WORK-0002.yaml` and `registry/reviews/REVIEW-0094.yaml` referring to absent `REVIEW-0095`; downstream `MONDE / Merge Gate` job **113561113576** failed because governance-core failed. The failing check was not evidence that GitHub needed to execute more generative LLM code: **referential consistency was missing before the expensive integration stage**. This is evidence for a high-value *preflight* and absence of a clean candidate, not a diagnosis that all historic PR findings have the same cause.
- Accepted `docs/13_QUALITY/definition-of-done.md` demands 100% meaningful project-owned line/branch coverage target or reviewed exception, meaningful tests and risk-targeted independent review. Accepted `review-council.md` fixes L2 independence/digest exactness; Accepted `development-process.md` supplies ordered gates and mandatory auditability. **Do not silently lower these Accepted obligations**.
- PR #18 itself now has a sizeable, still Proposed spec on a branch without generic docs PR CI; it demonstrates a **documentation-generation feedback loop**, not a deployed v2 engine.

### Failure tree (cause → avoidable waste → correction)

| Root cause | Visible symptom / rejection mechanism | Tiny preventative quick win | Limit or prior authority |
|---|---|---|---|
| **1. Missing independently frozen contract/test oracle** | Semantics and examples drift after code/review, so new findings cause costly rewrites | **Definition of Ready card:** `WORK/CAP/REQ + exact expected behavior + 3 representative negative cases + impacted contracts + applicable assurance`; for A3 trust-root **adversarial design review before implementation** | Existing Accepted REQ review/approval remains mandatory; a card is routing, not a second registry |
| **2. Structural validity checked late** | Dangling `REVIEW-0095` references, malformed YAML, missing required path/check trigger | **Preflight in branch BEFORE review/frozen CI:** syntax + referenced IDs + file/semantic scope + test discovery, reusing the **existing** MONDE governance validator and fast unit subset. Confirm error-free snapshot then batch publish | Do not run PR-controlled code with privileged tokens; trusted validation boundaries persist |
| **3. Reviewer and author disagree about trust boundaries** | Long chains of new security findings about executing candidate scripts or consuming candidate lockfiles in privileged validator | **1-page trust model first:** explicit candidate/untrusted vs protected/default-branch source, GitHub_TOKEN permissions, check-source authenticity, file/branch write boundary, 2–3 injected negative cases; cold-read before implementation | Correct real P1/R0 findings, do not dismiss the review or grant author approval |
| **4. Candidate HEAD churn and huge mixed PR** | Same PR accumulates many commits and stale exact-head check/review proofs | **One cohesive vertical slice per PR**, batch Git tree/commit operations when supported, stable `review-ready` SHA, parallel L2 prep + CI only then; no status-only code commit | New snapshot invalidates substantive exact-head proof; do not hide or squash historically required evidence without reviewed migration |
| **5. Non-author GitHub approval and unprotected main** | No legal merge even if model-generated code is good and code checks pass | **Owner/admin prerequisite:** configure effective public-repo ruleset and identify eligible distinct GitHub reviewer early. Use separate ChatGPT context for technical L2 independently | Cannot be implemented by W1–W4 sharing one GitHub actor; cannot be bypassed by faster codegen |
| **6. Over-modeling coordination before useful work** | 2,000+ lines of RFC/spec, no running dispatcher, repeat reading 70–85 KB documentation | **Stop adding orchestration features**. Start WORK-0004 inventory/low-risk read-only research now; implement only the event/request/grant controller required by proven second-writer concurrency | Actual protected four-writer launch still requires governed review and negative T0/T1/T2 tests |

**Operational lesson:** prioritize **prevention of rejection in the first 5–10% of a task's execution**, not maximizing corrective throughput after the same defect has propagated through dozens of commits and later reviews. The point of `preflight` is **routing to existing validators**, not a parallel custom QA engine.

### A tiny Ready-to-Build gate, reusing what MONDE already owns

Before a worker performs material code implementation, answer just six yes/no/unknown questions in existing WORK/issue or PR:

1. `INTENT`: is the target CAP/REQ/AC actually supported and sufficiently accepted for the authorized change?
2. `INTERFACE`: who owns changed contracts/files/semantic resources and what are the permitted dependents?
3. `ORACLE`: can independent test inputs, expected outputs and at least meaningful failure cases be stated now?
4. `TRUST`: are API/token/provenance/security boundaries explicit for A3/A4, or genuinely inapplicable?
5. `PREFLIGHT`: do cheap syntax, reference, scope and relevant subset tests pass on the actual candidate?
6. `ACCEPTOR`: is there a **real route** to the required CI/L2/native non-author approval and eventual merge?

If `1–4` are material UNKNOWN, research/specify first; don't speculate code. If `5` fails, diagnose/repair before requesting review. If `6` is blocked, prefer source research/test preparation on an isolated branch and DON'T label the product accepted; do not create a pile of permanently unmergeable feature PRs. For trivial local changes, this can be a 30-second internal check, not an issue template or formal ADR. Do not add a new persistence schema.

**Root prevention vs runtime**: the quick win is *one reviewer test-case pass at the beginning*, *one targeted preflight before CI*, and *one viable host approval route*. No custom dev-engine service needed to obtain this benefit.

### Pausing WORK-0001/0002 does NOT remove their gates

`WORK-0001` is **DONE** and must remain done. `WORK-0002` is **IN_REVIEW**, its candidate validator/merge protection functionality is still needed to make a high-assurance V2 safely accepted. **Owner may reprioritize and temporarily park further speculative WORK-0002 feature expansion after a reviewed stop boundary**, preserving its failing CI, unresolved findings and traceability. Do not silently set `DONE`, `BLOCKED`, drop checks/review requirements, or delete prior evidence. `WORK-0003` host ruleset settings and native reviewer authorization are still preconditions, and cannot be postponed *if* fully automated trusted four-writer promotion is expected.

The fastest *safe* switch is **parallel research/design (WORK-0004/0005) plus a separately governed tiny V2 T0/T1 prototype**, without claiming V2 trusted merged/deployed before WORK-0002/3. A governance scope/priority change belongs in a separately reviewed authorization. Merely changing the worker prompt does not permit breaking this dependency.

### MVP contraction: the Development Engine is a protocol, not a product platform

**Zero custom runtime for single writer**: one scoped branch, GitHub Issues, existing WORK registry, existing trusted validators, existing approvals and a concise 20–40-line startup prompt.

**Smallest genuinely multi-writer v2 controller only if required**:
- one default-branch GitHub Actions `issue_comment` handler restricted to one dispatch issue, serialized by GitHub Actions concurrency, with 2 small tested pure functions: `choose(eligible,active_claims,write_sets)` and `reconcile(live_issue_results,refs,run_attempts)`;
- a minimal typed claim/grant record in GitHub Issue comments; **do not create a distributed ledger, custom queue/cron service, project dashboard, own git-CAS service or another state machine**;
- a normal PR CI workflow only if existing WORK-0002 check set cannot satisfy actual requirements (reuse instead);
- four interchangeable Scheduled prompts differing by label, live state and scoped pointers. **No automatic reviewer or native approval invented**.

**Risk-weighted development effort, hypotheses and exclusions:**
- **0–4 focused engineering hours:** ready-to-build/preflight/checklist and WORK-0004 research without new executable orchestration; this is a process improvement, not a host-granted writer.
- **4–12 hours:** one Scheduled ChatGPT connector T0/T1 probe (subject to actual workflow review/permissions).
- **12–35 hours:** an isolated serial Action command/grant prototype with deterministic resource-collision tests and basic future lookup, **not trusted four-worker launch**.
- **24–70 focused hours total:** optimistic technically functional minimal controller + 1/2 worker pilots if source event/permissions work; review/host administration additional and may dominate.
- **50–120+ focused hours total:** production-qualified four-worker orchestration, long CI/review-future recovery, negative spoof/stale/reclaim tests and actual main rulesets, **excluding indefinite WAIT for eligible distinct GitHub reviewer or unresolved WORK-0002/3**. These ranges are *unmeasured engineering planning estimates*, not a promised calendar duration; overlap, DO NOT SUM.

**Falsifier:** if a real 1-writer→2-writer pilot shows controller overhead + review delays greater than accepted product delivery gained, keep one authorized writer and three source/review roles. Do not continue building speculative v2 infrastructure because a roadmap said "four agents".

## G7. Four-worker mini-engine: independent bottom-up sizing, not a two-worker target

**Target:** one controller that works for all **four** Scheduled ChatGPT tasks; one/two-worker runs are pilot tests only. Existing Accepted Definition of Ready, Specification Quality, Review Council, WORK/REQ/CAP/TEST/REVIEW templates handle MONDE documentation. The engine routes four workers to those artifacts, not a second documentation platform. Complete global blueprint inventory (WORK-0004) is not a prerequisite for implementing a sufficiently specified, properly accepted independent feature slice.

**Minimum code proposal:** one default-branch issue-comment GitHub Actions workflow (~60–120 YAML lines), one local JS controller using `actions/github-script` and Octokit (~180–450 lines), Node built-in tests for four simultaneous requests, collision/stale/unknown outcomes (~300–750 lines), and only small updates to the existing common worker prompt. **~540–1,320 total source/workflow/test lines is a design estimate**, not a size target. Python governance tooling already exists; compare a single-language JS approach against Python reuse through T0 rather than building both runtimes.

**Engineering estimate from constituent proof activities:** connector-to-Actions event and permissions (4–10 focused hours), grants/eligibility logic (8–18), four-way adversarial tests (8–20), late CI/review checkpoint reconciliation (6–16), four real worker pilots (8–20), trusted deployment/reviews (6–20). **Sum: ~40–104 engineer-equivalent focused hours** for a four-worker working mini-engine, *conditional on real app access and qualified review*. Roughly 1–3 favorable or 2–6 more cautious calendar weeks **after** GitHub administration/review prerequisites are satisfied; external approval can block indefinitely. These are bottom-up hypotheses, not real ChatGPT session durations.

**Review effort reuse, not approval reuse:** before any full review, use linked existing WORK.review_plan.completed_reviews, REVIEW-* scope/actors/roles/current normative REQ digests, TEST-* and GitHub review threads. Preserve exact HEAD, files/contracts/risk categories covered, tested adversarial cases, unresolved findings, explicitly uncovered areas and conditions that would invalidate the analysis. Reuse unchanged analysis; inspect deltas when valid; conduct complete new review for changed trust/world semantics or unknown coverage. Existing exact-HEAD/independent-authority gates still apply and old COMMENTED reviews never become APPROVED. Do **not** add a second review ledger.

**Four-worker capacity**: all W1–W4 may hold four independent non-conflicting branch grants after actual four-way tests; two concurrent code writers is a **soft initial WIP suggestion**, not a hard engine limit. If approvals are the bottleneck, workers switch to docs, adversarial tests and independent L2 technical reviews. Native non-author approval still requires a different eligible GitHub actor.

**Accepted product LOC sensitivity only after eligible merges:** `96 nominal hourly starts × useful-run share × code-share × net product LOC per code run × eventual merge acceptance share`. Hypothetical low `96×0.45×0.20×100×0.50 ≈ 430/day`; balanced `96×0.70×0.35×140×0.65 ≈ 2,140/day`; favorable `96×0.85×0.45×200×0.80 ≈ 5,875/day`. All five factors are **unmeasured and correlated**; results are illustrations, not guarantees. Code can remain at **0 accepted LOC** if the independent GitHub gate is unavailable. A pragmatic post-stabilization test target is **~500–2,500 net accepted functional product LOC/day averaged over several weeks**, with 3,000–6,000/day demanding favorable conditions; real scientific modules may be slower. Do not optimize generated/vendored LOC.

**Documentation timing:** one existing well-understood capability's Ready spec may take hours to days; first complete accepted feature family might take **~1–4 weeks** with accessible sources and reviews; no credible estimate for **all** MONDE documentation until WORK-0004 enumerates validated scope. Code on separately accepted slices may start before global inventory completion.

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
