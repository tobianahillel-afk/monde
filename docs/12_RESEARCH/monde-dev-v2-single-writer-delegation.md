# MONDE Development Engine V2 — single interactive writer

Status: implementation candidate (not Accepted). Updated 2026-10-11.

> **Implementation scope clarified 2026-10-11:** V2 implements one manually triggered GitHub writer plus 1–4 ephemeral ChatGPT read-only research/L2 reviewers. The obsolete issue-comment arbiter, `controller.cjs`, synthetic four-writer tests, and workflow dispatcher are **not included** in this implementation PR. No `ACTIVE_4` code runs in this release. The older RFC in PR #18 is a historical proposal, not authorization for a second GitHub writer.

## Execution topology

The user initiates the main development conversation manually. This foreground ChatGPT conversation is the sole writer of source code, tests, branches, PR updates and review publication through the connected GitHub app. Its work is scoped by the existing MONDE governance and repository protections.

The foreground agent may create 1–4 **one-shot scheduled ChatGPT tasks** when independent information will materially improve a current work item. Tasks have no development authority. Their permitted work is GitHub read-only research, architecture comparison, test ideation, and independent context-separated L2 code review. They must never attempt source or comment writes, merge PRs, configure the repository, create additional tasks, or request an external paid AI runtime.

These tasks are not four development writers. The older four-writer allocator remains only in the previous Git commit history; its source and dispatcher are removed from this V2 candidate to avoid deploying unnecessary privileged coordination code. ChatGPT alone decides what to write in a manually initiated conversation; the pure delegation helper produces read-only briefings and validates the format of retrieved reports, not their independent accuracy.

## Distinct read-only mission kinds

The foreground developer may delegate `L2_REVIEW`, `TECH_RESEARCH`,
`ARCH_ANALYSIS`, `SECURITY_ANALYSIS`, or `TEST_IDEATION`.
Each mission has an immutable assignment ID, PR, exact HEAD, scope and author
context ID. A cohort of one to four missions may mix kinds only for the same
repository, PR and SHA. Research missions are analytical work, **not L2**.

The pure helper `planDelegations` accepts an optional `mission_kind`;
omission means legacy `L2_REVIEW`. Research tasks receive the distinct
`MONDE_V2_RESEARCH_RESULT_V1` marker and may return `COMPLETED`,
`CHANGES_REQUIRED` or `BLOCKED`. `COMPLETED` is *never* GitHub
`APPROVED`. Verified R1/R2 findings in completed research remain
`NEEDS_CORRECTION`. A report without real separate-chat provenance is
`INDEPENDENCE_UNVERIFIED`, and a missing report is `REPORT_UNAVAILABLE`.

The original L2 marker `MONDE_V2_L2_RESULT_V1` and its formal verdict
contract remain distinct and backwards compatible. Both kinds preserve
read-only task permissions, require full output in the task's ChatGPT
conversation, and can never mark a PR eligible for merge on their own.

## Delegation protocol

1. The foreground developer verifies the current repository, exact PR HEAD, and relevant accepted rules.
2. Select only genuinely independent questions. Launch one task by default, up to four only when useful and capacity permits. Avoid redundant work.
3. Give each task a unique title, assignment ID, target SHA, focused questions, evidence constraints, and a clear prohibition on GitHub writes.
4. Request the entire analysis and findings in the task's **ChatGPT response**, not in a GitHub comment. Require a final machine-readable footer carrying assignment ID, HEAD and verdict.
5. Check task execution status and retrieve its separate conversation output if supported through ChatGPT conversation-history context. The scheduler listing alone is *not* the report. Cross-conversation retrieval is not guaranteed or instantaneous.
6. If the exact report cannot be accessed, record REPORT_UNAVAILABLE. Do not assume it succeeded or fabricate its findings. Continue independent foreground work when possible.
7. If retrieved, validate assignment identity, scope, factual links, exact SHA and context separation. A changed HEAD invalidates a blanket approval; re-review changed lines when required.
8. The foreground chat alone applies corrections and records verified evidence in GitHub. If publishing a report is permitted, attribute it to the task's separate conversation without claiming a distinct GitHub reviewer identity.
9. A L2 report is technical independent analysis, not a native GitHub non-author APPROVED review. Keep these two authorities separate.

## Safe speed

Use one focused implementation cycle and risk-appropriate local/synthetic tests while editing. Batch coherent changes, then require the authoritative exact-HEAD CI/review checks **once at the real promotion boundary**; do not re-run the full historical validation suite just to reconsider already diagnosed unchanged findings. No reduction of required protections or fabrication of quality evidence.

## Dispatch decision

Delegate when separate research/review provides useful independent information; otherwise develop directly. Reviewers get the accepted requirements and PR/HEAD, but not the author's private reasoning. Scheduled tasks never become automatic background writers.

## Recovery

Persist checkpoint fields: repo, branch, candidate HEAD, assignment IDs, task titles, execution status, observed report availability, findings, and next safe action. For an unavailable task output, mark UNKNOWN; for stale SHA, mark STALE; for an actual L2 finding, return to foreground coding and request a fresh context review only when material changes require it.

## Executable pure-helper for report return (interactive-only)

The branch-local `.github/scripts/monde-dev/delegation.cjs` provides a **small optional, dependency-free** protocol for the interactive writer. It has no GitHub/network/filesystem or scheduling APIs. Do not introduce another database, queue, reviewer-service or runtime.

- `assignment` checks a unique mission ID, exact PR SHA, intended scope and originating author context.
- `buildReviewPrompt` assembles the read-only ChatGPT task instruction and demands the complete report in the separate conversation's response with a compact footer labelled `MONDE_V2_L2_RESULT_V1`.
- `parseReviewResponse` validates the **actual retrieved response text**. It accepts UTF-8 French report content, flags evidence-bearing findings and rejects a missing, duplicate or noncanonical footer.
- `planDelegations` builds a cohort of 1–4 read-only missions, enforcing unique mission IDs and one exact PR/SHA/author context; it does **not** create Scheduled tasks.
- `assessDelegationBatch` classifies only actually retrieved mission results, retains missing reports as `REPORT_UNAVAILABLE` and always returns `native_github_approved:false` / `ready_for_merge:false`.
- `assessReview` distinguishes `REPORT_UNAVAILABLE`, `REPORT_NEEDS_MANUAL_REVIEW`, `WRONG_ASSIGNMENT`, `STALE_SHA`, `INDEPENDENCE_UNVERIFIED`, `NEEDS_CORRECTION`, `BLOCKED` and `L2_REPORT_RECEIVED_PENDING_VALIDATION`. A formatted positive result **still requires external substantive manual qualification**, even if a separate-chat provenance observation was supplied. It always returns `native_github_approved:false`.

Independence **cannot be proved by a self-declared JSON field**. The caller must have actually retrieved and matched the separate ChatGPT conversation and its provenance before marking that external observation verified. A review that cannot be retrieved remains unavailable regardless of the automation run's success. The older L2 report at SHA `4e4234f8f73ebe6d22be0724907c127143ca166e` is usable to inform corrections, but does not approve the current PR HEAD.

Use the module where it reduces manual transcription errors. The ChatGPT interactive session does **not** need to run JavaScript locally to honor the same protocol. A missing machine footer may still supply useful qualitative findings, but it must not automatically count as a qualified L2 approval. The reviewer prompt explicitly requests the marker on the penultimate line and compact JSON on the final line (no Markdown fence or trailing prose). No scheduled task may write a GitHub comment, even to post the report.


## Fast interactive handoff from a read-only L2 reviewer

The optional pure `prepareInteractiveHandoff` function creates a copy-ready, fully attributed
review artifact **only after the reviewer report has been retrieved from another
ChatGPT conversation, matched to its assignment, and checked against the exact
current SHA**. This helper does not publish anything or approve any GitHub PR.
The main interactive ChatGPT writer decides whether to relay it on GitHub.
Out-of-scope findings are preserved as useful discoveries, but a narrow
`APPROVE` with out-of-scope findings yields `L2_REPORT_SCOPE_EXPANSION` and
requires manual qualification. A `BLOCKED` review without any limitation or
finding is malformed. No machine footer is an assertion of native independence.

## L2 findings from latest separate context (author-side response)

When a task result is retrieved from ChatGPT history, preserve the actual message reference and reviewer-context marker, but treat both as **manually qualified observations**, not cryptographic signatures or a separate GitHub approver. The optional `prepareInteractiveHandoff` output uses `ready_for_manual_relay: true` when structure/assignment pass; its deprecated `can_publish` field remains **false**, since only the foreground conversation can decide to publish. Never claim the helper verified a human review or successful GitHub publication. The review prompt now gives a neutral BLOCKED example rather than inventing a critical finding.

The candidate PR CI must check out the PR's **head SHA**, verify it explicitly, and run without persisted checkout credentials. Default GitHub `pull_request` merge-ref CI is useful for compatibility, but is not proof that the *candidate HEAD itself* is what the reviewer checked. A separate trusted merge-gate remains the responsibility of repository governance when promotion is authorized.

`WORK-0005` in draft PR #18 describes an earlier four-writer architecture and is **not** a valid launch requirement for this interactive-only V2. Before accepting work-level normative status, that proposal must be reconciled through the governed documentation PR; this code PR does not silently rewrite a proposed WORK in another branch.

## Controls added for recovered-batch provenance and public relay

Two assignments cannot count as two context-separated L2 or research observations if their actual retrieved `context_id` **or** `message_ref` is reused. `assessDelegationBatch` marks every affected observed result `INDEPENDENCE_UNVERIFIED`, preserves its prior status, and never claims GitHub approval. These fields remain caller observations, not cryptographic signatures: the foreground ChatGPT must still verify their real conversation provenance.

Before a manually copied L2 review is prepared for a **public** GitHub PR, `prepareInteractiveHandoff` requires an explicit foreground confidentiality review (`secrets_checked`, `personal_data_checked`, `public_repo_safe` all true). A missing check returns `CONFIDENTIALITY_REVIEW_REQUIRED` without building public-ready text. Even after clearance, the writer remains solely responsible for accuracy, privacy and whether publication is authorized. The output labels normalized analysis and canonical JSON, not byte-identical original messages.

## Exact L2 file coverage and foreground publication safety

For any fresh L2 report, the machine footer requests `reviewed_paths` with the actual paths examined. This is reviewer-declared evidence, **not proof that all source files were read**. An `APPROVE` without declared coverage of the assigned paths returns `L2_SCOPE_NOT_EVIDENCED`, never accepted review. The interactive author must still inspect evidence and actual independent context; old footer versions remain parseable for correction reports.

Manual public-repo handoff additionally requires explicit confidentiality clearance and refuses obvious private key / GitHub credential patterns even when the flags are set. Each copy-ready relay gives the SHA-256 and byte length of the **original retrieved ChatGPT response**; the normalized relay text is not represented as byte-for-byte verbatim. Neither a digest nor a reviewed-file list proves external identity or GitHub-native approval.

## Distinct-context reuse across batches (2026-10-11)

The foreground writer can pass `prior_sources` to `assessDelegationBatch`: a bounded inventory of earlier observed `{assignment_id,context_id,message_ref}` values, retrieved from real separate ChatGPT task conversations. The helper now detects same-conversation/same-message reuse **both within the current batch and across supplied earlier batches**. This is a caller-supplied observation, **not authenticated provenance**. Missing historical observations do not prove independence. For duplicate contexts, R1/R2 `NEEDS_CORRECTION` and `BLOCKED` remain the primary status; the separate `independence_unverified` flag and `independence_conflicts` count prevent concealment of actionable findings. An otherwise clean result is instead downgraded to `INDEPENDENCE_UNVERIFIED`. No independent GitHub approval or automatic merge is produced.
