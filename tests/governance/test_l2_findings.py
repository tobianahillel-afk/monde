from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from tools.governance.change_guard import validate as validate_changes
from tools.governance.validate_repo import Record, Validator


def write(root: Path, path: str, data) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, dict):
        target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        target.write_text(data, encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def init_repo(tmp_path: Path, *, affected_paths=None) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "x@example.test")
    git(root, "config", "user.name", "x")
    work = {
        "id": "WORK-1",
        "status": "IN_PROGRESS",
        "purpose": "governance",
        "scope": {"in": ["governance"], "out": []},
        "acceptance_criteria": [{"id": "AC-1", "description": "x", "status": "IN_REVIEW"}],
        "assurance": {"level": "A3"},
        "affected_paths": affected_paths or [],
        "review_plan": {
            "independence_level": "L2_TARGET",
            "required_hats": ["SECURITY"],
            "completed_reviews": [],
        },
    }
    write(root, "registry/work-items/WORK-1.yaml", work)
    write(root, "tools/governance/change_guard.py", "guard")
    write(root, "README.md", "# test\n")
    return root, commit(root, "base")


def review_record(level: str, outcome: str = "APPROVE") -> Record:
    return Record(
        "reviews",
        Path("review.yaml"),
        {
            "id": "REVIEW-1",
            "status": "COMPLETE",
            "outcome": outcome,
            "roles": ["SECURITY"],
            "reviewer": {"independence_level": level},
            "findings": [],
        },
    )


def work_record(target: str) -> Record:
    return Record(
        "work-items",
        Path("work.yaml"),
        {
            "id": "WORK-1",
            "review_plan": {
                "required_hats": ["SECURITY"],
                "independence_level": target,
                "completed_reviews": ["REVIEW-1"],
            },
        },
    )


def test_l3_target_requires_l3_review(tmp_path: Path) -> None:
    validator = Validator(tmp_path)
    validator.by_id = {"REVIEW-1": review_record("L2")}
    validator.validate_review_evidence(work_record("L3_TARGET"))
    assert [issue.rule for issue in validator.issues] == ["DONE_REVIEW"]
    assert "L3_TARGET" in validator.issues[0].message

    validator = Validator(tmp_path)
    validator.by_id = {"REVIEW-1": review_record("L3")}
    validator.validate_review_evidence(work_record("L3_TARGET"))
    assert validator.issues == []


def test_canonical_review_outcomes_are_accepted(tmp_path: Path) -> None:
    for outcome in ("APPROVE", "APPROVE_WITH_FOLLOWUP"):
        validator = Validator(tmp_path)
        validator.by_id = {"REVIEW-1": review_record("L2", outcome)}
        validator.validate_review_evidence(work_record("L2_TARGET"))
        assert validator.issues == []


def test_review_requirements_are_substantive_but_completion_list_is_admin(tmp_path: Path) -> None:
    root, base = init_repo(tmp_path)
    work_path = root / "registry/work-items/WORK-1.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["status"] = "IN_REVIEW"
    write(root, "registry/work-items/WORK-1.yaml", work)
    reviewed = commit(root, "review point")
    write(root, "registry/reviews/REVIEW-1.yaml", {
        "id": "REVIEW-1", "status": "COMPLETE", "outcome": "APPROVE",
        "roles": ["SECURITY"], "reviewer": {"independence_level": "L2"},
        "artifact": {"commit_sha": reviewed}, "findings": [],
    })
    work["review_plan"]["completed_reviews"] = ["REVIEW-1"]
    write(root, "registry/work-items/WORK-1.yaml", work)
    admin_head = commit(root, "record review")
    assert not [x for x in validate_changes(root, reviewed, admin_head) if x.rule == "REVIEW_FRESHNESS"]

    work["review_plan"]["required_hats"] = []
    work["scope_change"] = {"approved": True, "rationale": "test semantic review weakening"}
    write(root, "registry/work-items/WORK-1.yaml", work)
    weakened = commit(root, "weaken review requirement")
    assert "REVIEW_FRESHNESS" in {x.rule for x in validate_changes(root, admin_head, weakened)}


def test_commit_sequence_union_catches_reverted_invalid_transition(tmp_path: Path) -> None:
    root, base = init_repo(tmp_path)
    work_path = root / "registry/work-items/WORK-1.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["status"] = "CANCELLED"
    work["scope_change"] = {"approved": True, "rationale": "test"}
    write(root, "registry/work-items/WORK-1.yaml", work)
    commit(root, "invalid intermediate transition")
    work["status"] = "IN_PROGRESS"
    work.pop("scope_change", None)
    write(root, "registry/work-items/WORK-1.yaml", work)
    head = commit(root, "restore endpoint")
    assert "registry/work-items/WORK-1.yaml" not in git(root, "diff", "--name-only", f"{base}..{head}").splitlines()
    assert "STATE_TRANSITION" in {x.rule for x in validate_changes(root, base, head)}


def test_meta_governance_requires_active_bound_work(tmp_path: Path) -> None:
    root, base = init_repo(tmp_path, affected_paths=["tools/governance/"])
    write(root, ".github/workflows/x.yml", "name: x\n")
    work_path = root / "registry/work-items/WORK-1.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["updated_at"] = "2026-09-10"
    write(root, "registry/work-items/WORK-1.yaml", work)
    head = commit(root, "unbound meta change")
    assert "META_GOVERNANCE" in {x.rule for x in validate_changes(root, base, head)}

    base = head
    work["affected_paths"] = [".github/", "tools/governance/"]
    work["scope_change"] = {"approved": True, "rationale": "bind workflow path"}
    write(root, "registry/work-items/WORK-1.yaml", work)
    write(root, ".github/workflows/y.yml", "name: y\n")
    head = commit(root, "bound meta change")
    assert "META_GOVERNANCE" not in {x.rule for x in validate_changes(root, base, head)}


def test_secret_added_then_removed_is_detected_in_history(tmp_path: Path) -> None:
    root, base = init_repo(tmp_path)
    token = "ghp_" + ("A" * 30)
    write(root, "temporary.txt", token + "\n")
    commit(root, "accidentally add secret")
    (root / "temporary.txt").unlink()
    head = commit(root, "remove secret")
    findings = validate_changes(root, base, head)
    assert "SECRET_HISTORY" in {x.rule for x in findings}
