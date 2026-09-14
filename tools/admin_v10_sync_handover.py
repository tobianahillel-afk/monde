from pathlib import Path
import sys

root = Path(sys.argv[1])
work_path = root / "registry/work-items/WORK-0001.yaml"
test8_path = root / "registry/tests/TEST-0008.yaml"
state_path = root / "PROJECT_STATE.md"


def one(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return text.replace(old, new, 1)

w = work_path.read_text(encoding="utf-8")
w = one(w, "    - REVIEW-0026/F-3\n\nread_before:\n", "    - REVIEW-0026/F-3\n    - REVIEW-0027\n\nread_before:\n", "scope evidence REVIEW-0027")
w = one(w, "  - registry/reviews/REVIEW-0026.yaml\n  - registry/tests/TEST-0005.yaml\n", "  - registry/reviews/REVIEW-0026.yaml\n  - registry/reviews/REVIEW-0027.yaml\n  - registry/tests/TEST-0005.yaml\n", "read_before REVIEW-0027")
w = one(w, "  - registry/reviews/REVIEW-0026.yaml\n  - registry/requirements/REQ-0005.yaml\n", "  - registry/reviews/REVIEW-0026.yaml\n  - registry/reviews/REVIEW-0027.yaml\n  - registry/requirements/REQ-0005.yaml\n", "affected docs REVIEW-0027")
w = one(w, "registry/reviews/REVIEW-0026.yaml, registry/requirements/REQ-0023.yaml", "registry/reviews/REVIEW-0026.yaml, registry/reviews/REVIEW-0027.yaml, registry/requirements/REQ-0023.yaml", "T6 expected REVIEW-0027")
w = one(w, "    - {id: RUN-3, objective: \"Post-merge bootstrap assurance correction and fresh re-review\", tasks: [T6], exit_condition: \"Current REVIEW-0026 corrections have revision-bound proof, TEST-0008 has real fresh-context evidence, a later L2 is approval-capable, and no unresolved blocking finding remains\", status: IN_REVIEW}\n", "    - {id: RUN-3, objective: \"Post-merge bootstrap assurance correction and fresh re-review\", tasks: [T6], exit_condition: \"REVIEW-0027/TEST-0008/REQ acceptance provenance and status-machines v10 receive one final exact-SHA fresh L2, all material findings are independently resolved or validly dispositioned, and completion gates are synchronized\", status: IN_REVIEW}\n", "RUN-3 exit")
w = one(w, "  completed_reviews: []\n", "  completed_reviews: [REVIEW-0027]\n", "completed reviews")
w = one(w, "    - \"REQ-0023/24/25 remain PROPOSED until exact-digest independent review plus qualifying TEST-0008 evidence exist\"\n", "    - \"REQ-0023/24/25 may become ACCEPTED only after exact-digest independent review plus qualifying TEST-0008 evidence resolve under the canonical acceptance machine\"\n", "acceptance regression")
w = one(w, "    - \"TEST-0008 remains reserved for genuine external fresh-context cold-read execution\"\n", "    - \"REVIEW-0027 external L2: c12a5b55c89168f20c028c2964da16de6f95ac56 reviewed by GitHub Actions Copilot CLI run 34793888383; import f78d5575a94b49d90abb166003cf4520bf167d3a → binding db2f737ceda531916590c4cc32d9f46964d601e0; authorization metadata consumed in e247a0e4c92b401828625007ce3479c90182b944\"\n    - \"TEST-0008 external cold-read result: exact execution tree c12a5b55c89168f20c028c2964da16de6f95ac56 → PASS import 4035cbd9fe5a9dc113d95ba83ad3c72d7d0b76f1 → binding/authorization consumption metadata 3125334eb00a8a3da28cb94271316856147965eb\"\n    - \"REQ-0023/24/25 atomic acceptance commit: 74dc253d849e3b6b6570fe55df415f5e9da65ab2\"\n", "real system current evidence")
old_compat = "    This active WORK record is a current routing/index record; immutable detail remains in linked REQ/REVIEW/TEST records and Git history. status-machines v9 remains canonical. content-identity v2 clarifies REQUIREMENT_NORMATIVE_V1 with byte-exact RFC 8785/JCS serialization. REQ-0023/24/25 remain PROPOSED. TEST-0008 remains independent-only and unqualified. Current TEST lifecycle/result identity is authoritative only in each TEST record. PROJECT_STATE and this WORK use conditional TEST-0006 routing that is intended to remain correct before, during and after a qualifying PASS. Cross-branch WORK-0002 implementation proof remains behind explicit PR #2 checkout.\n"
new_compat = "    This active WORK record is a current routing/index record; immutable detail remains in linked REQ/REVIEW/TEST records and Git history. status-machines v10 is canonical and adds a one-shot, source/executor/exact-revision-bound import path for TEST executions that genuinely completed externally before repository lifecycle materialization; it does not create a generic PLANNED→PASS edge. content-identity v2 remains RFC 8785/JCS byte-exact. REVIEW-0027 is COMPLETE/APPROVE_WITH_FOLLOWUP on exact candidate c12a5b55, TEST-0008 carries the matching L2 cold-read evidence, and REQ-0023/24/25 were atomically ACCEPTED only after both evidence halves resolved. Current TEST lifecycle/result identity remains authoritative only in each TEST record. Historical findings remain open until the final post-v10 exact-SHA L2 verifies the synchronized handover and import semantics. Cross-branch WORK-0002 implementation proof remains behind explicit PR #2 checkout.\n"
w = one(w, old_compat, new_compat, "compatibility notes")
insert_after = "    - \"Current TEST execution identity is read only from TEST records\"\n"
w = one(w, insert_after, insert_after + "    - \"REVIEW-0027 is COMPLETE/APPROVE_WITH_FOLLOWUP from fresh-context GitHub Actions Copilot CLI run 34793888383 on exact c12a5b55; all three requirement digests matched and all fifteen cold-read outcomes were PASS\"\n    - \"status-machines v10 preauthorized and then consumed truthful external imports for REVIEW-0027 and TEST-0008 without replaying lifecycle checkpoints after completion\"\n    - \"TEST-0008 result import 4035cbd9 is exact-SHA-bound to c12a5b55 and was metadata-bound/consumed by 3125334e\"\n    - \"REQ-0023/24/25 were atomically accepted in 74dc253d after REVIEW-0027 and TEST-0008 qualified\"\n", "validation executed current")
start = w.index("  known_gaps:\n")
end = w.index("\nrisk:\n", start)
new_gaps = '''  known_gaps:
    - "status-machines v10, REVIEW-0027/TEST-0008 materialization, requirement acceptance and this synchronized handover are newer than the c12a5b55 L2 and require one final exact-SHA fresh-context L2 before WORK-0001 can complete."
    - "Historical open findings remain OPEN until that final independent review explicitly verifies closure or a policy-valid disposition is recorded."
    - "WORK-0001 T6, RUN-3 and hard completion gates remain IN_REVIEW/false until the final v10 review passes."
    - "WORK-0002/PR #2 remains separate IN_REVIEW work and must integrate merged WORK-0001 before closure."
'''
w = w[:start] + new_gaps + w[end:]
old_run = '  - {run: RUN-3, date: "2026-09-14", note: "REVIEW-0026 returned CHANGES_REQUIRED on frozen 4f8cebee. Corrections now use independently-resolvable GitHub owner authority, RFC 8785/JCS byte-exact requirement identity and a current review-first handover. TEST-0005 and TEST-0007 have current exact-SHA PASS chains. The first synchronized TEST-0006 REVIEW-0026 attempt on d3997dd1 correctly FAILed because handover text would still order the rerun after PASS; that FAIL is bound in 8e8e54a3 and PROJECT_STATE is now conditionally transition-stable. Continue TEST-0006 only until one qualifying current PASS exists, then freeze and request fresh L2 + TEST-0008 cold read."}\n'
new_run = '  - {run: RUN-3, date: "2026-09-14", note: "Fresh-context Copilot L2 run 34793888383 approved exact c12a5b55 with follow-up, independently parsed WORK-0001, verified REVIEW-0026/F-1/F-2/F-3, recomputed all three JCS digests and returned 15/15 TEST-0008 outcomes PASS. status-machines v10 truthfully imported REVIEW-0027 and TEST-0008 without lifecycle replay; REQ-0023/24/25 were atomically ACCEPTED in 74dc253d. RUN-3 remains IN_REVIEW until one final exact-SHA L2 verifies the post-v10 materialization/acceptance/handover state."}\n'
w = one(w, old_run, new_run, "RUN-3 log")
work_path.write_text(w, encoding="utf-8")

t = test8_path.read_text(encoding="utf-8")
t = one(t, "Every v9 required cold-read outcome", "Every v10 required cold-read outcome", "TEST8 invariant v10")
t = one(t, "verify v9 rejects it", "verify v10 rejects it", "TEST8 adversarial v10")
test8_path.write_text(t, encoding="utf-8")

state = '''# MONDE — Project State

Status: Accepted  
Canonical operational state: Yes

> Fast resume point. Durable intent lives in Git. Live PR/check/thread truth is volatile and must be re-queried before review or merge decisions. Mutable TEST lifecycle/result truth lives only in each `registry/tests/TEST-*.yaml` record.

## Current phase / lot / blocker

- **PHASE-0 — Specification, repository governance and canonical documentation**
- **LOT-0 — AI-first repository operating system**
- **SUBLOT-0.1 — Governance bootstrap / post-merge assurance correction**
- `WORK-0001` remains `IN_REVIEW / A3` on PR #3 / `chore/work-0001-assurance-closure`.
- `WORK-0002` remains separate `IN_REVIEW` work on PR #2 and must integrate merged WORK-0001 before it can close.
- WORK-0003 and WORK-0004 have not started.

PR #1 remains historically squash-merged into `main` as `b88e9edf2ac445e8f730eb1a2769a6d5a06a42f1`.

## Latest independent review and cold read

A fresh-context GitHub Actions Copilot CLI L2 reviewed exact candidate `c12a5b55c89168f20c028c2964da16de6f95ac56` in workflow run `34793888383` / job `103823151339`.

The independent result was **APPROVE_WITH_FOLLOWUP** with no material R1/R2/R3 finding. It independently parsed WORK-0001, confirmed `IN_REVIEW / A3` and RUN-3 `IN_REVIEW`, recomputed all three REQUIREMENT_NORMATIVE_V1 RFC 8785/JCS digests while REQ-0023/24/25 were PROPOSED, verified REVIEW-0026/F-1/F-2/F-3 as corrected, and returned PASS for all five cold-read outcomes on each of the three requirements (15/15).

The result is durably represented by `REVIEW-0027` and `TEST-0008`; do not substitute author reasoning for those records.

### REVIEW-0027 provenance

- one-shot authorization parent: `4b15dc41c2489239d932827880f612d7ef55bbfa`
- first materialization/import: `f78d5575a94b49d90abb166003cf4520bf167d3a`
- review-record import binding: `db2f737ceda531916590c4cc32d9f46964d601e0`
- authorization-consumption metadata commit: `e247a0e4c92b401828625007ce3479c90182b944`
- the canonical authorization's `consumed_by_commit` is the actual import commit `f78d5575a94b49d90abb166003cf4520bf167d3a`

### TEST-0008 provenance

TEST-0008 genuinely executed externally while its canonical record was still PLANNED. status-machines v10 therefore used a record-specific one-shot import instead of fabricating READY/RUNNING checkpoints after the execution had already completed.

- exact execution tree: `c12a5b55c89168f20c028c2964da16de6f95ac56`
- source: `github-actions-run:34793888383:attempt:1`
- executor context: `github-actions:34793888383:1:test-0008-v2`
- first PASS result import: `4035cbd9fe5a9dc113d95ba83ad3c72d7d0b76f1`
- result/history binding + authorization-consumption metadata: `3125334eb00a8a3da28cb94271316856147965eb`
- the canonical authorization's `consumed_by_commit` is the actual PASS import commit `4035cbd9fe5a9dc113d95ba83ad3c72d7d0b76f1`

Read `registry/tests/TEST-0008.yaml` for mutable current lifecycle/result truth.

## Requirement acceptance

REQ-0020/0021/0022 remain `SUPERSEDED` premature-acceptance history.

After REVIEW-0027 and TEST-0008 both qualified, REQ-0023/0024/0025 were atomically transitioned `PROPOSED → ACCEPTED` in commit `74dc253d849e3b6b6570fe55df415f5e9da65ab2`. That commit changed only each requirement's status and added `REVIEW-0027` to `verification.acceptance_evidence`; it did not modify normative statements, dependencies, verification method or declared digests.

The exact reviewed digests remain:

- REQ-0023: `sha256:2c6e649de911822268b7faea6c3004e6c866af15e0b9470cfaba612481dd066b`
- REQ-0024: `sha256:a9ba33cbb408b322be0ef9093c059ed2c8799be8a72b4468de48cc049d2fb4c4`
- REQ-0025: `sha256:93a7671272f7c6f38374ac3714af07a8786c645180e0453feb5620fe3a43db67`

## Canonical governance contract

`registry/status-machines.yaml` version 10 is canonical. v10 preserves the normal TEST lifecycle and adds only a record-specific, exact-source/executor/revision-bound one-shot external execution import mechanism. A consumed authorization cannot be reused and the mechanism does not create a generic `PLANNED → PASS` transition.

`registry/content-identity.yaml` version 2 remains the byte-exact RFC 8785/JCS requirement identity contract. `registry/acceptance-authority.yaml` version 1 remains the authority matrix.

## Historical findings

REVIEW-0027 independently verified REVIEW-0026/F-1/F-2/F-3 corrections on `c12a5b55…`; however the v10 import mechanism, evidence materialization, requirement acceptance and this handover were created afterward. Historical findings therefore remain OPEN in WORK-0001 until one final exact-SHA fresh-context L2 verifies the complete post-v10 state. Do not resolve threads/findings merely by author assertion.

## WORK-0002 cross-branch boundary

The WORK-0002 record on PR #3 is only the globally readable lifecycle/dependency mirror while WORK-0001 closes. Before editing or validating WORK-0002 implementation, query live PR #2 and checkout `feat/work-0002-governance-ci` or its integrated successor. Do not canonize volatile PR #2 HEAD/check/thread state here.

## Repository visibility

MONDE intentionally remains **public** by explicit owner decision. Never commit credentials/tokens/secrets, private/personal datasets or user-identifying runtime data. Sensitive runtime material remains outside Git.

## Next action

1. Keep WORK-0001/T6/RUN-3 `IN_REVIEW`; keep hard completion gates false and historical findings OPEN.
2. Query live PR #3 and freeze its current synchronized HEAD after this handover commit.
3. Run one final **fresh-context L2** on that exact SHA, separate from the authoring context. It must inspect status-machines v10, the REVIEW-0027 and TEST-0008 one-shot provenance chains, atomic REQ-0023/24/25 acceptance, current WORK-0001/PROJECT_STATE consistency, historical findings, WORK-0002 branch isolation, and the full accumulated PR for any remaining material defect.
4. Do not mutate the frozen candidate while the final review runs.
5. If the final L2 is negative, import it truthfully and correct/re-prove. If it is approval-capable with no unresolved material defect, preserve its review provenance, independently close the verified historical findings/threads, synchronize WORK-0001/progress/completion, and only then merge PR #3.
6. After PR #3 merges, integrate new main into PR #2, rerun its full gate/fresh L2, finish WORK-0002, then proceed to WORK-0003 and WORK-0004.

## Resume sequence

1. `README.md`
2. `AGENTS.md`
3. `docs/00_START_HERE.md`
4. this file
5. `registry/work-items/WORK-0001.yaml`
6. `registry/status-machines.yaml`
7. `registry/reviews/REVIEW-0027.yaml`
8. `registry/tests/TEST-0008.yaml`
9. `registry/requirements/REQ-0023.yaml` through `REQ-0025.yaml`
10. `registry/reviews/REVIEW-0026.yaml`
11. `registry/tests/TEST-0005.yaml`, `TEST-0006.yaml`, `TEST-0007.yaml`
12. `registry/content-identity.yaml`
13. `registry/acceptance-authority.yaml`
14. `registry/work-items/WORK-0002.yaml` and `registry/progress/matrix.yaml`
15. live PR #3 reviews/threads and live PR #2 state

No prior chat history is required.
'''
state_path.write_text(state, encoding="utf-8")
