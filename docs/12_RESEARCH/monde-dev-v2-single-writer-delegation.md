# MONDE Development Engine V2 — single interactive writer

Status: implementation candidate (not Accepted). Updated 2026-10-11.
WORK-0005 remains PROPOSED on documentation PR #18, where its declared work
dependency is WORK-0001 (DONE). The executable candidate is draft PR #19.
This V2 requires neither WORK-0002 nor WORK-0003 as a runtime dependency,
but integrations remain subject to Accepted MONDE governance and host rules.

> **Implementation scope clarified 2026-10-11:** V2 implements one manually triggered GitHub writer plus 1–4 ephemeral ChatGPT read-only research/L2 reviewers. The obsolete issue-comment arbiter, `controller.cjs`, synthetic four-writer tests, and workflow dispatcher are **not included** in this implementation PR. No `ACTIVE_4` code runs in this release. The older RFC in PR #18 is a historical proposal, not authorization for a second GitHub writer.

## Execution topology

The user initiates the main development conversation manually. This foreground ChatGPT conversation is the sole writer of source code, tests, branches, PR updates and review publication through the connected GitHub app. Its work is scoped by the existing MONDE governance and repository protections.

The foreground agent may create 1–4 **one-shot scheduled ChatGPT tasks** when independent information will materially improve a current work item. Tasks have no development authority. Their permitted work is GitHub read-only research, architecture comparison, test ideation, and independent context-separated L2 code review. They must never attempt source or comment writes, merge PRs, configure the repository, create additional tasks, or request an external paid AI runtime.

When using `planDelegations`, inspect `schedule_recommended` and `equivalent_mission_of`: two assignments with the same mission kind, normalized scope and objective are potential redundant ChatGPT tasks. By default schedule only the first; a second context-separated L2 review may deliberately be requested when materially useful. This hint never creates, cancels, approves or classifies a report, and it does not prove independence.

These tasks are not four development writers. The older four-writer allocator remains only in the previous Git commit history; its source and dispatcher are removed from this V2 candidate to avoid deploying unnecessary privileged coordination code. ChatGPT alone decides what to write in a manually initiated conversation; the pure delegation helper produces read-only briefings and validates the format of retrieved reports, not their independent accuracy.

## Distinct read-only mission kinds

The foreground developer may delegate `L2_REVIEW`, `TECH_RESEARCH`,
`ARCH_ANALYSIS`, `SECURITY_ANALYSIS`, or `TEST_IDEATION`.
Each mission has an immutable assignment ID, PR, exact HEAD, scope and author
context ID. A cohort of one to four missions may mix kinds only for the same
repository, PR and SHA.
L2 review assignments reject nested directory/file scopes to keep coverage
unambiguous. Read-only research may intentionally include nested scope paths;
this never grants L2 coverage or approval. Research missions are analytical work, **not L2**.

The pure helper `planDelegations` **requires** a `mission_kind` for
every mission; a missing, unknown or null kind is rejected (fail-closed).
`buildReviewPrompt` accepts only `L2_REVIEW`; `buildResearchPrompt`
accepts only the four research kinds; `planDelegations` explicitly routes
to the matching prompt. Research tasks receive the distinct
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

## Incremental L2 delta safeguard

`planL2Delta` now requires the foreground operator to supply a positive
`previous_review` observation bound to the old SHA **and the exact prior
assignment ID and sorted scope paths**, with an explicitly different reviewer
context, `review_verdict: APPROVE`, qualified coverage and zero open R1/R2
findings before suggesting a changed-file-only L2 mission. Without that observation, a GitHub diff alone
returns `MANUAL_IMPACT_ANALYSIS_REQUIRED` (no targeted assignment).
These booleans are **not host-verified inside the pure helper**; the foreground
operator must verify their sources independently. Even a targeted candidate
is never a reusable approval, a qualified L2 report or a merge authorization.

## Safe speed

Use one focused implementation cycle and risk-appropriate local/synthetic tests while editing. Batch coherent changes, then require the authoritative exact-HEAD CI/review checks **once at the real promotion boundary**; do not re-run the full historical validation suite just to reconsider already diagnosed unchanged findings. No reduction of required protections or fabrication of quality evidence.

## Dispatch decision

Delegate when separate research/review provides useful independent information; otherwise develop directly. Reviewers get the accepted requirements and PR/HEAD, but not the author's private reasoning. Scheduled tasks never become automatic background writers.

## Recovery

Persist checkpoint fields: repo, branch, candidate HEAD, assignment IDs, task titles, execution status, observed report availability, findings, and next safe action. For an unavailable task output, mark UNKNOWN; for stale SHA, mark STALE; for an actual L2 finding, return to foreground coding and request a fresh context review only when material changes require it.

## Executable pure-helper for report return (interactive-only)

The branch-local `.github/scripts/monde-dev/delegation.cjs` provides a **small optional, dependency-free** protocol for the interactive writer. It has no GitHub/network/filesystem or scheduling APIs. Do not introduce another database, queue, reviewer-service or runtime.

- `assignment` checks a **mandatory explicit mission kind**, unique mission ID, exact PR SHA, intended scope and originating author context.
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

`WORK-0005` in draft PR #18 now describes the **single interactive GitHub writer and read-only scheduled reviewers**. It remains `PROPOSED`, so the review and acceptance of that documentation PR are still separate requirements; the superseded four-writer RFC does not authorize an additional writer.

## Controls added for recovered-batch provenance and public relay

Two assignments cannot count as two context-separated L2 or research observations if their actual retrieved `context_id` **or** `message_ref` is reused. `assessDelegationBatch` marks every affected observed result `INDEPENDENCE_UNVERIFIED`, preserves its prior status, and never claims GitHub approval. These fields remain caller observations, not cryptographic signatures: the foreground ChatGPT must still verify their real conversation provenance.

Before a manually copied L2 review is prepared for a **public** GitHub PR, `prepareInteractiveHandoff` requires an explicit foreground confidentiality review (`secrets_checked`, `personal_data_checked`, `public_repo_safe` all true). A missing check returns `CONFIDENTIALITY_REVIEW_REQUIRED` without building public-ready text. Even after clearance, the writer remains solely responsible for accuracy, privacy and whether publication is authorized. The output labels normalized analysis and canonical JSON, not byte-identical original messages.

## Exact L2 file coverage and foreground publication safety

For any fresh L2 report, the machine footer requests `reviewed_paths` with the actual paths examined. This is reviewer-declared evidence, **not proof that all source files were read**. An `APPROVE` without declared coverage of the assigned paths returns `L2_SCOPE_NOT_EVIDENCED`, never accepted review. The interactive author must still inspect evidence and actual independent context; old footer versions remain parseable for correction reports.

Manual public-repo handoff additionally requires explicit confidentiality clearance and refuses obvious private key / GitHub credential patterns even when the flags are set. Only with explicit interactive opt-in (`provenance_hashes_approved:true`) may a copy-ready relay include the original response SHA-256 and byte length, and observer-identifier fingerprints. These are **never published by default**; the normalized relay text is not represented as byte-for-byte verbatim. Neither a digest nor a reviewed-file list proves external identity or GitHub-native approval.

## Distinct-context reuse across batches (2026-10-11)

When malformed machine footers contain numerous finding objects, the fallback scans every claim but retains **at most 50 actionable details**, prioritizing R1 before R2/R3; a complete original report stays in its ChatGPT conversation. This bounded list and any malformed report remain unqualified for acceptance. The 1 MiB inspection threshold is measured in UTF-8 bytes.

The foreground writer can pass `prior_sources` to `assessDelegationBatch`: a bounded inventory of earlier observed `{assignment_id,context_id,message_ref}` values, retrieved from real separate ChatGPT task conversations. The helper now detects same-conversation/same-message reuse **both within the current batch and across supplied earlier batches**. This is a caller-supplied observation, **not authenticated provenance**. Missing historical observations do not prove independence. For duplicate contexts, R1/R2 `NEEDS_CORRECTION` and `BLOCKED` remain the primary status; the separate `independence_unverified` flag and `independence_conflicts` count prevent concealment of actionable findings. An otherwise clean result is instead downgraded to `INDEPENDENCE_UNVERIFIED`. No independent GitHub approval or automatic merge is produced.

## Minimal public relay by default

Even after confidentiality review, `prepareInteractiveHandoff` now emits a **minimal** copy-ready GitHub comment: mission identity, reviewed SHA, and only opt-in checksums of the source response and observer identifiers, verdict/status, finding counts and IDs/severities. It does **not** include the full reviewer analysis, footer, unredacted message reference or context identifier by default. The complete text stays in the original separate ChatGPT review conversation. To include the full review deliberately, the foreground interactive writer must both complete the existing three confidentiality checks and explicitly set `publication_clearance.full_report_approved=true`; private-key/token-pattern rejection still applies. Neither setting establishes GitHub native approval or verified reviewer identity.

## Latest L2 remediation — 2026-10-11 (candidate, not Accepted)

The read-only implementation now permits an honestly blocked L2 with `reviewed_paths: []` and stated limitations, while `APPROVE` still needs declared coverage. A research mission cannot be processed as an L2 review. For a directory-scoped L2 assignment, the foreground writer must provide a GitHub-observed enumeration of its files at the exact HEAD to `assessReview` using a complete `coverage_manifest` (`head_sha`, `verified_at_head:true`, `source_kind:'github_recursive_tree'`, `enumeration_complete:true`, `tree_sha`, `enumerated_count`, `files`); every enumerated file must be declared examined to avoid even *provisional* coverage. This is still a manual observation and never cryptographic evidence of reading.

The L2 task prompt explicitly requests the six relevant Review Council hats and their evidence/limitations. Public relay screens both source and generated output, including source reference identifiers, and rejects prepared comments larger than 12 KiB; oversized reports remain in ChatGPT until the interactive writer prepares an appropriate manually reviewed summary. CI uses Node's native nonregression thresholds (99% lines, 93% branches, 100% functions) **only as an interim warning barrier against degradation**, not as a waiver of MONDE's stricter meaningful 100% line/branch target. Final acceptance still requires full DoD or a reviewed exception and a current SHA-separated L2.


## Review provenance and batch-qualification clarification (2026-10-11)

The foreground writer passes an external, exact-HEAD `coverage_manifests` map into `assessDelegationBatch`, keyed by actual assignment ID. Directory coverage is only provisionally complete if every required file is listed as examined; a manifest is **not** proof of reading. An unverified source, stale SHA or malformed footer does not erase claimed R1/R2: the batch returns `unqualified_blocking_reports`, `unqualified_r1`, `unqualified_r2` and `needs_attention` for manual triage.

For cross-cohort history, use `prior_sources` with `assignment_id`, actual retrieved `context_id` and `message_ref`, plus `head_sha`, `mission_kind` and SHA-256 `response_sha256` of the *entire raw retrieved message*. An old three-field record is readable for historical context, but if its mission ID is reused it is **ambiguous**, not fresh review approval. A different SHA, mission type or message digest for the same ID is disqualified. Never reuse an assignment ID after a HEAD change: create a new mission instead.

Manual relays to the public GitHub PR must be cleared by the foreground ChatGPT writer. Best-effort secret-pattern checks now include Slack, GitLab, npm, Stripe secret/restricted `sk_live_`/`rk_live_` keys, payment/API and bearer credentials, and the maximum generated relay is **12 KiB = 12,288 bytes**. The pattern scanner is a safety backstop, not confidentiality certification. The former four-writer RFC text in PR #18 is superseded. The revised `WORK-0005` now targets single-writer V2 but remains **PROPOSED**, not Accepted or sufficient for deployment.

## Triage interactif des constats récupérés

Le moteur conserve en mémoire les preuves et corrections des constats L2 et recherches. Un rapport ancien ou de provenance non qualifiée expose ses constats sous `reported_findings` (allégations), sans statut d'approbation. Le résultat L2 valide de format expose `findings_for_triage`; l'agrégateur retourne `triage_findings` explicitement marqués `UNVERIFIED_REPORT_CLAIM`. Les tâches déléguées restent strictement en lecture seule ; aucun constat n'est automatiquement publié, accepté ou fusionné. Le relais public exige toujours une vérification humaine de confidentialité.

## Recovery for a reviewer report without a machine footer

A separate ChatGPT reviewer may return a useful technical report without the exact
footer. `assessReview` classifies it as `REPORT_NEEDS_MANUAL_REVIEW`,
retains a **foreground-only**, bounded 8,192-character head excerpt and
(optional) 8,192-character tail excerpt, plus at most **13** R1/R2 snippets
(first six, last six, and the first detected R1 even if it occurs in the middle).
The extractor keeps no unbounded set of matches. The limit means **1,048,576 UTF-8 bytes** (not JavaScript string length). Reports above that size are
inspected only through bounded head/tail windows, so findings in their
uninspected middle remain **unknown**. A SHA-256 is computed internally
only for responses of 1 MiB or less; any publication of report fingerprints,
message-reference fingerprints or original-response byte counts requires
explicit `provenance_hashes_approved:true` plus the normal confidentiality
clearance. Nothing is published by default. This is **not** L2 acceptance
evidence, native GitHub approval,
or permission for public publication. The main interactive writer may inspect
and apply substantiated findings directly while preserving original provenance.

## Dédoublonnage prudent des constats

La fonction pure `groupTriageFindings` et la sortie `actionable_finding_groups` d’`assessDelegationBatch` regroupent uniquement les constats ayant exactement la même **gravité (R1/R2/R3), le même chemin, la même preuve et la même correction proposée**. Ces quatre champs forment l’identité du regroupement ; même sur un chemin et une preuve identiques, une qualification R1 et une qualification R3 restent deux constats distincts. Chaque groupe conserve toutes ses références d’origine ; `triage_findings` demeure intégral. `repeated_finding_occurrences` indique les répétitions textuelles, **jamais les corrections réalisées**. Deux observations semblables mais matériellement différentes restent séparées. Aucun regroupement ne vaut fermeture, preuve L2, autorisation de fusion ou dispense de vérification de la correction au HEAD approprié.

## L2 findings qualification and exact-tree coverage (2026-10-11)

The `assessReview` helper never interprets a machine-valid clean `APPROVE` as the end of validation: `needs_attention: true` and `human_review_required: true` remain set until an interactive developer qualifies the substantive report. For an internally contradictory or malformed footer (notably `APPROVE` alongside R1/R2 findings), the report stays `REPORT_NEEDS_MANUAL_REVIEW` but machine-recognizable R1/R2 allegations, corrective actions and counts are preserved as **unqualified allegations**. Neither the footer nor its recovery proves reviewer identity or review validity.

Directory-scoped `coverage_manifest` must now include the foreground-observed exact commit `head_sha`, `verified_at_head:true`, `source_kind:'github_recursive_tree'`, `enumeration_complete:true`, a 40-character `tree_sha`, the full `files` array, and `enumerated_count` matching its length. Missing/mismatched evidence results in `L2_SCOPE_NOT_EVIDENCED`. This is a strict input contract and a declaration by the interactive caller, **not independent proof of GitHub traversal or that a reviewer actually read the files**. If recursion is truncated or exceeds the 2,000-file bound, keep review incomplete and manually subdivide the assignment; never invent an exhaustive manifest.

## Stable closing pass — focused L2 findings

The reviewer footer and provenance/coverage manifests remain **claims awaiting foreground qualification**, not host-signed proof. For speed, schedule L2 only once a coherent candidate is frozen; batch material F01–F04 fixes. A complete-looking directory tree manifest alone never upgrades a directory-scoped review to provisionally complete. Prefer **explicit file paths** in delegated review assignments; externally confirm the GitHub exact-SHA tree before accepting any broad-directory completeness claim. Research reports marked COMPLETED always require foreground inspection. Unqualified R1/R2 allegations, even in malformed reports, must stay visible in triage counters and block automatic readiness.

## Simple-code implementation rules and ChatGPT L2 retrieval

The interactive developer obeys the twelve implementation rules in `monde-dev-v2-interactive-prompt.md`: source invariants, minimal structure, linear control flow, fail-closed sensitive operations, clear responsibility, prudent reuse, root-cause corrections, and no speculative abstractions. Batch related changes and perform focused testing at a stable candidate HEAD; do not loop over old known failures without new evidence.

L2 tasks run in distinct ChatGPT conversations and return their complete reports **in the conversation**, without any GitHub mutation. The foreground writer itself retrieves prior task conversations when accessible, preserves the reviewed SHA and reviews findings before modifying GitHub. Reports with unreadable research footers are retained in memory as a bounded excerpt for manual triage, never accepted as L2 evidence or automatic approval.

## Progressive delivery — stop nonblocking micro-fix loops (proposal for WORK-0005)

The interactive developer prioritizes **usable, coherent increments** rather than spending successive sessions perfecting cosmetic edge cases. Review/R&D claims are triaged once per substantive batch: R1/R2, demonstrable functional defects or material security/privacy/data-contract failures merit targeted remediation before affected acceptance; R3 and **confirmed** low-impact findings are recorded as follow-up in existing WORK/PR tracking with evidence and selected remedy, then another eligible function may proceed. Unknown severity is not silently R3. Repeated identical findings reuse the original proof; re-review and broad CI run on a stable release candidate, not on every inconsequential edit. Deferred work is not automatically resolved and no protected DoD or GitHub approval requirement is waived.

`groupTriageFindings` now emits **advisory-only** `material_triage_candidates`, `deferred_backlog_candidates` and `progression_advice` without closing, publishing or approving any finding. `assessDelegationBatch` propagates these candidate groups. This is prioritization, never a merge gate or an authoritative R3 classification. The global mandatory-agent rule is separately proposed in [the progressive-delivery governance PR](https://github.com/tobianahillel-afk/monde/pull/21).

## Differential L2 scope after an implementation change (candidate)

`planL2Delta` is an optional, pure foreground helper to avoid unnecessarily re-reading unchanged files. It accepts a previously **observed** L2 assignment, the new exact PR HEAD, and a host-verified complete file comparison from the previous HEAD. It proposes a **new** mission ID and only the modified/additional files within the old scope. A rename, deletion, edit outside scope, missing comparison, or more than 24 scoped files instead requires manual broader impact analysis; review dependency changes explicitly. The caller must verify the GitHub compare data, completeness and impact: the helper cannot do so and is not an L2 review, retained approval, merge eligibility or scheduled task. The fresh-context reviewer must read relevant adjacent contracts and record findings against the new SHA.

### Remediation visibility when development is blocked

A task with a reported R1/R2 concern must remain visible in `remediation_candidates` even when its WORK is `PROPOSED`, a prerequisite is pending, or another execution gate is not met. The suggested triage remains **read-only, unverified and non-executable**, with `execution_allowed:false` and `execution_blockers` showing why the task cannot advance. This is not a backdoor to `READY`, and it never changes a registry status. Report fingerprints used for deduplication include the **severity, path, evidence, and proposed corrective action**; claims with different correction text are not collapsed.

## Interactive review relay size limits

A malformed or provenance-unverified L2 report can produce an **unqualified**, read-only triage handoff via `prepareUnqualifiedTriageHandoff`. The resulting public-repo text is capped at 12 KiB. It explicitly distinguishes **claims received**, **structurally recognized**, **invalid/unrecognized**, **candidates omitted by the 50-entry internal retention limit**, and **details omitted later by the 12 KiB public relay budget**. These counts describe unverified claims, not confirmed vulnerabilities. When the original report contains too many details, the helper orders validated allegations by **R1, then R2, then R3**, removes fallback excerpts before removing lower-severity structured findings, and explicitly reports the numbers of omitted details. The complete evidence remains in the originating ChatGPT conversation; the shortened relay is **not complete L2 evidence, a verified security finding, an independent GitHub approval or permission to merge**. The interactive writer must inspect confidentiality before publication.

### Public evidence references in PR checkpoints

The `MONDE_V2_RESUME_V1` bookmark accepts only GitHub CI job/run/check numeric IDs (`job-115331656856`, `run-38325226864`, or equivalent colon separators), canonical `registry/reviews/REVIEW-*.yaml`, `WORK-*` / `TEST-*` registry IDs or paths, and numbered `PR-*` references. Do not insert ChatGPT conversation/message identifiers, arbitrary text, or report content in `evidence_refs`. These fields are navigation hints only: the writer must independently verify all claims and the exact HEAD from GitHub. Existing malformed checkpoint references are treated as invalid and rebuilt, not silently trusted.
