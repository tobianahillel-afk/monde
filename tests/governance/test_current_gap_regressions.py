from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from tools.governance import change_guard as cg
from tools.governance import context_manifest as cm
from tools.governance.strict_contracts import (
    WORK_PROGRESS_DIMENSIONS,
    validate_progress_uniqueness,
    validate_work_lifecycle,
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "test")


def test_work_schema_rejects_unknown_review_independence_target() -> None:
    schema = json.loads(Path("schemas/registry/work-items.schema.json").read_text(encoding="utf-8"))
    bad = {
        "id": "WORK-1",
        "status": "PROPOSED",
        "review_plan": {"required_hats": [], "independence_level": "SELF", "completed_reviews": []},
    }
    good = {
        "id": "WORK-1",
        "status": "PROPOSED",
        "review_plan": {"required_hats": [], "independence_level": "L2_TARGET", "completed_reviews": []},
    }
    assert list(Draft202012Validator(schema).iter_errors(bad))
    assert list(Draft202012Validator(schema).iter_errors(good)) == []


def test_done_progress_requires_complete_canonical_dimensions(tmp_path: Path) -> None:
    matrix = {
        "phases": {
            "P": {
                "lots": {
                    "L": {
                        "sublots": {
                            "S": {
                                "work_items": {
                                    "WORK-1": {"status": "DONE"},
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    dump(tmp_path / "registry/progress/matrix.yaml", matrix)
    rules = {issue.rule for issue in validate_progress_uniqueness(tmp_path)}
    assert "PROGRESS_DONE_DIMENSION" in rules

    state = {"status": "DONE", **{key: "DONE" for key in WORK_PROGRESS_DIMENSIONS}}
    state["tests"] = "PASS"
    matrix["phases"]["P"]["lots"]["L"]["sublots"]["S"]["work_items"]["WORK-1"] = state
    dump(tmp_path / "registry/progress/matrix.yaml", matrix)
    rules = {issue.rule for issue in validate_progress_uniqueness(tmp_path)}
    assert "PROGRESS_DIMENSION_STATUS" in rules

    state["tests"] = "DONE"
    dump(tmp_path / "registry/progress/matrix.yaml", matrix)
    assert validate_progress_uniqueness(tmp_path) == []


def test_done_requires_specification_completion_gate(tmp_path: Path) -> None:
    work = {
        "id": "WORK-1",
        "status": "DONE",
        "depends_on": [],
        "review_plan": {"completed_reviews": []},
        "required_tests": {},
        "completion": {"specification_gates_checked": False},
    }
    dump(tmp_path / "registry/work-items/WORK-1.yaml", work)
    rules = {issue.rule for issue in validate_work_lifecycle(tmp_path)}
    assert "DONE_COMPLETION" in rules


def test_review_severity_is_canonical_and_blocks_r1_r2(tmp_path: Path) -> None:
    work = {
        "id": "WORK-1",
        "status": "DONE",
        "depends_on": [],
        "review_plan": {"completed_reviews": ["REVIEW-1"]},
        "required_tests": {},
        "completion": {"specification_gates_checked": True},
    }
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-1"},
        "findings": [{"id": "F-1", "severity": "R1_CRITICAL", "disposition": "OPEN"}],
    }
    dump(tmp_path / "registry/work-items/WORK-1.yaml", work)
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    rules = {issue.rule for issue in validate_work_lifecycle(tmp_path)}
    assert "DONE_REVIEW_FINDING" in rules

    review["findings"][0]["severity"] = "SEVERE"
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    rules = {issue.rule for issue in validate_work_lifecycle(tmp_path)}
    assert "DONE_REVIEW_SEVERITY" in rules


def test_context_manifest_traverses_planned_downstream_work_and_tests(tmp_path: Path) -> None:
    init_git(tmp_path)
    for name in ("README.md", "AGENTS.md", "PROJECT_STATE.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/00_START_HERE.md").write_text("x", encoding="utf-8")
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared/contract.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/downstream.py").write_text("# test", encoding="utf-8")

    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "IN_PROGRESS",
            "read_before": ["README.md"],
            "affected_paths": ["shared/"],
            "assurance": {"level": "A3"},
        },
    )
    dump(
        tmp_path / "registry/work-items/WORK-2.yaml",
        {
            "id": "WORK-2",
            "status": "PLANNED",
            "depends_on": ["WORK-1"],
            "required_tests": {"integration": ["TEST-2"]},
            "read_before": [],
        },
    )
    dump(
        tmp_path / "registry/tests/TEST-2.yaml",
        {
            "id": "TEST-2",
            "status": "PASS",
            "location": {"test_path": "tests/downstream.py"},
        },
    )
    base = commit(tmp_path, "base")
    (tmp_path / "shared/contract.json").write_text('{"v": 2}', encoding="utf-8")
    head = commit(tmp_path, "change shared contract")

    manifest = cm.build(tmp_path, base, head)
    should = set(manifest["context"]["should_read"])
    assert "WORK-2" in manifest["impacted_work"]
    assert "registry/work-items/WORK-2.yaml" in should
    assert "registry/tests/TEST-2.yaml" in should
    assert "tests/downstream.py" in should


def test_review_freshness_ignores_unrelated_work_but_catches_owned_path(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / cg.GUARD_PATH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / cg.GUARD_PATH).write_text("guard", encoding="utf-8")
    (tmp_path / "component-a").mkdir()
    (tmp_path / "component-b").mkdir()
    (tmp_path / "component-a/a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "component-b/b.txt").write_text("b", encoding="utf-8")
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "IN_REVIEW",
            "purpose": "a",
            "scope": {"in": ["a"], "out": []},
            "acceptance_criteria": [{"id": "AC", "description": "a", "status": "DONE"}],
            "assurance": {"level": "A3"},
            "affected_paths": ["component-a/"],
            "review_plan": {"completed_reviews": []},
        },
    )
    reviewed = commit(tmp_path, "review point")
    dump(
        tmp_path / "registry/reviews/REVIEW-1.yaml",
        {"id": "REVIEW-1", "status": "COMPLETE", "artifact": {"commit_sha": reviewed}},
    )
    work = yaml.safe_load((tmp_path / "registry/work-items/WORK-1.yaml").read_text(encoding="utf-8"))
    work["review_plan"]["completed_reviews"] = ["REVIEW-1"]
    dump(tmp_path / "registry/work-items/WORK-1.yaml", work)
    admin = commit(tmp_path, "record review")

    (tmp_path / "component-b/b.txt").write_text("changed", encoding="utf-8")
    unrelated = commit(tmp_path, "unrelated work")
    assert "REVIEW_FRESHNESS" not in {f.rule for f in cg.validate(tmp_path, admin, unrelated)}

    (tmp_path / "component-a/a.txt").write_text("changed", encoding="utf-8")
    owned = commit(tmp_path, "owned change")
    assert "REVIEW_FRESHNESS" in {f.rule for f in cg.validate(tmp_path, unrelated, owned)}


def test_strict_defensive_gap_branches(tmp_path: Path) -> None:
    from tools.governance.strict_contracts import validate_review_findings

    review = {
        "findings": [
            "not-a-map",
            {"id": "F-low", "severity": "R3_MODERATE", "disposition": "OPEN"},
            {"id": "F-resolved", "severity": "R2_MAJOR", "disposition": "RESOLVED"},
        ]
    }
    assert validate_review_findings("work.yaml", "REVIEW-1", review) == []

    complete = {key: "DONE" for key in WORK_PROGRESS_DIMENSIONS}
    complete["tests"] = "PARTIAL"
    complete["typo_dimension"] = "DONE"
    matrix = {
        "phases": {
            "P": {
                "lots": {
                    "L": {
                        "sublots": {
                            "S": {
                                "work_items": {
                                    "WORK-bad-shape": "DONE",
                                    "WORK-incomplete": {"status": "DONE", **complete},
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    dump(tmp_path / "registry/progress/matrix.yaml", matrix)
    rules = {issue.rule for issue in validate_progress_uniqueness(tmp_path)}
    assert {"PROGRESS_SHAPE", "PROGRESS_DIMENSION_KEY", "PROGRESS_DONE_DIMENSION"} <= rules


def test_context_helper_and_bad_metadata_branches(tmp_path: Path) -> None:
    assert list(cm.iter_strings([])) == []
    assert cm.record_refs({"id": 7, "values": []}) == set()
    assert cm.record_index(tmp_path) == {}

    dump(tmp_path / "registry/_TEMPLATE.yaml", {"id": "WORK-999"})
    dump(tmp_path / "registry/bad-id.yaml", {"id": 7})
    assert cm.record_index(tmp_path) == {}

    assert cm.declared_paths({"read_before": "README.md", "implementation_plan": "bad"}) == []
    paths = cm.declared_paths(
        {
            "implementation_plan": {
                "tasks": [
                    "bad-task",
                    {"expected_files": ["owned/file.txt", 7]},
                    {"expected_files": "not-a-list"},
                ]
            }
        }
    )
    assert paths == ["owned/file.txt"]


def test_context_build_handles_noncanonical_metadata_without_crashing(tmp_path: Path) -> None:
    init_git(tmp_path)
    for name in ("README.md", "AGENTS.md", "PROJECT_STATE.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/00_START_HERE.md").write_text("x", encoding="utf-8")
    (tmp_path / "note.txt").write_text("a", encoding="utf-8")

    dump(
        tmp_path / "registry/work-items/WORK-bad.yaml",
        {"id": 7, "status": "IN_PROGRESS", "read_before": [], "assurance": {"level": "A1"}},
    )
    dump(
        tmp_path / "registry/work-items/WORK-2.yaml",
        {
            "id": "WORK-2",
            "status": "IN_PROGRESS",
            "read_before": [],
            "required_tests": {"unit": ["TEST-2", "TEST-3"]},
            "assurance": {"level": "A2"},
        },
    )
    dump(tmp_path / "registry/tests/TEST-2.yaml", {"id": "TEST-2", "status": "PASS", "location": "bad"})
    dump(tmp_path / "registry/tests/TEST-3.yaml", {"id": "TEST-3", "status": "PASS", "location": {"test_path": 7}})
    base = commit(tmp_path, "base")
    (tmp_path / "note.txt").write_text("b", encoding="utf-8")
    head = commit(tmp_path, "text change")

    manifest = cm.build(tmp_path, base, head)
    assert "WORK-2" in manifest["active_work"]
    assert "note.txt" not in manifest["context"]["should_read"]


def test_change_guard_scope_helpers_and_registry_reference(tmp_path: Path) -> None:
    assert list(cg.iter_strings([])) == []
    assert cg.work_scope_paths({"read_before": "bad", "implementation_plan": "bad"}) == []
    assert cg.work_scope_paths(
        {
            "implementation_plan": {
                "tasks": [
                    "bad-task",
                    {"expected_files": ["component/x.txt", 7]},
                    {"expected_files": "bad"},
                ]
            }
        }
    ) == ["component/x.txt"]
    assert cg.work_referenced_ids({"id": 7, "requirements": ["REQ-1"]}) == {"REQ-1"}

    init_git(tmp_path)
    dump(tmp_path / "registry/requirements/REQ-1.yaml", {"id": "REQ-1", "status": "ACCEPTED"})
    dump(tmp_path / "registry/requirements/REQ-2.yaml", {"id": 7, "status": "ACCEPTED"})
    reviewed = commit(tmp_path, "requirements")
    dump(tmp_path / "registry/requirements/REQ-1.yaml", {"id": "REQ-1", "status": "SUPERSEDED"})
    head = commit(tmp_path, "change requirement")

    assert cg.registry_id_for_change(tmp_path, reviewed, head, "registry/requirements/REQ-1.yaml") == "REQ-1"
    assert cg.registry_id_for_change(tmp_path, reviewed, head, "registry/requirements/REQ-2.yaml") is None
    work = {"id": "WORK-1", "requirements": ["REQ-1"]}
    assert cg.change_relevant_to_work(
        tmp_path,
        "registry/work-items/WORK-1.yaml",
        work,
        reviewed,
        head,
        "registry/requirements/REQ-1.yaml",
    )


def test_strict_redundant_defensive_scope_and_docker_branches(tmp_path: Path) -> None:
    from tools.governance.strict_contracts import review_targets, validate_action_surfaces

    assert review_targets({"scope": ["not-a-map"]}) == set()
    workflow = tmp_path / ".github/workflows/docker.yaml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("jobs:\n  x:\n    steps:\n      - uses: docker://alpine:latest\n", encoding="utf-8")
    assert "ACTION_PIN" in {issue.rule for issue in validate_action_surfaces(tmp_path)}
