from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from tools.governance import change_guard as cg


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_secret_introduced_in_intermediate_commit_is_detected(tmp_path: Path) -> None:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "coverage@example.test")
    git(tmp_path, "config", "user.name", "coverage")

    work_path = tmp_path / "registry/work-items/WORK-1.yaml"
    work_path.parent.mkdir(parents=True)
    work_path.write_text(
        yaml.safe_dump(
            {
                "id": "WORK-1",
                "status": "IN_PROGRESS",
                "purpose": "secret-history coverage",
                "scope": {"in": ["test"], "out": []},
                "acceptance_criteria": [{"id": "AC-1", "description": "test", "status": "IN_REVIEW"}],
                "assurance": {"level": "A3"},
                "affected_paths": [],
                "review_plan": {"required_hats": [], "completed_reviews": []},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    guard = tmp_path / cg.GUARD_PATH
    guard.parent.mkdir(parents=True)
    guard.write_text("guard", encoding="utf-8")
    base = commit(tmp_path, "base")

    evidence = tmp_path / "evidence.txt"
    evidence.write_text("AKIA" + "A" * 16, encoding="utf-8")
    commit(tmp_path, "introduce synthetic secret")
    evidence.write_text("redacted", encoding="utf-8")
    head = commit(tmp_path, "remove synthetic secret")

    findings = cg.validate(tmp_path, base, head)
    assert "SECRET_HISTORY" in {finding.rule for finding in findings}
