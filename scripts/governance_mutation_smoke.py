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
        'if data.get("status") not in {"COMPLETE", "CLOSED"}:',
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
        'if isinstance(value, str) and value in GLOBAL_STATUSES and value not in DONE_PROGRESS_ALLOWED:',
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
        'if test is None or test.get("status") != "PASS":',
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
        'if rank <= BLOCKING_REVIEW_RANK and finding.get("disposition") not in {"RESOLVED", "ACCEPTED"}:',
        'if False:',
    ),
    "context-dependency-closure": (
        "tools/governance/context_manifest.py",
        'neighbors = forward.get(rid, set()) | reverse.get(rid, set())',
        'neighbors = forward.get(rid, set())',
    ),
    "review-freshness-scope": (
        "tools/governance/change_guard.py",
        'if change_relevant_to_work(root, path, work, reviewed, head, file_path)',
        'if True',
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
            for item in ("tools", "tests", "schemas", "pyproject.toml"):
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
