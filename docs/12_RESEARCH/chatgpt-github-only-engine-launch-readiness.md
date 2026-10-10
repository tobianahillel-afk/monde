# MONDE Development Engine v2 — Launch readiness, freeze and four-worker operating checklist

Status: **NOT READY — PROPOSED ONLY**
Date: 2026-10-10
Tracking: WORK-0005, [draft PR #18](https://github.com/tobianahillel-afk/monde/pull/18), [Issue #17](https://github.com/tobianahillel-afk/monde/issues/17)
Related: [main RFC](chatgpt-github-only-development-engine-v2-rfc.md), [reconciliation runbook](chatgpt-github-only-engine-reconciliation-runbook.md), [ADR](../11_ADR/ADR-0001-chatgpt-github-only-development-engine.md).

**Decisive answer as of this checked baseline:** **DO NOT create/enable four WRITE-CAPABLE hourly ChatGPT tasks.** Four matching scheduler prompts alone do not deploy shared task coordination, GitHub branch protections, fresh-context L2 routing or recovery. They can double-select WORK, alter the same docs, invalidate HEAD-specific proofs and create conflicting PR branches. This is a hard safety gate, not a preference.

If the owner nevertheless creates four scheduled tasks *before readiness*, every task must be strictly **READ_ONLY / DISCOVERY**, not "autonomously continue development." No claims, pushes, approvals, workflow reruns, protected ref changes, merges or changes to existing WORK-0002 branches. That temporary mode is **not** the requested production system and can consume task slots/quota unnecessarily.

## A. Current observed baseline: do not mistake planning for runtime

Snapshot on 2026-10-10; re-query GitHub every time:
- `main` = `b4b52c77fbf05eda65e8f0e951959da70e7edbe7`; branch reports `protected:false`, repository rulesets API returned `[]`.
- WORK-0001 DONE; WORK-0002 IN_REVIEW / AC-6 incomplete; WORK-0003 PLANNED. PR #2 and #14 OPEN. PR #14 success checks do not replace missing exact-head independent reviewer authority.
- PR #18 on separate proposal branch; WORK-0005/ADR-0001 **PROPOSED**; no merged development engine controller.
- No actual deployed `claim` / `fencing` / `reconciler` / four-way scheduler or trusted merge eligibility from WORK-0005; no four-worker race proof.
- `PROJECT_STATE.md` in main contains old narrative about the now-merged PR #5; use live PR/ref/check state instead of copying that stale account.
- All four chat workers can share the same GitHub account; technical context-separated ChatGPT L2 cannot be submitted as a distinct GitHub non-author APPROVED review by the same user.
- The connector does not expose an authorized branch-protection configuration operation at present; WORK-0003 requires owner/admin settings via GitHub UI/qualified permissioned route. User can configure public-repo rulesets via the official GitHub Settings → Rules → Rulesets UI; verify branch rule applies, not just that settings were saved.

## B. Launch gates — an explicit all-green checklist

| ID | Gate | Evidence required | Current result |
|---|---|---|---|
| G-01 | RFC and ADR accepted through proper independent A3 work/review process | Accepted exact revision, real cold read, required hats, no blocking findings | FAIL: Proposed |
| G-02 | Existing WORK-0002 trust root established | PR #14 and PR #2 applicable review/CI/threads settled per existing gates | FAIL: IN_REVIEW |
| G-03 | `main` protected by actual GitHub ruleset or branch protection | Current targeted effective rules: PR, required checks from trusted source, review policy, no force/delete and checked bypass rights | FAIL: unprotected |
| G-04 | Accurate, accepted documentation/progress state | Canonical WORK, status machine, `PROJECT_STATE.md`, accepted ADRs and valid references align | FAIL: proposal only; known stale handover |
| G-05 | Coordinator implementation merged via protected checks | allocator, claims, fencing, ledger, CI future reconcile, bounded error handling | FAIL: not implemented |
| G-06 | Connector real-world atomic claim proven | same initial ref, four simultaneous contenders, one-winner for colliding resources, no lost update | FAIL: untested |
| G-07 | Fencing and stale-worker eligibility enforcement | expired/reassigned writer attempts cannot be promoted/merged after recovery | FAIL: untested |
| G-08 | Automatic+manual reconciliation verified | ambiguous GitHub API result, missed run, late CI, stale review, orphan PR and conflicting control log covered | FAIL: not implemented |
| G-09 | CI source, status and attempt qualification hardened | exact SHA/job/run/attempt trust checked; skipped/spoofed/old green rejected | FAIL: not proven for v2 |
| G-10 | L2 context separation and GitHub authority verified | separate ChatGPT contexts/hats, exact-head review packet; non-author host approval where existing policy demands | FAIL: not proven |
| G-11 | Production-grade bounded resource permissions/WIP | worker write-set/semantic conflict and code branch isolation; one integrator; leak/abuse-safe tools | FAIL: untested |
| G-12 | Pilot with one worker | real GitHub scoped task + CI + durable checkpoint + resume + review without false success | FAIL: not done |
| G-13 | Pilot with two simultaneous workers | same snapshot races, independent work/merges, no owner collision | FAIL: not done |
| G-14 | Four-worker trial and rollback | same nominal hour, delayed/duplicate/missing runs, test failures, rate limits, review unavailability | FAIL: not done |
| G-15 | Task identity and scheduled app authorization | actual distinct task/chat/run identities, app permissions, notification and slot settings verified | FAIL: not configured |

**Launch rule: `ACTIVE_4` only if all G-01..G-15 are PASS on current authority sources.** If any gate changes or becomes unknown, move to controlled degraded mode and stop writes/merges where required. A green check on PR #18 alone is insufficient.

## C. What exactly is frozen?

- Accepted Constitution, work and requirement/review governance remain effective and unchanged by this proposal.
- The **design decision** is not frozen or accepted: proposed ADR-0001 and WORK-0005 can be corrected on their isolated PR branch following the existing review process.
- Once accepted, record exact ADR/work/doc revisions and policy hash; subsequent changes require a new reviewed PR/ADR supersession when warranted. A frozen review HEAD is not to be updated for transient CI status.
- Each implementation task freezes its input base SHA, declared scope, semantic contract snapshot, artifact digest and task attempt ID before execution. Material changes require revalidation.
- Never claim a review remains valid after the reviewed substantive HEAD or normative digest changes.

## D. Operational modes (PROPOSED; not an implemented switch)

| Mode | Authorizations | When |
|---|---|---|
| `OFF` | No worker automation | Current safest production default |
| `READ_ONLY` | Inspect/research/prepare non-mutating proposals; no claim/push/rerun/merge | Before gates or after uncertain trust state |
| `SINGLE_WORKER` | One scoped writer with approved controls and reviews | Pilot, fallback from swarm |
| `PILOT_2` | Two simultaneous bounded writers with proven claims | Controlled real two-worker test |
| `PILOT_4` | Four controlled task invocations on test or low-risk independent work | Pre-launch validation |
| `ACTIVE_4` | Four full hourly task workers, respecting resource claims and required gates | **Only** all G-01..G-15 PASS |
| `RECOVERY` | Read-only triage and specifically authorized corrective action; no automatic broad mutation | Contradiction/outage/unknown effect |
| `EMERGENCY_PAUSE` | No writes, reruns, merges until trust re-established | Main protection loss, compromised ledger, unsafe integration |

Mode must be backed by **actual authoritative, verified control-plane state** and checked before every protected write. The mode names in a Markdown document or chat message do not themselves enforce permissions.

## E. Required GitHub admin step: WORK-0003

The current GitHub connector has not demonstrated an action to configure repository rulesets/branch protection. The owner can access GitHub Settings → Rules → Rulesets → New branch ruleset for public MONDE (eligibility supported by GitHub documentation). Proposed audited protections for `main`:
1. Require pull requests; required status checks must be actual deployed trusted checks, not guessed names.
2. Require valid non-author approval according to the existing Accepted MONDE policy; independently review any later policy migration.
3. Prevent force push, branch delete and bypasses where supported; restrict who may dismiss reviews and modify workflows.
4. Test with a safe negative PR/push case, then GET branch/ruleset state and record evidence in WORK-0003.
5. Avoid selecting a nonexistent required check which could deadlock all merges. Administrative settings must be tested with actual permission level and existing workflows.
GitHub administrator access does **not** establish the independent context of a ChatGPT L2; those assurances remain separate.

Useful official docs: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository and https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches .

## F. Safe order of implementation — no global rollout in a PR

**Before the four tasks:**
1. Finish/safely redirect WORK-0002/PR #14 trust-root blockers without altering their approved contract for expediency.
2. Configure WORK-0003 host-enforced protection, including proof. If sequencing requires WORK-0002 completion first, perform an explicitly authorized protected prerequisite without silently marking WORK-0003 DONE.
3. Review and accept/modify WORK-0005/ADR, including context-separation evidence and non-author authority.
4. Introduce new tightly scoped implementation WORK. Add pure allocator+conflict tests; then control-ref CAS/fencing; then CI future/reconciler; then integration-review packet.
5. Trial with one, two, then four task invocations; do not launch four full scheduled writer tasks to *test* whether claims work.
6. After all G gates pass, create four distinct Scheduled tasks, identical schedule `every hour at :00` Europe/Paris, different worker IDs; verify the platform actually supports four active new tasks without disabling unrelated automations.
7. Preserve downgrade/pause operation and reconcilers. Stop the engine at stable MVP and prioritize the first real MONDE lawful-data/evidence/temporal-query/Console or Globe vertical slice.

No fixed per-role assignment: workers change action types within a single run. A same-chat role switch remains L1; genuinely fresh separate-context L2 requires another worker context.

## G. Suggested common future worker startup prompt — FAIL CLOSED (NOT FOR ACTIVE_4 TODAY)

> MONDE WORKER W{1..4}. Repository tobianahillel-afk/monde, ChatGPT + GitHub connector only. Never use an external local host, Codex paid review, or another project's repo. On every invocation, read live main SHA, Accepted governance/AGENTS.md, the current WORK DAG and authorized policy/mode, PR/CI/review sources, operational control ref, reconciliation runbook and the readiness-gate evidence. **If the accepted scheduler, verified claim+fencing, reconciliation, review/merge and branch-protection gates are not actually deployed, work only READ_ONLY and report the missing prerequisite.** Never approximate a claim with an Issue label, clock offset, free-form task name or ChatGPT memory. After verified claim, complete as much useful scoped work as the session allows, switching RESEARCH/BUILD/FIX/TEST/L1/review-prep as appropriate. L2 must be from a genuinely different fresh context and cannot substitute for a required GitHub non-author approval. CI futures and ambiguous mutations require durable evidence/reconciliation; never blindly repeat remote writes. No direct main write, force push or stale-head merge. Report observed commits/PR/CI, blocked gates and exact next action truthfully. Do not claim completion or enable ACTIVE_4 by editing this prompt.

This is an operational **template**, not permission to schedule four write-capable tasks or claim any control-plane feature exists. Separate ChatGPT conversations, not just different IDs in one chat, are needed for genuine separate-context L2.

## H. Stop/rollback, acceptance and readiness recheck

- If any trust-root check source becomes suspect, GitHub protections disappear, unknown side-effects accumulate or lease integrity becomes unverifiable: stop new writes/integration, preserve evidence, enter RECOVERY.
- If one worker repeatedly collides, restrict to read-only or SINGLE_WORKER **only through an approved mechanism**; do not delete someone else's branch, reset reviews or erase pending operations.
- Measure accepted real MONDE merges/day, READY→MERGED time, duplicate claims, collision resets, review latency, Actions cost, API errors, and rollback frequency. Do not invent throughput multipliers.
- Reassess launch gates on **live GitHub facts**, not on this dated snapshot. Unknown is FAIL until checked.
- A user-facing answer must state both current mode (conceptual `OFF/READ_ONLY`) and whether the actual enforcement/scheduler is deployed, and never confuse documentation with running code.

**Current decision:** `NOT_READY`; **four automated write-capable Scheduled tasks must remain disabled/not created**.
