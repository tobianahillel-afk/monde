# MONDE Development Engine V2 — single interactive writer

Status: implementation candidate (not Accepted). Updated 2026-10-11.

## Execution topology

The user initiates the main development conversation manually. This foreground ChatGPT conversation is the sole writer of source code, tests, branches, PR updates and review publication through the connected GitHub app. Its work is scoped by the existing MONDE governance and repository protections.

The foreground agent may create 1–4 **one-shot scheduled ChatGPT tasks** when independent information will materially improve a current work item. Tasks have no development authority. Their permitted work is GitHub read-only research, architecture comparison, test ideation, and independent context-separated L2 code review. They must never attempt source or comment writes, merge PRs, configure the repository, create additional tasks, or request an external paid AI runtime.

These tasks are not four development writers. The previous issue-comment allocator remains an isolated TEST_ONLY prototype and is not the production operating mode. Its synthetic GRANTED result conveys no GitHub write authorization. The ACTIVE_4 design is dormant and must not be deployed as part of single-writer activation.

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
