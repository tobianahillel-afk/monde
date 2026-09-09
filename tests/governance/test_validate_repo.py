from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from tools.governance.validate_repo import GLOBAL_STATUSES, Issue, Validator, main


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def dump(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def base_work(wid: str = "WORK-0001", status: str = "IN_PROGRESS") -> dict:
    return {
        "id": wid,
        "status": status,
        "read_before": ["README.md"],
        "affected_docs": [],
        "affected_schemas": [],
        "depends_on": [],
        "acceptance_criteria": [{"id": "AC-1", "status": "DONE" if status == "DONE" else "NOT_STARTED"}],
        "implementation_plan": {
            "tasks": [{"id": "T1", "depends_on": []}],
            "planned_runs": [{"id": "RUN-1", "tasks": ["T1"]}],
        },
        "review_plan": {"required_hats": [], "completed_reviews": []},
        "completion": {
            "definition_of_ready_checked": status == "DONE",
            "definition_of_done_checked": status == "DONE",
            "traceability_checked": status == "DONE",
            "review_complete": status == "DONE",
            "docs_updated": status == "DONE",
            "registries_updated": status == "DONE",
            "project_state_updated": status == "DONE",
        },
    }


def make_repo(tmp_path: Path, work: dict | None = None) -> Path:
    root = tmp_path / "repo"
    write(root / "README.md", "# Repo\n")
    work = work or base_work()
    dump(root / "registry/work-items/WORK-0001.yaml", work)
    dump(root / "registry/progress/matrix.yaml", {
        "status_vocabulary": sorted(GLOBAL_STATUSES),
        "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {work["id"]: {"status": work["status"]}}}}}}}},
    })
    write(root / "PROJECT_STATE.md", f"# State\n\n## Active work\n\n- `{work['id']}` active\n\n## Current status\n\n`{work['status']}`\n")
    return root


def rules(validator: Validator) -> set[str]:
    return {issue.rule for issue in validator.run()}


def test_issue_render() -> None:
    assert Issue("a", "R", "m").render() == "ERROR R a: m"


def test_clean_repository_passes(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert Validator(root, today=date(2026, 9, 10)).run() == []


def test_yaml_parse_shape_id_prefix_duplicate_and_status(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write(root / "registry/capabilities/CAP-1.yaml", "[not: valid: yaml")
    dump(root / "registry/requirements/one.yaml", ["not-a-map"])
    dump(root / "registry/assumptions/no-id.yaml", {"status": "OPEN"})
    dump(root / "registry/risks/bad-prefix.yaml", {"id": "CAP-999", "status": "OPEN"})
    dump(root / "registry/work-items/duplicate.yaml", base_work("WORK-0001"))
    dump(root / "registry/tests/bad-status.yaml", {"id": "TEST-0002", "status": "BOGUS"})
    found = rules(Validator(root))
    assert {"YAML_PARSE", "RECORD_SHAPE", "ID_REQUIRED", "ID_PREFIX", "ID_UNIQUE", "STATUS"} <= found


def test_unknown_registry_reference(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/tests/TEST-0002.yaml", {"id": "TEST-0002", "status": "PASS", "protects": {"requirements": ["REQ-4040"]}})
    assert "REFERENCE" in rules(Validator(root))


def test_path_validation(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    work_path = root / "registry/work-items/WORK-0001.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["read_before"] = "README.md"
    work["affected_docs"] = [42, "missing.md"]
    work["affected_schemas"] = None
    dump(work_path, work)
    found = rules(Validator(root))
    assert {"PATH_LIST", "PATH_TYPE", "PATH_EXISTS"} <= found


def test_work_dependency_task_run_and_cycle_validation(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    one = yaml.safe_load((root / "registry/work-items/WORK-0001.yaml").read_text())
    one["depends_on"] = ["WORK-0002", "WORK-9999"]
    one["implementation_plan"]["tasks"] = [{"id": "T1", "depends_on": ["T404"]}, "bad"]
    one["implementation_plan"]["planned_runs"] = [{"id": "R", "tasks": ["T404"]}, "bad"]
    dump(root / "registry/work-items/WORK-0001.yaml", one)
    two = base_work("WORK-0002")
    two["depends_on"] = ["WORK-0001"]
    dump(root / "registry/work-items/WORK-0002.yaml", two)
    found = rules(Validator(root))
    assert {"WORK_DEP_EXISTS", "TASK_DEP", "TASK_SHAPE", "RUN_TASK", "RUN_SHAPE", "WORK_CYCLE"} <= found


def test_work_depends_on_must_be_list(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    work_path = root / "registry/work-items/WORK-0001.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["depends_on"] = "WORK-0002"
    dump(work_path, work)
    assert "WORK_DEPS" in rules(Validator(root))


def test_done_work_requires_criteria_completion_and_review(tmp_path: Path) -> None:
    work = base_work(status="DONE")
    work["acceptance_criteria"] = []
    work["completion"]["review_complete"] = False
    work["review_plan"] = {"required_hats": ["SECURITY"], "completed_reviews": []}
    root = make_repo(tmp_path, work)
    found = rules(Validator(root))
    assert {"DONE_AC", "DONE_COMPLETION", "DONE_REVIEW", "ACTIVE_WORK"} <= found

    work["acceptance_criteria"] = ["bad"]
    dump(root / "registry/work-items/WORK-0001.yaml", work)
    assert "DONE_AC" in rules(Validator(root))


def test_due_dates_and_invalid_dates(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/assumptions/ASM-0001.yaml", {"id": "ASM-0001", "status": "OPEN", "validation": {"target_date": "2026-09-01"}})
    dump(root / "registry/risks/RISK-0001.yaml", {"id": "RISK-0001", "status": "OPEN", "review_by": "not-a-date"})
    dump(root / "registry/assumptions/ASM-0002.yaml", {"id": "ASM-0002", "status": "CLOSED", "validation": {"target_date": "2020-01-01"}})
    found = rules(Validator(root, today=date(2026, 9, 10)))
    assert {"ASSUMPTION_DUE", "RISK_DUE"} <= found


def test_markdown_placeholders_links_and_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)
    write(root / "docs/good.md", "Status: Accepted\nCanonical: Yes\n[ok](../README.md) [web](https://example.com) [mail](mailto:a@b) [anchor](#x)\n")
    write(root / "docs/bad.md", "Status: Accepted\nCanonical: Yes\nTODO later\n[missing](none.md)\n")
    original = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "unreadable.md":
            raise OSError("boom")
        return original(self, *args, **kwargs)

    write(root / "docs/unreadable.md", "x")
    monkeypatch.setattr(Path, "read_text", fake_read_text)
    found = rules(Validator(root))
    assert {"CANONICAL_PLACEHOLDER", "MARKDOWN_LINK", "MARKDOWN_READ"} <= found


def test_progress_missing_invalid_shape_vocab_unknown_and_mismatch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    matrix = root / "registry/progress/matrix.yaml"
    matrix.unlink()
    assert "PROGRESS_REQUIRED" in rules(Validator(root))

    write(matrix, "- bad\n")
    Validator(root).run()

    dump(matrix, {"status_vocabulary": ["BOGUS"], "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-0001": {"status": "DONE"}, "WORK-9999": {"status": "PLANNED"}}}}}}}}})
    found = rules(Validator(root))
    assert {"STATUS_VOCAB", "PROGRESS_STATUS", "PROGRESS_WORK"} <= found


def test_project_state_missing_empty_unknown_and_terminal(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    state = root / "PROJECT_STATE.md"
    state.unlink()
    assert "PROJECT_STATE_REQUIRED" in rules(Validator(root))

    write(state, "# x\n")
    assert "ACTIVE_WORK" in rules(Validator(root))

    write(state, "## Active work\nWORK-9999\n")
    assert "ACTIVE_WORK" in rules(Validator(root))

    work_path = root / "registry/work-items/WORK-0001.yaml"
    work = yaml.safe_load(work_path.read_text())
    work["status"] = "CANCELLED"
    dump(work_path, work)
    dump(root / "registry/progress/matrix.yaml", {"status_vocabulary": sorted(GLOBAL_STATUSES), "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-0001": {"status": "CANCELLED"}}}}}}}}})
    write(state, "## Active work\nWORK-0001\n")
    assert "ACTIVE_WORK" in rules(Validator(root))


def test_extract_section_without_next_heading() -> None:
    text = "## Active work\nWORK-0001\nend"
    assert "WORK-0001" in Validator.extract_section(text, "Active work")
    assert Validator.extract_section(text, "Missing") == ""


def test_add_external_path_and_yaml_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)
    validator = Validator(root)
    validator.add(Path("/outside/file"), "X", "y")
    assert validator.issues[0].path == "/outside/file"
    path = root / "registry/tests/TEST-0002.yaml"
    write(path, "id: TEST-0002\nstatus: PASS\n")
    original = Path.open

    def fake_open(self: Path, *args: object, **kwargs: object):
        if self == path:
            raise OSError("read failed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    assert validator.load_yaml(path) is None
    assert validator.issues[-1].rule == "YAML_PARSE"


def test_main_success_errors_and_bad_date(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_repo(tmp_path)
    assert main([str(root), "--today", "2026-09-10"]) == 0
    assert "0 error(s)" in capsys.readouterr().out

    write(root / "PROJECT_STATE.md", "# broken\n")
    assert main([str(root)]) == 1
    captured = capsys.readouterr()
    assert "ACTIVE_WORK" in captured.err

    assert main([str(root), "--today", "bad"]) == 2
    assert "--today must be ISO" in capsys.readouterr().err


def test_template_files_are_skipped_and_iter_strings_ignores_scalars(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/tests/_TEMPLATE.yaml", {"id": "TEST-9999", "status": "BOGUS"})
    validator = Validator(root)
    assert list(validator.iter_strings(42)) == []
    assert validator.run() == []


def test_valid_task_dependencies_review_and_future_dates(tmp_path: Path) -> None:
    work = base_work()
    work["implementation_plan"]["tasks"] = [
        {"id": "T1", "depends_on": []},
        {"id": "T2", "depends_on": ["T1"]},
    ]
    work["implementation_plan"]["planned_runs"] = [{"id": "RUN-1", "tasks": ["T1", "T2"]}]
    root = make_repo(tmp_path, work)
    dump(root / "registry/assumptions/ASM-0001.yaml", {"id": "ASM-0001", "status": "OPEN", "validation": {"target_date": None}})
    dump(root / "registry/risks/RISK-0001.yaml", {"id": "RISK-0001", "status": "OPEN", "review_by": "2027-01-01"})
    assert Validator(root, today=date(2026, 9, 10)).run() == []


def test_done_work_with_completed_review_is_valid_except_active_state(tmp_path: Path) -> None:
    work = base_work(status="DONE")
    work["review_plan"] = {"required_hats": ["SECURITY"], "completed_reviews": ["REVIEW-0001"]}
    root = make_repo(tmp_path, work)
    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "status": "COMPLETE"})
    found = rules(Validator(root))
    assert found == {"ACTIVE_WORK"}


def test_git_markdown_is_skipped(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write(root / ".git" / "bad.md", "Status: Accepted\nCanonical: Yes\nTODO\n")
    assert "CANONICAL_PLACEHOLDER" not in rules(Validator(root))


def test_progress_non_mapping_work_state(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/progress/matrix.yaml", {
        "status_vocabulary": sorted(GLOBAL_STATUSES),
        "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-0001": "bad"}}}}}}},
    })
    assert "PROGRESS_STATUS" in rules(Validator(root))


def test_add_string_path_branch(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    validator = Validator(root)
    validator.add("logical/path", "RULE", "message", severity="WARNING")
    assert validator.issues[-1] == Issue("logical/path", "RULE", "message", "WARNING")
