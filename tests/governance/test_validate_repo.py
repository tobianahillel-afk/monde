from __future__ import annotations

import json
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


def install_schemas(root: Path) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["id", "status"],
        "properties": {"id": {"type": "string"}, "status": {"type": "string"}},
        "additionalProperties": True,
    }
    for kind in ("work-items", "capabilities", "requirements", "assumptions", "risks", "reviews", "tests", "experiments"):
        p = root / "schemas/registry" / f"{kind}.schema.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(schema), encoding="utf-8")


def base_work(wid: str = "WORK-0001", status: str = "IN_PROGRESS") -> dict:
    return {
        "id": wid,
        "status": status,
        "read_before": ["README.md"],
        "affected_docs": [],
        "affected_schemas": [],
        "depends_on": [],
        "acceptance_criteria": [{"id": "AC-1", "description": "x", "status": "DONE" if status == "DONE" else "NOT_STARTED"}],
        "implementation_plan": {"tasks": [{"id": "T1", "depends_on": []}], "planned_runs": [{"id": "RUN-1", "tasks": ["T1"]}]},
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


def matrix_for(work: dict, extra: dict | None = None) -> dict:
    state = {"status": work["status"]}
    if extra:
        state.update(extra)
    return {"status_vocabulary": sorted(GLOBAL_STATUSES), "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {work["id"]: state}}}}}}}}


def make_repo(tmp_path: Path, work: dict | None = None) -> Path:
    root = tmp_path / "repo"
    write(root / "README.md", "# Repo\n")
    install_schemas(root)
    work = work or base_work()
    dump(root / "registry/work-items/WORK-0001.yaml", work)
    dump(root / "registry/progress/matrix.yaml", matrix_for(work))
    write(root / "PROJECT_STATE.md", f"# State\n\n## Active work\n\n- `{work['id']}` active\n")
    return root


def rules(v: Validator) -> set[str]:
    return {x.rule for x in v.run()}


def test_issue_and_clean_repo(tmp_path: Path) -> None:
    assert Issue("a", "R", "m").render() == "ERROR R a: m"
    root = make_repo(tmp_path)
    assert Validator(root, today=date(2026, 9, 10)).run() == []


def test_yaml_record_id_status_and_reference_failures(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    write(root / "registry/capabilities/CAP-1.yaml", "[not: valid: yaml")
    dump(root / "registry/requirements/one.yaml", ["not-a-map"])
    dump(root / "registry/assumptions/no-id.yaml", {"status": "OPEN"})
    dump(root / "registry/risks/bad-prefix.yaml", {"id": "CAP-999", "status": "OPEN"})
    dump(root / "registry/work-items/duplicate.yaml", base_work("WORK-0001"))
    dump(root / "registry/tests/bad-status.yaml", {"id": "TEST-0002", "status": "BOGUS", "protects": ["REQ-4040"]})
    found = rules(Validator(root))
    assert {"YAML_PARSE", "RECORD_SHAPE", "ID_REQUIRED", "ID_PREFIX", "ID_UNIQUE", "STATUS", "REFERENCE"} <= found


def test_schema_missing_parse_and_validation(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    (root / "schemas/registry/work-items.schema.json").unlink()
    assert "SCHEMA_MISSING" in rules(Validator(root))
    install_schemas(root)
    write(root / "schemas/registry/work-items.schema.json", "{")
    assert "SCHEMA_PARSE" in rules(Validator(root))
    install_schemas(root)
    schema_path = root / "schemas/registry/work-items.schema.json"
    schema = json.loads(schema_path.read_text())
    schema["required"].append("purpose")
    schema_path.write_text(json.dumps(schema))
    assert "SCHEMA" in rules(Validator(root))


def test_paths_tasks_runs_dependencies_cycle(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    p = root / "registry/work-items/WORK-0001.yaml"
    one = yaml.safe_load(p.read_text())
    one["read_before"] = "README.md"
    one["affected_docs"] = [42, "missing.md"]
    one["depends_on"] = ["WORK-0002", "WORK-9999"]
    one["implementation_plan"]["tasks"] = [{"id": "T1", "depends_on": ["T404"]}, "bad"]
    one["implementation_plan"]["planned_runs"] = [{"id": "R", "tasks": ["T404"]}, "bad"]
    dump(p, one)
    two = base_work("WORK-0002")
    two["depends_on"] = ["WORK-0001"]
    dump(root / "registry/work-items/WORK-0002.yaml", two)
    found = rules(Validator(root))
    assert {"PATH_LIST", "PATH_TYPE", "PATH_EXISTS", "WORK_DEP_EXISTS", "TASK_DEP", "TASK_SHAPE", "RUN_TASK", "RUN_SHAPE", "WORK_CYCLE"} <= found
    one["depends_on"] = "WORK-0002"
    dump(p, one)
    assert "WORK_DEPS" in rules(Validator(root))


def review(rid: str, *, level: str = "L2", status: str = "COMPLETE", outcome: str = "APPROVED", roles: list[str] | None = None, findings: list[dict] | None = None) -> dict:
    return {"id": rid, "status": status, "outcome": outcome, "roles": roles or ["SECURITY"], "reviewer": {"independence_level": level}, "findings": findings or []}


def test_done_review_semantics(tmp_path: Path) -> None:
    work = base_work(status="DONE")
    work["review_plan"] = {"required_hats": ["SECURITY", "VERIFICATION_VALIDATION"], "independence_level": "L2_TARGET", "completed_reviews": ["REVIEW-0001", "REVIEW-0002"]}
    root = make_repo(tmp_path, work)
    dump(root / "registry/reviews/REVIEW-0001.yaml", review("REVIEW-0001", level="L1", roles=["SECURITY"]))
    dump(root / "registry/reviews/REVIEW-0002.yaml", review("REVIEW-0002", level="L2", roles=["VERIFICATION_VALIDATION"]))
    found = rules(Validator(root))
    assert found == {"ACTIVE_WORK"}

    dump(root / "registry/reviews/REVIEW-0002.yaml", review("REVIEW-0002", level="L1", roles=[], outcome="REJECTED", status="IN_PROGRESS", findings=[{"id": "F", "severity": "R2_MAJOR", "disposition": "OPEN"}]))
    found = rules(Validator(root))
    assert "DONE_REVIEW" in found


def test_done_missing_review_and_completion(tmp_path: Path) -> None:
    work = base_work(status="DONE")
    work["acceptance_criteria"] = []
    work["completion"]["review_complete"] = False
    work["review_plan"] = {"required_hats": ["SECURITY"], "independence_level": "L2_TARGET", "completed_reviews": []}
    root = make_repo(tmp_path, work)
    found = rules(Validator(root))
    assert {"DONE_AC", "DONE_COMPLETION", "DONE_REVIEW", "ACTIVE_WORK"} <= found
    work["acceptance_criteria"] = ["bad"]
    dump(root / "registry/work-items/WORK-0001.yaml", work)
    assert "DONE_AC" in rules(Validator(root))


def test_due_dates(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/assumptions/ASM-0001.yaml", {"id": "ASM-0001", "status": "OPEN", "validation": {"target_date": "2026-09-01"}})
    dump(root / "registry/risks/RISK-0001.yaml", {"id": "RISK-0001", "status": "OPEN", "review_by": "not-a-date"})
    dump(root / "registry/assumptions/ASM-0002.yaml", {"id": "ASM-0002", "status": "CLOSED", "validation": {"target_date": "2020-01-01"}})
    found = rules(Validator(root, today=date(2026, 9, 10)))
    assert {"ASSUMPTION_DUE", "RISK_DUE"} <= found


def test_markdown_titles_placeholder_and_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)
    write(root / "docs/good.md", "Status: Accepted\nCanonical: Yes\n[ok](../README.md \"Guide\") [web](https://example.com)\n")
    write(root / "docs/bad.md", "Status: Accepted\nCanonical: Yes\nTODO later\n[missing](none.md \"Missing\")\n")
    write(root / "docs/unreadable.md", "x")
    original = Path.read_text
    def fake(self: Path, *a: object, **k: object) -> str:
        if self.name == "unreadable.md":
            raise OSError("boom")
        return original(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)
    found = rules(Validator(root))
    assert {"CANONICAL_PLACEHOLDER", "MARKDOWN_LINK", "MARKDOWN_READ"} <= found


def test_progress_reverse_mismatch_and_done_dimensions(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    p = root / "registry/progress/matrix.yaml"
    p.unlink()
    assert "PROGRESS_REQUIRED" in rules(Validator(root))
    write(p, "- bad\n")
    Validator(root).run()
    dump(p, {"status_vocabulary": ["BOGUS"], "phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-9999": {"status": "PLANNED"}}}}}}}}})
    found = rules(Validator(root))
    assert {"STATUS_VOCAB", "PROGRESS_WORK"} <= found

    work = base_work(status="DONE")
    dump(root / "registry/work-items/WORK-0001.yaml", work)
    dump(p, matrix_for(work, {"tests": "PARTIAL", "docs": "DONE"}))
    found = rules(Validator(root))
    assert "PROGRESS_DONE_DIMENSION" in found
    dump(p, matrix_for(work, {"tests": "DONE"}))
    write(root / "PROJECT_STATE.md", "## Active work\nWORK-0001\n")
    assert "ACTIVE_WORK" in rules(Validator(root))


def test_project_state_missing_unknown_and_read_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)
    p = root / "PROJECT_STATE.md"
    p.unlink()
    assert "PROJECT_STATE_REQUIRED" in rules(Validator(root))
    write(p, "# empty\n")
    assert "ACTIVE_WORK" in rules(Validator(root))
    write(p, "## Active work\nWORK-9999\n")
    assert "ACTIVE_WORK" in rules(Validator(root))
    original = Path.read_text
    def fake(self: Path, *a: object, **k: object) -> str:
        if self == p:
            raise OSError("boom")
        return original(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)
    assert "PROJECT_STATE_READ" in rules(Validator(root))


def test_action_pin_and_secret_rules(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    wf = root / ".github/workflows/x.yml"
    write(wf, "jobs:\n  x:\n    steps:\n      - uses: ./local\n      - uses: owner/action@0123456789012345678901234567890123456789\n      - uses: docker://alpine@sha256:" + "a" * 64 + "\n      - uses: owner/action@v1\n      - uses: docker://alpine:latest\n")
    write(root / "leak.txt", "ghp_" + "A" * 30)
    found = rules(Validator(root))
    assert {"ACTION_PIN", "SECRET_PATTERN"} <= found


def test_helpers_and_main_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_repo(tmp_path)
    v = Validator(root)
    v.add("logical/path", "RULE", "m", severity="WARNING")
    v.add(Path("/outside/file"), "X", "y")
    assert list(v.iter_strings(42)) == []
    assert Validator.extract_section("## Active work\nWORK-1\nend", "Active work").strip().startswith("WORK-1")
    assert Validator.extract_section("x", "Missing") == ""
    out = tmp_path / "findings.json"
    assert main([str(root), "--today", "2026-09-10", "--json-out", str(out)]) == 0
    assert json.loads(out.read_text()) == []
    assert "0 error(s)" in capsys.readouterr().out
    assert main([str(root), "--today", "bad"]) == 2


def test_yaml_oserror_template_skip_and_secret_binary_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path)
    dump(root / "registry/tests/_TEMPLATE.yaml", {"id": "TEST-9999", "status": "BOGUS"})
    write(root / "image.png", "ghp_" + "A" * 30)
    path = root / "registry/tests/TEST-0002.yaml"
    write(path, "id: TEST-0002\nstatus: PASS\n")
    v = Validator(root)
    original = Path.read_text
    def fake(self: Path, *a: object, **k: object) -> str:
        if self == path:
            raise OSError("read failed")
        return original(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)
    assert v.load_yaml(path) is None
    assert v.issues[-1].rule == "YAML_PARSE"
