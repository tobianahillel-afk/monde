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
    "tests/governance/test_t11_repository_wiring.py",
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
        "        if any(tuple(command) == expected for command in commands):\n",
        "        if any(tuple(command[: len(expected)]) == expected for command in commands):\n",
    ),
    "t13-step-control-enforcement": (
        "tools/governance/t11_closure.py",
        "        if not _execution_controls_safe(job, step, allowed_job_ifs, allowed_step_ifs):\n            continue\n        run = step.get(\"run\")\n",
        "        if False:\n            continue\n        run = step.get(\"run\")\n",
    ),
    "t13-inherited-execution-controls": (
        "tools/governance/t11_closure.py",
        "def _steps_execute_prefix(\n    job: dict[str, Any],\n    expected: tuple[str, ...],\n    *,\n    workflow: dict[str, Any] | None = None,\n    allowed_job_ifs: frozenset[str] = frozenset(),\n    allowed_step_ifs: frozenset[str] = frozenset(),\n) -> bool:\n    if not _inherited_execution_controls_safe(workflow, job):\n        return False\n",
        "def _steps_execute_prefix(\n    job: dict[str, Any],\n    expected: tuple[str, ...],\n    *,\n    workflow: dict[str, Any] | None = None,\n    allowed_job_ifs: frozenset[str] = frozenset(),\n    allowed_step_ifs: frozenset[str] = frozenset(),\n) -> bool:\n    if False:\n        return False\n",
    ),
    "t13-background-command-mask": (
        "tools/governance/t11_closure.py",
        '_FAILURE_MASKING_SHELL_FRAGMENTS = ("||", "&&", "&", ";", "|", ">", "<", "`", "$(")',
        '_FAILURE_MASKING_SHELL_FRAGMENTS = ("||", "&&", ";", "|", ">", "<", "`", "$(")',
    ),
    "t13-dependency-review-required": (
        ".github/workflows/governance.yml",
        "          test '${{ needs.dependency-review.result }}' = 'success'\n",
        "          true\n",
    ),
    "t13-shell-function-shadow": (
        ".github/workflows/governance.yml",
        "        run: python -m tools.governance.thread_state_poll\n",
        "        run: |\n          python() {\n            true\n          }\n          python -m tools.governance.thread_state_poll\n",
    ),
    "t13-dependency-action-binding": (
        ".github/workflows/governance.yml",
        "        uses: actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0\n",
        "        run: true\n",
    ),
    "t13-final-live-gate-wiring": (
        ".github/workflows/governance.yml",
        "          python -m tools.governance.github_live_gate \\\n",
        "          python -m tools.governance.github_live_gate_disabled \\\n",
    ),
    "t13-core-command-inventory": (
        ".github/workflows/_governance-core.yml",
        "          python -m tools.governance.context_manifest . \\\n",
        "          python -m tools.governance.context_manifest_disabled . \\\n",
    ),
    "t13-codeql-action-binding": (
        ".github/workflows/governance.yml",
        "        uses: github/codeql-action/init@b96794f015dfd88f77b49b1c93e0fa7110f94c63 # v4\n",
        "        run: true\n",
    ),
    "t13-checkout-ref-binding": (
        ".github/workflows/governance.yml",
        "          ref: ${{ github.event.pull_request.head.sha }}\n",
        "          ref: deadbeef\n",
    ),
    "t13-shell-split-function-shadow": (
        ".github/workflows/governance.yml",
        "        run: python -m tools.governance.thread_state_poll\n",
        "        run: |\n          function python\n          {\n            true\n          }\n          python -m tools.governance.thread_state_poll\n",
    ),
    "t13-shell-subshell-function-shadow": (
        ".github/workflows/governance.yml",
        "        run: python -m tools.governance.thread_state_poll\n",
        "        run: |\n          python() (\n            true\n          )\n          python -m tools.governance.thread_state_poll\n",
    ),
    "t13-dependency-probe-binding": (
        ".github/workflows/governance.yml",
        "        id: depgraph\n",
        "        id: depgraph_disabled\n",
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
