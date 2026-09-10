from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools/governance/validate_repo.py"
MUTATIONS = {
    "review-completion": (
        'if data.get("status") not in {"COMPLETE", "CLOSED"}:',
        'if False:',
    ),
    "progress-reverse-membership": (
        'if wid not in found:',
        'if False:',
    ),
    "action-sha-pinning": (
        'if not PINNED_ACTION.fullmatch(uses):',
        'if False:',
    ),
    "done-progress-dimensions": (
        'if dimension_status not in DONE_PROGRESS_ALLOWED:',
        'if False:',
    ),
}


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    killed = 0
    for name, (needle, replacement) in MUTATIONS.items():
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
            mutated = temp / "tools/governance/validate_repo.py"
            mutated.write_text(original.replace(needle, replacement, 1), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(temp)
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "tests/governance/test_validate_repo.py"],
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
