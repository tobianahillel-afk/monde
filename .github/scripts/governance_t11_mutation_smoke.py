from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = [
    "tests/governance/test_t11_findings.py",
    "tests/governance/test_t11_repository_wiring.py",
    "tests/governance/test_thread_state_poll.py",
]
MUTATIONS = {
    "t11-provenance-bootstrap-audit": (
        "tools/governance/t11_closure.py",
        "    if observed == EXPECTED_PROVENANCE_BOOTSTRAP_COMMITS:\n        return []\n",
        "    if True:\n        return []\n",
    ),
    "t11-inherited-provenance-merge-filter": (
        "tools/governance/t11_closure.py",
        "    return [sha for sha in commits if not merge_inherits_provenance_blob(root, sha)]\n",
        "    return commits\n",
    ),
    "t11-full-history-import-materialization": (
        "tools/governance/t11_closure.py",
        '            "--full-history",\n            "--reverse",\n            "--topo-order",\n            head,\n',
        '            "--reverse",\n            "--topo-order",\n            head,\n',
    ),
    "t11-squash-history-is-not-evidence-eligibility": (
        "tools/governance/t11_closure.py",
        "        if not isinstance(entry, dict):\n            continue\n",
        "        if not isinstance(entry, dict) or record.get(\"id\") not in (entry.get(\"eligible_review_ids\" if directory == \"reviews\" else \"eligible_test_ids\") or []):\n            continue\n",
    ),
    "t11-raw-blob-secret-scan": (
        "tools/governance/t11_closure.py",
        "            if any(pattern.search(text) for pattern in cg.SECRET_PATTERNS):\n",
        "            if False:\n",
    ),
    "t11-structural-yaml-loader": (
        "tools/governance/t11_closure.py",
        "Loader=yaml.BaseLoader",
        "Loader=yaml.SafeLoader",
    ),
    "t11-review-thread-poll-schedule": (
        "tools/governance/t11_closure.py",
        "    if not has_poll_schedule:\n",
        "    if False:\n",
    ),
    "t11-poller-stale-success-only": (
        "tools/governance/thread_state_poll.py",
        'run.get("conclusion") != "success"',
        'run.get("conclusion") == "success"',
    ),
    "t11-core-gate-wiring": (
        ".github/workflows/_governance-core.yml",
        "          python -m tools.governance.t11_closure . \\\n",
        "          python -m tools.governance.t10_closure . \\\n",
    ),
    "t11-empty-external-import-finalization": (
        "tools/governance/t11_closure.py",
        "            if not raw_import:\n",
        "            if not raw_import and ext:\n",
    ),
    "t11-single-logical-command-proof": (
        "tools/governance/t11_closure.py",
        "        if commands == [list(expected)]:\n            return True\n",
        "        if any(tuple(command) == expected for command in commands):\n            return True\n",
    ),
    "t11-dependency-producer-order": (
        "tools/governance/t11_closure.py",
        "            after_index=probe_index,\n",
        "            after_index=None,\n",
    ),
    "t11-trusted-predecessor-prefix": (
        "tools/governance/t11_closure.py",
        "    return all(checks)\n",
        "    return True\n",
    ),
    "t11-job-container-execution-context": (
        "tools/governance/t11_closure.py",
        '    if "container" in job:\n        return False\n',
        '    if False:\n        return False\n',
    ),
    "t11-job-runner-execution-context": (
        "tools/governance/t11_closure.py",
        '    if runner is not None and runner != TRUSTED_RUNNER:\n        return False\n',
        '    if False:\n        return False\n',
    ),
    "t11-job-service-execution-context": (
        "tools/governance/t11_closure.py",
        '    if "services" in job:\n        return False\n',
        '    if False:\n        return False\n',
    ),
}


def main() -> int:
    originals: dict[str, str] = {}
    killed = 0
    for name, (target, needle, replacement) in MUTATIONS.items():
        original = originals.setdefault(target, (ROOT / target).read_text(encoding="utf-8"))
        if original.count(needle) != 1:
            print(f"T11 MUTATION ERROR {name}: target occurrence count != 1", file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix="monde-t11-mutation-") as temp_dir:
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
                print(f"T11 MUTATION SURVIVED {name}", file=sys.stderr)
                continue
            print(f"T11 MUTATION KILLED {name}")
            killed += 1
    print(f"MONDE T11 mutation smoke: {killed}/{len(MUTATIONS)} critical mutations killed")
    return 0 if killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
