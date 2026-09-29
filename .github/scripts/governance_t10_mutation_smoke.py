from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ["tests/governance/test_t10_findings.py"]
MUTATIONS = {
    "t10-integration-provenance-authority": (
        "tools/governance/t10_closure.py",
        "if not t9.base_preexisting_work_covers(root, base, INTEGRATION_PROVENANCE_PATH):",
        "if False:",
    ),
    "t10-global-requirement-revalidation": (
        "tools/governance/t10_closure.py",
        'if not t9.requirement_acceptance_invariant(root, after, record):',
        "if False:",
    ),
    "t10-global-risk-revalidation": (
        "tools/governance/t10_closure.py",
        'if not cg.risk_acceptance_satisfied(root, after, record):',
        "if False:",
    ),
    "t10-review-comment-trigger": (
        ".github/workflows/governance.yml",
        "  pull_request_review_comment:\n    types: [created, edited, deleted]\n",
        "",
    ),
    "t10-gate-wiring": (
        ".github/workflows/_governance-core.yml",
        "          python -m tools.governance.t10_closure . \\\n",
        "          python -m tools.governance.t9_closure . \\\n",
    ),
}


def main() -> int:
    originals: dict[str, str] = {}
    killed = 0
    for name, (target, needle, replacement) in MUTATIONS.items():
        original = originals.setdefault(target, (ROOT / target).read_text(encoding="utf-8"))
        if original.count(needle) != 1:
            print(f"T10 MUTATION ERROR {name}: target occurrence count != 1", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="monde-t10-mutation-") as temp_dir:
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
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *TESTS],
                cwd=temp,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if proc.returncode == 0:
                print(f"T10 MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"T10 MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE T10 mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
