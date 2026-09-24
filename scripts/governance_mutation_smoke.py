from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    "review-completion": (
        "tools/governance/validate_repo.py",
        'if data.get("status") != "COMPLETE":',
        'if False:',
    ),
    "progress-reverse-membership": (
        "tools/governance/validate_repo.py",
        'if wid not in found:',
        'if False:',
    ),
    "action-sha-pinning": (
        "tools/governance/validate_repo.py",
        'elif not PINNED_ACTION.fullmatch(item):',
        'elif False:',
    ),
    "done-progress-dimensions": (
        "tools/governance/validate_repo.py",
        'if isinstance(value, str) and value in progress_states and value not in DONE_PROGRESS_ALLOWED:',
        'if False:',
    ),
    "review-independence-rank": (
        "tools/governance/validate_repo.py",
        'if target_rank >= 0 and max_rank < target_rank:',
        'if False:',
    ),
    "canonical-review-outcome": (
        "tools/governance/validate_repo.py",
        'if data.get("outcome") not in REVIEW_OUTCOMES_APPROVING:',
        'if False:',
    ),
    "dependency-lifecycle": (
        "tools/governance/strict_contracts.py",
        'if target is not None and target.get("status") not in allowed:',
        'if False:',
    ),
    "review-work-binding": (
        "tools/governance/strict_contracts.py",
        'if wid not in review_targets(review):',
        'if False:',
    ),
    "required-test-pass": (
        "tools/governance/strict_contracts.py",
        'if test is None or not pass_test_has_execution(test) or not pass_test_revision_valid(root, test):',
        'if False:',
    ),
    "progress-unique-placement": (
        "tools/governance/strict_contracts.py",
        'if previous is not None:',
        'if False:',
    ),
    "review-independence-target-schema": (
        "schemas/registry/work-items.schema.json",
        '"enum": ["L0", "L1", "L2", "L3", "L0_TARGET", "L1_TARGET", "L2_TARGET", "L3_TARGET"]',
        '"type": "string"',
    ),
    "specification-completion-gate": (
        "tools/governance/strict_contracts.py",
        'if isinstance(completion, dict) and completion.get("specification_gates_checked") is not True:',
        'if False:',
    ),
    "done-progress-complete-set": (
        "tools/governance/strict_contracts.py",
        'if missing:',
        'if False:',
    ),
    "canonical-review-severity": (
        "tools/governance/strict_contracts.py",
        'if rank <= BLOCKING_REVIEW_RANK:',
        'if False:',
    ),
    "context-dependency-closure": (
        "tools/governance/context_manifest.py",
        'neighbors = forward.get(rid, set()) | reverse.get(rid, set())',
        'neighbors = forward.get(rid, set())',
    ),
    "review-freshness-scope": (
        "tools/governance/change_guard.py",
        'if file_path in endpoint_set\n                and change_relevant_to_work(root, path, work, reviewed, head, file_path)',
        'if change_relevant_to_work(root, path, work, reviewed, head, file_path)',
    ),
    "review-freshness-predecessor-exception-scope": (
        "tools/governance/change_guard.py",
        "                and inherited_predecessor_review_freshness_exception(\n                    root, work, rid, review, head\n                )\n",
        "                and True\n",
    ),
    "assurance-min-review": (
        "tools/governance/strict_contracts.py",
        'if assurance_level in ASSURANCE_MIN_REVIEW_RANK and declared_rank < ASSURANCE_MIN_REVIEW_RANK[assurance_level]:',
        'if False:',
    ),
    "review-complete-sha": (
        "tools/governance/strict_contracts.py",
        'if not FULL_COMMIT_SHA.fullmatch(reviewed_sha):',
        'if False:',
    ),
    "na-justification": (
        "tools/governance/strict_contracts.py",
        'if state.get("status") == "DONE" and value == "NOT_APPLICABLE":',
        'if False:',
    ),
    "context-registry-change-seed": (
        "tools/governance/context_manifest.py",
        'if rel in files:',
        'if False:',
    ),
    "test-pass-execution-sha-schema": (
        "schemas/registry/tests.schema.json",
        '"pattern": "^[0-9a-f]{40}$"',
        '"type": "string"',
    ),
    "lifecycle-initial-state": (
        "tools/governance/change_guard.py",
        "if not record_introduction_allowed(root, previous_sha, sha, head, kind, current):",
        "if False:",
    ),
    "requirement-acceptance-precondition": (
        "tools/governance/change_guard.py",
        "and not requirement_acceptance_satisfied(root, sha, current):",
        "and False:",
    ),
    "review-full-immutable-sha": (
        "tools/governance/change_guard.py",
        "if not FULL_COMMIT_SHA.fullmatch(reviewed):",
        "if False:",
    ),
    "blocking-finding-authority": (
        "tools/governance/strict_contracts.py",
        "if disposition == \"ACCEPTED\" and not accepted_finding_authorized(root, assurance_level, finding):",
        "if False:",
    ),
    "required-test-semantic-freshness": (
        "tools/governance/change_guard.py",
        "return test_semantic_projection(old_test) != test_semantic_projection(new_test)",
        "return False",
    ),
    "endpoint-merge-base": (
        "tools/governance/change_guard.py",
        "endpoint_files = endpoint_changed_files(root, base, head)",
        "endpoint_files = changed_files(root, base, head)",
    ),
    "duplicate-yaml-key-rejection": (
        "tools/governance/__init__.py",
        "yaml.SafeLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)",
        "# duplicate-key guard removed by mutation",
    ),
    "requirement-jcs-recompute": (
        "tools/governance/change_guard.py",
        "if requirement_normative_digest(root, requirement, identity_policy) != digest:",
        "if False:",
    ),
    "risk-acceptance-authority": (
        "tools/governance/change_guard.py",
        'if kind == "risks" and before != "ACCEPTED" and after == "ACCEPTED" and not risk_acceptance_satisfied(root, sha, current):',
        'if False:',
    ),
    "repository-owner-binding": (
        "tools/governance/strict_contracts.py",
        "return repository_owner_evidence_valid(acceptance, policy)",
        "return True",
    ),
    "external-review-import-finalization": (
        "tools/governance/strict_contracts.py",
        "if not review_external_import_finalized(review, machine):",
        "if False:",
    ),
    "test-execution-revision-reachability": (
        "tools/governance/strict_contracts.py",
        "return pass_test_execution_revision_valid(root, test)",
        "return True",
    ),
    "closed-review-completion": (
        "tools/governance/strict_contracts.py",
        'if review.get("status") != "COMPLETE":',
        'if False:',
    ),
    "squash-integration-tree-binding": (
        "tools/governance/proof_contracts.py",
        "if source_tree == expected_tree and integrated_tree == expected_tree:",
        "if True:",
    ),
    "squash-integration-reachability-fallback": (
        "tools/governance/proof_contracts.py",
        "return squash_integration_revision_valid(root, test, target)",
        "return True",
    ),
    "malformed-yaml-history-binding": (
        "tools/governance/change_guard.py",
        "if file_exists_at(root, sha, path) and historical_malformed_yaml_allowed(root, path, sha, head):",
        "if file_exists_at(root, sha, path):",
    ),
}


def main() -> int:
    originals = {
        rel: (ROOT / rel).read_text(encoding="utf-8")
        for rel, _, _ in MUTATIONS.values()
    }
    killed = 0
    for name, (target_rel, needle, replacement) in MUTATIONS.items():
        original = originals[target_rel]
        if original.count(needle) != 1:
            print(f"MUTATION ERROR {name}: target occurrence count != 1", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="monde-mutation-") as temp_dir:
            temp = Path(temp_dir)
            for item in ("tools", "tests", "schemas", "registry", "pyproject.toml"):
                src = ROOT / item
                dst = temp / item
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            mutated = temp / target_rel
            mutated.write_text(original.replace(needle, replacement, 1), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(temp)
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/governance"],
                cwd=temp,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if proc.returncode == 0:
                print(f"MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
