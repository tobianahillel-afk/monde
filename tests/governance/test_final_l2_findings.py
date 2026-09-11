from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from tools.governance import context_manifest as cm
from tools.governance.strict_contracts import (
    WORK_PROGRESS_DIMENSIONS,
    validate_progress_uniqueness,
    validate_work_lifecycle,
)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "final-l2@example.invalid")
    git(root, "config", "user.name", "final-l2")


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def schema(name: str) -> dict:
    return json.loads(Path(f"schemas/registry/{name}.schema.json").read_text(encoding="utf-8"))


def test_assurance_level_sets_minimum_review_independence() -> None:
    work_schema = schema("work-items")
    a3_l1 = {
        "id": "WORK-1",
        "status": "PROPOSED",
        "assurance": {"level": "A3", "rationale": "critical"},
        "review_plan": {"required_hats": [], "independence_level": "L1", "completed_reviews": []},
    }
    a3_l2 = {
        **a3_l1,
        "review_plan": {"required_hats": [], "independence_level": "L2_TARGET", "completed_reviews": []},
    }
    a4_l2 = {
        **a3_l1,
        "assurance": {"level": "A4", "rationale": "constitutional"},
        "review_plan": {"required_hats": [], "independence_level": "L2", "completed_reviews": []},
    }
    a4_l3 = {
        **a4_l2,
        "review_plan": {"required_hats": [], "independence_level": "L3_TARGET", "completed_reviews": []},
    }
    validator = Draft202012Validator(work_schema)
    assert list(validator.iter_errors(a3_l1))
    assert list(validator.iter_errors(a3_l2)) == []
    assert list(validator.iter_errors(a4_l2))
    assert list(validator.iter_errors(a4_l3)) == []


def test_strict_contract_rejects_assurance_downgrade(tmp_path: Path) -> None:
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "IN_REVIEW",
            "depends_on": [],
            "assurance": {"level": "A3"},
            "review_plan": {"independence_level": "L1", "completed_reviews": []},
        },
    )
    assert "REVIEW_ASSURANCE_INDEPENDENCE" in {x.rule for x in validate_work_lifecycle(tmp_path)}
    work = yaml.safe_load((tmp_path / "registry/work-items/WORK-1.yaml").read_text(encoding="utf-8"))
    work["review_plan"]["independence_level"] = "L2"
    dump(tmp_path / "registry/work-items/WORK-1.yaml", work)
    assert "REVIEW_ASSURANCE_INDEPENDENCE" not in {x.rule for x in validate_work_lifecycle(tmp_path)}


def test_complete_review_requires_commit_sha_in_schema_and_done_gate(tmp_path: Path) -> None:
    review_schema = schema("reviews")
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-1"},
    }
    assert list(Draft202012Validator(review_schema).iter_errors(review))
    review["artifact"]["commit_sha"] = "abc123"
    assert list(Draft202012Validator(review_schema).iter_errors(review)) == []

    review["artifact"].pop("commit_sha")
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "DONE",
            "depends_on": [],
            "review_plan": {"completed_reviews": ["REVIEW-1"]},
            "required_tests": {},
            "completion": {"specification_gates_checked": True},
        },
    )
    assert "DONE_REVIEW_SHA" in {x.rule for x in validate_work_lifecycle(tmp_path)}


def test_pass_test_schema_requires_substantive_proof() -> None:
    test_schema = schema("tests")
    validator = Draft202012Validator(test_schema)
    assert list(validator.iter_errors({"id": "TEST-1", "status": "PASS"}))

    execution_backed = {
        "id": "TEST-1",
        "status": "PASS",
        "name": "proof",
        "type": "MANUAL_E2E",
        "protects": {"contracts": ["contract"]},
        "cases": {"happy_path": ["works"]},
        "execution": {
            "command_or_workflow": "manual",
            "result": "PASS",
            "evidence": ["evidence"],
        },
    }
    assert list(validator.iter_errors(execution_backed)) == []

    no_contract = {**execution_backed, "protects": {"contracts": []}}
    assert list(validator.iter_errors(no_contract))

    definition_backed = {
        "id": "TEST-2",
        "status": "PASS",
        "name": "ci proof",
        "type": "UNIT",
        "protects": {"contracts": ["contract"]},
        "cases": {"failure_modes": ["fails closed"]},
        "execution_definition": {"command": "pytest"},
        "execution_evidence_policy": {
            "source_of_truth": "GITHUB_CHECKS_AND_ARTIFACTS",
            "rule": "execution is SHA-bound",
        },
    }
    assert list(validator.iter_errors(definition_backed)) == []


def test_not_applicable_progress_requires_work_justification(tmp_path: Path) -> None:
    state = {"status": "DONE", **{key: "DONE" for key in WORK_PROGRESS_DIMENSIONS}}
    state["scientific_validation"] = "NOT_APPLICABLE"
    matrix = {
        "phases": {
            "P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-1": state}}}}}}
        }
    }
    dump(tmp_path / "registry/progress/matrix.yaml", matrix)
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE"})
    assert "PROGRESS_NA_JUSTIFICATION" in {x.rule for x in validate_progress_uniqueness(tmp_path)}

    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "DONE",
            "progress_justifications": {"scientific_validation": "No scientific/model claim exists."},
        },
    )
    assert "PROGRESS_NA_JUSTIFICATION" not in {x.rule for x in validate_progress_uniqueness(tmp_path)}


def test_changed_registry_record_seeds_context_dependency_closure(tmp_path: Path) -> None:
    init_git(tmp_path)
    for name in ("README.md", "AGENTS.md", "PROJECT_STATE.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/00_START_HERE.md").write_text("x", encoding="utf-8")

    dump(
        tmp_path / "registry/requirements/REQ-1.yaml",
        {"id": "REQ-1", "status": "ACCEPTED", "statement": "v1"},
    )
    dump(
        tmp_path / "registry/work-items/WORK-2.yaml",
        {
            "id": "WORK-2",
            "status": "PLANNED",
            "requirements": ["REQ-1"],
            "read_before": [],
        },
    )
    base = commit(tmp_path, "base")
    dump(
        tmp_path / "registry/requirements/REQ-1.yaml",
        {"id": "REQ-1", "status": "ACCEPTED", "statement": "v2"},
    )
    head = commit(tmp_path, "change requirement")

    manifest = cm.build(tmp_path, base, head)
    assert "REQ-1" in manifest["dependency_records"]
    assert "WORK-2" in manifest["impacted_work"]
    assert "registry/work-items/WORK-2.yaml" in manifest["context"]["should_read"]
