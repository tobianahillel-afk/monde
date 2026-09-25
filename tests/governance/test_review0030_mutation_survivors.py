from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import tools.governance.change_guard as cg
from tools.governance.strict_contracts import validate_work_lifecycle


ROOT = Path(__file__).resolve().parents[2]


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "mutation-survivors@example.invalid")
    git(root, "config", "user.name", "mutation-survivors")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_pass_schema_rejects_short_string_execution_sha() -> None:
    schema = json.loads((ROOT / "schemas/registry/tests.schema.json").read_text(encoding="utf-8"))
    record = {
        "id": "TEST-9999",
        "name": "revision-bound proof",
        "status": "PASS",
        "type": "UNIT",
        "protects": {"contracts": ["revision-bound execution"]},
        "cases": {"happy_path": ["real immutable revision"]},
        "execution": {
            "command_or_workflow": "pytest",
            "commit_sha": "abc123",
            "result": "PASS",
            "evidence": ["run evidence"],
        },
    }
    errors = list(Draft202012Validator(schema).iter_errors(record))
    assert errors
    assert any("does not match" in error.message for error in errors)


def test_done_required_pass_test_rejects_nonexistent_execution_revision(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "DONE",
            "depends_on": [],
            "review_plan": {"completed_reviews": []},
            "required_tests": {"unit": ["TEST-1"]},
            "completion": {"specification_gates_checked": True},
        },
    )
    dump(
        tmp_path / "registry/tests/TEST-1.yaml",
        {
            "id": "TEST-1",
            "status": "PASS",
            "execution": {
                "command_or_workflow": "pytest",
                "commit_sha": "f" * 40,
                "result": "PASS",
                "evidence": ["fabricated revision must fail"],
            },
        },
    )
    commit(tmp_path, "fixture")

    assert "DONE_TEST_EVIDENCE" in {issue.rule for issue in validate_work_lifecycle(tmp_path)}


def test_endpoint_scope_ignores_base_only_registry_addition(tmp_path: Path) -> None:
    init_git(tmp_path)
    guard = tmp_path / cg.GUARD_PATH
    guard.parent.mkdir(parents=True, exist_ok=True)
    guard.write_text("guard already adopted\n", encoding="utf-8")
    merge_base = commit(tmp_path, "merge base")

    git(tmp_path, "checkout", "-b", "feature", merge_base)
    (tmp_path / "feature.txt").write_text("feature contribution\n", encoding="utf-8")
    head = commit(tmp_path, "feature change")

    git(tmp_path, "checkout", "master")
    dump(
        tmp_path / "registry/tests/TEST-BASE-ONLY.yaml",
        {"id": "TEST-BASE-ONLY", "status": "PLANNED"},
    )
    base_tip = commit(tmp_path, "base-only registry addition")

    assert cg.endpoint_changed_files(tmp_path, base_tip, head) == ["feature.txt"]
    assert cg.validate(tmp_path, base_tip, head) == []
