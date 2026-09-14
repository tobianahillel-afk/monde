from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ".github/scripts/governance_l2_hardening.py"
TESTS = [
    "tests/governance/test_l2_hardening_v2.py",
    "tests/governance/test_l2_hardening_materialization.py",
]
MUTATIONS = {
    "exact-head-checkout": ('or (checkout.get("with") or {}).get("ref") != CHECKOUT_REF', 'or False'),
    "complete-review-immutability": ('if review_semantic_projection(previous) != review_semantic_projection(current):', 'if False:'),
    "authority-actor-binding": ('if actor not in actor_values:', 'if False:'),
    "review-import-materialization": ('actual_import = first_status_commit(root, path, str(review.get("status") or ""), head)\n    if actual_import != import_commit:', 'actual_import = first_status_commit(root, path, str(review.get("status") or ""), head)\n    if False:'),
    "requirement-review-import-finalization": ('if not review_import_finalized(root, review, after, review_path):', 'if False:'),
    "cold-read-revision-reachability": ('if not pass_test_execution_revision_valid(root, test, after):', 'if False:'),
    "progress-transition-enforcement": ('if new not in allowed:', 'if False:'),
    "squash-nonreusable-flags": ('if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:', 'if False:'),
    "done-task-run-terminal-state": ('if not isinstance(item, dict) or item.get("status") not in DONE_TASK_RUN_STATES:', 'if False:'),
}


def main() -> int:
    original = (ROOT / TARGET).read_text(encoding="utf-8")
    killed = 0
    for name, (needle, replacement) in MUTATIONS.items():
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
            mutated = temp / TARGET
            mutated.write_text(original.replace(needle, replacement, 1), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(temp)
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *TESTS],
                cwd=temp,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if proc.returncode == 0:
                print(f"L2 MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"L2 MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE L2 mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
