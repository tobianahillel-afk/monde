from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    "tests/governance/test_l2_hardening_v2.py",
    "tests/governance/test_l2_hardening_materialization.py",
    "tests/governance/test_l2_gate_provenance.py",
    "tests/governance/test_codex_followup_five.py",
    "tests/governance/test_codex_followup_mutation.py",
    "tests/governance/test_t7_closure.py",
    "tests/governance/test_t7_closure_coverage.py",
    "tests/governance/test_t8_findings.py",
    "tests/governance/test_t9_findings.py",
    "tests/governance/test_t9_full_history_mutation.py",
    "tests/governance/test_t9_import_binding.py",
    "tests/governance/test_live_thread_id_parser.py",
    "tests/governance/test_github_live_gate.py",
]
MUTATIONS = {
    "exact-head-checkout": (".github/scripts/governance_l2_hardening.py", 'or (checkout.get("with") or {}).get("ref") != CHECKOUT_REF', 'or False'),
    "complete-review-immutability": (".github/scripts/governance_l2_hardening.py", 'if review_semantic_projection(previous) != review_semantic_projection(current):', 'if False:'),
    "authority-actor-binding": (".github/scripts/governance_l2_hardening.py", 'if actor not in actor_values:', 'if False:'),
    "review-import-materialization": (".github/scripts/governance_l2_hardening.py", 'actual_import = first_status_commit(root, path, str(review.get("status") or ""), head)\n    if actual_import != import_commit:', 'actual_import = first_status_commit(root, path, str(review.get("status") or ""), head)\n    if False:'),
    "requirement-review-import-finalization": (".github/scripts/governance_l2_hardening.py", 'if not review_import_finalized(root, review, after, review_path):', 'if False:'),
    "cold-read-revision-reachability": (".github/scripts/governance_l2_hardening.py", 'if not pass_test_execution_revision_valid(root, test, after):', 'if False:'),
    "progress-transition-enforcement": (".github/scripts/governance_l2_hardening.py", 'if new not in allowed:', 'if False:'),
    "squash-nonreusable-flags": (".github/scripts/governance_l2_hardening.py", 'if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:', 'if False:'),
    "done-task-run-terminal-state": (".github/scripts/governance_l2_hardening.py", 'if not isinstance(item, dict) or item.get("status") not in DONE_TASK_RUN_STATES:', 'if False:'),
    "progress-adoption-nonreusable": (".github/scripts/governance_l2_gate.py", 'or entry.get("historical_only") is not True\n            or entry.get("future_reuse_forbidden") is not True\n            or not h.git_ok(root, "cat-file", "-e", f"{adoption}^{{commit}}")', 'or False\n            or False\n            or not h.git_ok(root, "cat-file", "-e", f"{adoption}^{{commit}}")'),
    "review-squash-explicit-id": (".github/scripts/governance_l2_gate.py", 'if not isinstance(entry, dict) or review_id not in (entry.get("eligible_review_ids") or []):', 'if not isinstance(entry, dict):'),
    "requirement-review-real-revision": ("tools/governance/change_guard.py", 'and review_requirement_revision_valid(root, sha, str(rid), digest, review)', 'and True'),
    "risk-delegation-role-scope": ("tools/governance/change_guard.py", 'and (str(work_items[0]) in work_scope or str(governed.get("full_name") or "") in repo_scope)', 'and True'),
    "test-import-transition-boundary": ("tools/governance/change_guard.py", 'and not external_test_import:', 'and True:'),
    "test-import-not-initial-state": ("tools/governance/change_guard.py", 'if kind == "tests":\n        rid, status = current.get("id"), current.get("status")\n        policy = canonical_machine_spec(root, policy_sha, kind)', 'if False:\n        rid, status = current.get("id"), current.get("status")\n        policy = canonical_machine_spec(root, policy_sha, kind)'),
    "done-test-import-consumption": ("tools/governance/strict_contracts.py", 'elif not test_external_import_bound_and_consumed(test, machine):', 'elif False:'),
    "context-merge-base": ("tools/governance/context_manifest.py", 'merge_base = git(root, "merge-base", base, head).strip()', 'merge_base = base'),
    "done-test-import-materialization": (".github/scripts/governance_l2_followup.py", 'if test.get("external_import") is not None and not test_import_finalized(root, test, head, path):', 'if False:'),
    "t7-policy-predecessor-authority": ("tools/governance/t7_closure.py", 'if not active_predecessor_work_covers(root, before, path):', 'if False:'),
    "t7-adoption-git-binding": ("tools/governance/t7_closure.py", 'entry.get("adoption_commit_sha") != actual', 'False'),
    "t7-review-co-satisfaction": ("tools/governance/t7_closure.py", 'if not any(review_qualifies(root, after, current, digest, floor, review) for review in reviews):', 'if False:'),
    "t7-cold-read-co-satisfaction": ("tools/governance/t7_closure.py", 'if not any(cold_read_qualifies(root, after, current, digest, floor, test) for test in tests):', 'if False:'),
    "t7-policy-revision-binding": ("tools/governance/t7_closure.py", 'and policy_blob(root, reviewed_sha) == policy_blob(root, acceptance_sha)', 'and True'),
    "t7-owner-external-anchor": ("tools/governance/t7_closure.py", 'governed.get("full_name") == actual', 'True'),
    "t7-live-exact-head-approval": ("tools/governance/github_live_gate.py", 'if not approvers:', 'if False:'),
    "t8-continuing-requirement": ("tools/governance/t8_closure.py", 'if kind == "requirements" and not requirement_acceptance_invariant(root, after, current):', 'if kind == "requirements" and False:'),
    "t8-continuing-risk": ("tools/governance/t8_closure.py", 'if kind == "risks" and not cg.risk_acceptance_satisfied(root, after, current):', 'if kind == "risks" and False:'),
    "t8-complete-review-fields": ("tools/governance/t8_closure.py", 'if completion_review_projection(previous) != completion_review_projection(current):', 'if False:'),
    "t8-policy-history": ("tools/governance/t8_closure.py", 'return not touched', 'return True'),
    "t8-work-reopening-scope": ("tools/governance/t8_closure.py", 'if not target_work_reopening_triggered(root, before, after, work_id):', 'if False:'),
    "t8-live-trusted-reviewer": ("tools/governance/github_live_gate.py", 'if reviewer_permission(repo, actor, token) not in TRUSTED_REVIEW_PERMISSIONS:', 'if False:'),
    "t8-live-l2-attestation": ("tools/governance/github_live_gate.py", 'if not l2_approval_body_valid(str(review.get("body") or ""), head):', 'if False:'),
    "t9-full-history-policy": ("tools/governance/t9_closure.py", '"--full-history",\n            "--topo-order",', '"--topo-order",'),
    "t9-review-import-continuing": ("tools/governance/t9_closure.py", 'and review_import_finalized(root, review, acceptance_sha, path)', 'and True'),
    "t9-test-import-continuing": ("tools/governance/t9_closure.py", 'and test_import_finalized(root, test, acceptance_sha, path)', 'and True'),
    "t9-import-commit-immutability": ("tools/governance/t9_closure.py", 'review_import_binding_allowed(root, current, after, path)\n                or review_import_finalized(root, current, after, path)', 'True\n                or review_import_finalized(root, current, after, path)'),
    "t9-base-policy-authority": ("tools/governance/t9_closure.py", 'if not base_preexisting_work_covers(root, base, path):', 'if False:'),
    "t9-new-reopening-trigger": ("tools/governance/t9_closure.py", 'if not new_reopening_trigger(root, before, after, work_id):', 'if False:'),
    "t9-durable-thread-identities": ("tools/governance/github_live_gate.py", 'if durable_ids != unresolved:', 'if False:'),
    "t9-thread-id-base64url": ("tools/governance/github_live_gate.py", 'THREAD_ID = re.compile(r"(?<![A-Za-z0-9_-])(PRRT_[A-Za-z0-9_-]+)(?![A-Za-z0-9_-])")', 'THREAD_ID = re.compile(r"\\b(PRRT_[A-Za-z0-9_-]+)\\b")'),
}


def main() -> int:
    originals: dict[str, str] = {}
    killed = 0
    for name, (target, needle, replacement) in MUTATIONS.items():
        original = originals.setdefault(target, (ROOT / target).read_text(encoding="utf-8"))
        if original.count(needle) != 1:
            print(f"L2 MUTATION ERROR {name}: target occurrence count != 1", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="monde-l2-mutation-") as temp_dir:
            temp = Path(temp_dir)
            for item in ("tools", "tests", ".github", "schemas", "registry", "pyproject.toml"):
                src = ROOT / item
                dst = temp / item
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            mutated = temp / target
            mutated.write_text(original.replace(needle, replacement, 1), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(temp)
            proc = subprocess.run([sys.executable, "-m", "pytest", "-q", *TESTS], cwd=temp, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if proc.returncode == 0:
                print(f"L2 MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"L2 MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE L2 mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())