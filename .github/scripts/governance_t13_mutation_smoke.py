from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    "tests/governance/test_t13_findings.py",
    "tests/governance/test_thread_state_poll.py",
    "tests/governance/test_github_live_gate.py",
]
MUTATIONS = {
    "t13-review-event-gate-runs": (
        "tools/governance/thread_state_poll.py",
        'PR_FAMILY_EVENTS = {"pull_request", "pull_request_review", "pull_request_review_comment"}',
        'PR_FAMILY_EVENTS = {"pull_request"}',
    ),
    "t13-terminal-import-binding": (
        "tools/governance/t11_closure.py",
        "            if not raw_import:\n",
        "            if False:\n",
    ),
    "t13-ambiguous-first-status": (
        "tools/governance/t11_closure.py",
        "            if len(boundaries) > 1:\n",
        "            if False:\n",
    ),
    "t13-executable-command-proof": (
        "tools/governance/t11_closure.py",
        "    return any(tuple(command[: len(expected)]) == expected for command in _logical_run_commands(job))\n",
        "    return any(' '.join(expected) in ' '.join(command) for command in _logical_run_commands(job))\n",
    ),
    "t13-active-work-binding": (
        "tools/governance/github_live_gate.py",
        "    return candidates[0] if len(candidates) == 1 else None\n",
        '    return ("registry/work-items/WORK-0002.yaml", "WORK-0002")\n',
    ),
}


def main() -> int:
    originals: dict[str, str] = {}
    killed = 0
    for name, (target, needle, replacement) in MUTATIONS.items():
        original = originals.setdefault(target, (ROOT / target).read_text(encoding="utf-8"))
        if original.count(needle) != 1:
            print(f"T13 MUTATION ERROR {name}: target occurrence count != 1", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="monde-t13-mutation-") as temp_dir:
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
                print(f"T13 MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"T13 MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE T13 mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
