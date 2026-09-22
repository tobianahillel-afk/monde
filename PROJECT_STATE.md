# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions.

## Current phase / lot

- PHASE-0 / LOT-0 remain `IN_PROGRESS`.
- WORK-0001 is `DONE / A3`, integrated on `main` at `29086643387ff46ab6636dd2fa3014efccc10165`.
- WORK-0002 remains `IN_REVIEW / A3`; WORK-0003 and WORK-0004 remain blocked.

## PR #5 / T12 trusted predecessor

PR #5 (`chore/work-0002-stale-green-bootstrap`) remains the narrow trusted-default-branch predecessor for WORK-0002/T12. No merge and no historical review-thread resolution is permitted while material findings remain open or a successor review is incomplete.

REVIEW-0049 is terminal `COMPLETE / CHANGES_REQUIRED` independent negative evidence on exact head `c8f1fec24358c25224771a15b647d56c8a2f0287` via `PRR_kwDOUUI5ts8AAAABN4sxvg`.

## REVIEW-0050 — administrative terminal negative evidence

REVIEW-0050 technical candidate `cbe21fa4cebc1c8f8b3030af17284de5700f9818` passed Bootstrap #154 / run `35152847816` with **194/194 tests**, **1,856 statements / 842 branches**, **100% line + branch**, and live read-only PR #2 contract probe SUCCESS. Its OPEN checkpoint `871850ac5b66a43cfd8491ef445d1738ad09d822` passed #155 and frozen IN_PROGRESS head `f2ec7e8a0ca30b2be3272b2b1f022b7dabd7048c` passed #156.

REVIEW-0050 is nevertheless now **`CLOSED / CHANGES_REQUIRED`**. No exact-head independent L2 was submitted before author-side adversarial review **`PRR_kwDOUUI5ts8AAAABN7LvGQ`** invalidated the frozen head.

The P1 is a positive-authorization failure in break-glass recovery: recovery reads the baseline run attempt and prior effective-check identity, then later clears issue #7. The workflow concurrency group serializes this bootstrap workflow with itself, but cannot serialize collaborators, GitHub UI, REST clients or another workflow capable of rerunning the canonical run. An external rerun can therefore start after the last GET and before the issue PATCH, leaving a new head-scoped mutation in flight after the only durable pending identity has been erased.

A third or fourth GET cannot solve this TOCTOU. REVIEW-0051 must remove recovery's authority to clear pending state from non-atomic observations.

All **65** historical inline material threads remain unresolved. No merge is permitted.

The REVIEW-0050 `CLOSED` state-only checkpoint `71c40aeb7ca7de4968a78953e9d003a5f65c3f9f` passed Bootstrap #157 / run `35211526610`: **194/194 tests**, **1,856 statements / 842 branches**, **100% line + branch**, and live read-only PR #2 contract probe SUCCESS at **7/100** requests.

## REVIEW-0051 corrective direction

The minimum safe successor is intentionally simpler:

- preserve the proven REVIEW-0050 V5 poll and closed-origin pending observation behavior;
- replace break-glass clear with an inspection/authorization runbook that **never writes scheduler state and never automatically reruns**;
- require the exact durable pending tuple, exact confirmation phrase and auditable reason;
- positively revalidate unchanged baseline attempt and prior effective-check identity only to establish that the operator is looking at the intended pending record;
- keep issue #7 pending unchanged throughout recovery inspection;
- instruct the operator to rerun the exact canonical run manually if they have independently established that the original POST never occurred;
- let the normal serialized poll observe `baseline+1` under the existing durable pending identity;
- if another actor races and attribution becomes ambiguous, retain pending state and fail closed rather than erasing authority;
- keep recovery permissions read-only for Actions and without `actions:write`;
- add regressions proving recovery cannot call `_write_state` or `rerun_workflow` and cannot clear pending under any accepted request.

## REVIEW-0051 implementation candidate

Development now proceeds through a new `stale_green_bootstrap_authority_review0051_recovery.py` adapter. Normal scheduled polling still reuses the proven REVIEW-0050 V5 closed-origin/pending-observation semantics. The manual recovery surface becomes inspection-only: it validates the exact durable pending tuple plus explicit confirmation/reason, revalidates unchanged baseline attempt and prior effective-check identity, prints the exact canonical run for a separately authorized manual rerun, and **never clears or writes issue #7 and never calls a rerun API**. Its workflow permissions are read-only for Actions and Issues.

Technical candidate `63001400659273252771d32c61665203b7d43ef3` passed Bootstrap #159 / run `35708508061`: **200/200 tests**, **1,894 statements / 856 branches**, **100% line + branch**, and the live read-only PR #2 probe succeeded at **7/100** requests. The active 0051 adapter contains no `_write_state()` call and no `rerun_workflow()` call, and the workflow regression proves manual recovery has `actions: read` + `issues: read` with no corresponding write permission.

Because that technical candidate is proved, REVIEW-0051 was opened on `2017a6ef2143574aa3b43028d776352bfa81d401`. Bootstrap #160 / run `35708741464` then proved the `OPEN` state-only checkpoint SUCCESS. REVIEW-0051 was transitioned to `IN_PROGRESS`; exact head `dd97f30617f1772032def036cdb94b1030001adf` then passed Bootstrap #161 with **200/200 tests**, **1,894 statements / 856 branches**, **100% line + branch**, and live PR #2 probe SUCCESS at **7/100** requests.

Fresh Codex review trigger comment `5773961643` was refused by the platform review quota via comment `5773963162`. **No REVIEW-0051 independent L2 was produced.** Reviewer actor/context and reviewed commit therefore remain unset. This is a tooling-capacity blocker, not approval and not a semantic finding.

## PR #2 relationship

PR #2 remains the durable WORK-0002 implementation branch on `4046e03b1e00a2051d29ccd6dcf5f0af7426259a` as last re-queried. After PR #5 eventually merges, PR #2 must explicitly integrate new `main` and port/reuse the final proven behavior. Pull-request base retargeting must positively create a fresh gate; dynamic `workflow_run.pull_requests[]` is not event-time provenance.

T12 cannot close merely because PR #5 exists or merges. Final WORK-0002 closure still requires a fresh exact-head L2 plus eligible trusted non-author exact-head `APPROVED` collaborator evidence.

## REVIEW-0051 — terminal negative evidence

REVIEW-0051 preserved its successful inspection-only recovery correction, but is now **CLOSED / CHANGES_REQUIRED** on exact head `151fcd13e2fc5b15420de097635b6c9fbc9795ba`.

Integration rehearsal PR #8 reproduced a new real-system P1: PR #2 head `0c06fa7a...` legitimately has two GitHub Actions-owned `MONDE / Merge Gate` checks from Gate #232 and review-event Gate #233. Bootstrap #163 rejected this as malformed because `latest_required_check()` assumed `filter=latest` implies exactly one check globally. Author-side finding `PRR_kwDOUUI5ts8AAAABOoOnSQ` therefore invalidated REVIEW-0051 before any independent L2 ran.

The successor must keep REVIEW-0051's non-mutating recovery semantics while validating every candidate check and selecting the newest legitimate effective check deterministically. Duplicate IDs, malformed identity, wrong app/name/head and invalid status/conclusion remain fail-closed.

A rehearsal-only correction was proved on PR #8: Bootstrap #166 / run `35714306323` passed **202/202 tests**, **1,899 statements / 858 branches**, **100% line + branch**, and the live PR #2 contract probe succeeded against the same multi-check state. The exact proven code has now been ported to PR #5 as the REVIEW-0052 technical candidate; REVIEW-0052 itself remains unopened until this PR #5 head passes its own exact-head proof.

## Current next action

1. Keep all **65** PR #5 inline material threads unresolved.
2. REVIEW-0050 `CLOSED / CHANGES_REQUIRED` checkpoint proof is complete on `71c40aeb...` via Bootstrap #157.
3. Implement the REVIEW-0051 inspection-only recovery adapter without rewriting REVIEW-0050 history.
4. REVIEW-0051 technical candidate proof is complete on `63001400...` via Bootstrap #159.
5. REVIEW-0051 is CLOSED/CHANGES_REQUIRED after real multi-check reproduction PRR_kwDOUUI5ts8AAAABOoOnSQ; do not request REVIEW-0051 approval.
6. Exact-head prove the ported multi-check selector candidate on PR #5 with 100% bootstrap proof + live PR #2 probe.
7. Only after that proof open REVIEW-0052, prove OPEN then IN_PROGRESS/frozen exact head, and request one fresh independent L2.
8. Resolve no historical thread before a clean successor review.
9. WORK-0003 and WORK-0004 remain blocked.

## Resume sequence

1. README.md
2. AGENTS.md
3. docs/00_START_HERE.md
4. PROJECT_STATE.md
5. registry/work-items/WORK-0002.yaml
6. registry/requirements/REQ-0026.yaml
7. registry/tests/TEST-0009.yaml
8. registry/reviews/REVIEW-0049.yaml
9. registry/reviews/REVIEW-0050.yaml
10. issue #7 scheduler state
11. live PR #5 exact HEAD/checks/reviews/65 threads
12. live PR #2 exact HEAD/checks/reviews/threads

MONDE remains public. Never commit credentials, tokens or secrets.
