from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import yaml

from tools.governance import change_guard as cg
from tools.governance.validate_repo import GLOBAL_STATUSES, Issue, Record, Validator, main as validate_main


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def write(root: Path, path: str, data) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, dict):
        target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        target.write_text(data, encoding="utf-8")


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "coverage@example.test")
    git(root, "config", "user.name", "coverage")


def minimal_work(*, assurance: str = "A3", status: str = "IN_PROGRESS", affected_paths=None) -> dict:
    return {
        "id": "WORK-1",
        "status": status,
        "purpose": "coverage",
        "scope": {"in": ["coverage"], "out": []},
        "acceptance_criteria": [{"id": "AC-1", "description": "x", "status": "IN_REVIEW"}],
        "assurance": {"level": assurance},
        "affected_paths": affected_paths or [],
        "review_plan": {"required_hats": [], "completed_reviews": []},
    }


def test_change_guard_helper_branches() -> None:
    assert cg.review_plan_contract("not-a-map") == "not-a-map"
    assert cg.semantic_projection({"purpose": "x"}) == {"purpose": "x"}
    assert cg.path_is_declared("x.txt", [42, "x.txt"])
    assert not cg.path_is_declared("x.txt", [42, "other.txt"])
    assert cg.path_is_declared("x/y.txt", ["x/"])
    assert not cg.path_is_declared("x/y.txt", ["other/"])


def test_meta_qualifier_skip_branches(tmp_path: Path) -> None:
    init_git(tmp_path)
    write(tmp_path, cg.GUARD_PATH, "guard")
    write(tmp_path, "registry/work-items/WORK-1.yaml", minimal_work(affected_paths=[".github/"]))
    base = commit(tmp_path, "base")

    # WORK-1 is substantively present in the changed-file set and authorizes the meta path.
    # WORK-2/3/4 exercise terminal, low-assurance and malformed-work skip paths.
    authorizer = minimal_work(affected_paths=[".github/"])
    authorizer["updated_at"] = "2026-09-10"
    write(tmp_path, "registry/work-items/WORK-1.yaml", authorizer)
    write(tmp_path, "registry/work-items/WORK-2.yaml", {"id": "WORK-2", "status": "DONE", "assurance": {"level": "A4"}, "affected_paths": [".github/"]})
    write(tmp_path, "registry/work-items/WORK-3.yaml", {"id": "WORK-3", "status": "IN_PROGRESS", "assurance": {"level": "A1"}, "affected_paths": [".github/"]})
    write(tmp_path, "registry/work-items/WORK-4.yaml", "not: [valid")
    write(tmp_path, ".github/workflows/x.yml", "name: x\n")
    head = commit(tmp_path, "meta")
    findings = cg.validate(tmp_path, base, head)
    assert "META_GOVERNANCE" not in {f.rule for f in findings}


def test_change_guard_cli_prints_finding_without_json(tmp_path: Path, capsys) -> None:
    init_git(tmp_path)
    write(tmp_path, cg.GUARD_PATH, "guard")
    write(tmp_path, "registry/work-items/WORK-1.yaml", minimal_work())
    base = commit(tmp_path, "base")
    work = minimal_work()
    work["id"] = "WORK-2"
    write(tmp_path, "registry/work-items/WORK-1.yaml", work)
    head = commit(tmp_path, "bad id")
    assert cg.main([str(tmp_path), "--base", base, "--head", head]) == 1
    captured = capsys.readouterr()
    assert "ID_IMMUTABLE" in captured.err
    assert "MONDE change guard" in captured.out


def test_review_finding_nonblocking_and_nonmapping_branches(tmp_path: Path) -> None:
    validator = Validator(tmp_path)
    work = Record("work-items", tmp_path / "work.yaml", {
        "id": "WORK-1",
        "review_plan": {
            "required_hats": ["SECURITY"],
            "independence_level": "L2_TARGET",
            "completed_reviews": ["REVIEW-1"],
        },
    })
    review = Record("reviews", tmp_path / "review.yaml", {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "roles": ["SECURITY"],
        "reviewer": {"independence_level": "L2"},
        "findings": ["nondict", {"id": "F-low", "severity": "R4_LOW", "disposition": "OPEN"}],
    })
    validator.by_id = {"REVIEW-1": review}
    validator.validate_review_evidence(work)
    assert validator.issues == []


def test_task_known_dependency_and_future_due_branches(tmp_path: Path) -> None:
    validator = Validator(tmp_path, today=date(2026, 9, 10))
    work = Record("work-items", tmp_path / "work.yaml", {
        "implementation_plan": {
            "tasks": [{"id": "T1", "depends_on": []}, {"id": "T2", "depends_on": ["T1"]}],
            "planned_runs": [{"id": "RUN", "tasks": ["T1", "T2"]}],
        }
    })
    validator.validate_work_tasks(work)
    validator.check_due(work, "2026-09-11", "DUE")
    assert validator.issues == []


def test_progress_status_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "registry/progress/matrix.yaml"
    path.parent.mkdir(parents=True)
    work = Record("work-items", tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "IN_PROGRESS"})
    path.write_text(yaml.safe_dump({
        "status_vocabulary": sorted(GLOBAL_STATUSES),
        "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-1": {"status": "PLANNED"}}}}}}}},
    }), encoding="utf-8")
    validator = Validator(tmp_path)
    validator.records = [work]
    validator.by_id = {"WORK-1": work}
    validator.validate_progress()
    assert [issue.rule for issue in validator.issues] == ["PROGRESS_STATUS"]


def test_validate_cli_prints_error_without_json(tmp_path: Path, capsys) -> None:
    assert validate_main([str(tmp_path), "--today", "2026-09-10"]) == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "error(s)" in captured.out


def test_validate_cli_warning_branch(tmp_path: Path, capsys, monkeypatch) -> None:
    def fake_run(self):
        self.records = []
        return [Issue("x", "WARN", "message", severity="WARNING")]

    monkeypatch.setattr(Validator, "run", fake_run)
    assert validate_main([str(tmp_path), "--today", "2026-09-10"]) == 0
    captured = capsys.readouterr()
    assert "WARNING WARN" in captured.out
    assert captured.err == ""
