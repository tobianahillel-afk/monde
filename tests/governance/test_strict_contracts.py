from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools.governance.strict_contracts import (
    executable_manifests,
    iter_test_ids,
    load_mapping,
    load_records,
    main,
    review_targets,
    run,
    validate_action_surfaces,
    validate_progress_uniqueness,
    validate_work_lifecycle,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def dump(path: Path, value: object) -> None:
    write(path, yaml.safe_dump(value, sort_keys=False))


def work(wid: str, status: str = "IN_PROGRESS", deps: list[str] | None = None) -> dict:
    return {
        "id": wid,
        "status": status,
        "depends_on": deps or [],
        "review_plan": {"completed_reviews": []},
        "required_tests": {},
    }


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


def issue_rules(items: list) -> set[str]:
    return {item.rule for item in items}


def test_load_mapping_records_and_iterators(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = repo(tmp_path)
    assert load_records(root, "tests") == {}
    assert load_mapping(root / "missing.yaml") == {}
    write(root / "bad.yaml", "[not: yaml")
    assert load_mapping(root / "bad.yaml") == {}
    write(root / "list.yaml", "- x\n")
    assert load_mapping(root / "list.yaml") == {}
    dump(root / "registry/tests/_TEMPLATE.yaml", {"id": "TEST-9999"})
    dump(root / "registry/tests/one.yaml", {"id": "TEST-0001", "status": "PASS"})
    dump(root / "registry/tests/no-id.yaml", {"status": "PASS"})
    assert set(load_records(root, "tests")) == {"TEST-0001"}
    assert list(iter_test_ids("see TEST-0001 and TEST-0002")) == ["TEST-0001", "TEST-0002"]
    assert list(iter_test_ids({"x": ["TEST-0003", 4]})) == ["TEST-0003"]
    assert list(iter_test_ids(42)) == []

    target = root / "boom.yaml"
    write(target, "x: 1\n")
    original = Path.read_text

    def fail(self: Path, *args: object, **kwargs: object) -> str:
        if self == target:
            raise OSError("boom")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail)
    assert load_mapping(target) == {}


def test_review_targets_structured_scope_and_artifact() -> None:
    assert review_targets({}) == set()
    assert review_targets({"scope": {"work_items": ["WORK-0001", 4]}, "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-0002"}}) == {"WORK-0001", "WORK-0002"}
    assert review_targets({"scope": [], "artifact": {"type": "PULL_REQUEST", "id_or_path": "PR-2"}}) == set()
    assert review_targets({"artifact": {"type": "WORK_ITEM", "id_or_path": 4}}) == set()


def test_dependency_state_contract(tmp_path: Path) -> None:
    root = repo(tmp_path)
    dump(root / "registry/work-items/WORK-0001.yaml", work("WORK-0001", "PLANNED"))
    dump(root / "registry/work-items/WORK-0002.yaml", work("WORK-0002", "IN_PROGRESS", ["WORK-0001", "WORK-9999"]))
    assert issue_rules(validate_work_lifecycle(root)) == {"WORK_DEP_STATE"}

    dump(root / "registry/work-items/WORK-0001.yaml", work("WORK-0001", "IN_REVIEW"))
    assert validate_work_lifecycle(root) == []

    dump(root / "registry/work-items/WORK-0002.yaml", work("WORK-0002", "DONE", ["WORK-0001"]))
    assert issue_rules(validate_work_lifecycle(root)) == {"WORK_DEP_STATE"}

    dump(root / "registry/work-items/WORK-0001.yaml", work("WORK-0001", "DONE"))
    assert validate_work_lifecycle(root) == []


def test_done_review_binding_and_test_evidence(tmp_path: Path) -> None:
    root = repo(tmp_path)
    current = work("WORK-0002", "DONE")
    current["review_plan"] = {"completed_reviews": ["REVIEW-0001", "REVIEW-4040"]}
    current["required_tests"] = {"unit": ["TEST-0001", "TEST-0002", "TEST-4040"], "notes": "also TEST-0001"}
    dump(root / "registry/work-items/WORK-0002.yaml", current)
    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "scope": {"work_items": ["WORK-9999"]}})
    dump(root / "registry/tests/TEST-0001.yaml", {"id": "TEST-0001", "status": "PASS"})
    dump(root / "registry/tests/TEST-0002.yaml", {"id": "TEST-0002", "status": "FAIL"})
    assert issue_rules(validate_work_lifecycle(root)) == {"DONE_REVIEW_SCOPE", "DONE_TEST_EVIDENCE"}

    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "scope": {"work_items": ["WORK-0002"]}})
    current["review_plan"] = {"completed_reviews": ["REVIEW-0001"]}
    current["required_tests"] = {"unit": ["TEST-0001"]}
    dump(root / "registry/work-items/WORK-0002.yaml", current)
    assert validate_work_lifecycle(root) == []

    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-0002"}})
    assert validate_work_lifecycle(root) == []


def test_progress_duplicate_detection(tmp_path: Path) -> None:
    root = repo(tmp_path)
    matrix = {
        "phases": {
            "P1": {"lots": {"L1": {"sublots": {"S1": {"work_items": {"WORK-0001": {"status": "PLANNED"}}}}}}},
            "P2": {"lots": {"L2": {"sublots": {"S2": {"work_items": {"WORK-0001": {"status": "PLANNED"}, "WORK-0002": {"status": "PLANNED"}}}}}}},
        }
    }
    dump(root / "registry/progress/matrix.yaml", matrix)
    issues = validate_progress_uniqueness(root)
    assert len(issues) == 1
    assert issues[0].rule == "PROGRESS_DUPLICATE"
    dump(root / "registry/progress/matrix.yaml", {"phases": {}})
    assert validate_progress_uniqueness(root) == []


def test_action_surfaces_cover_yaml_and_local_manifests(tmp_path: Path) -> None:
    root = repo(tmp_path)
    assert executable_manifests(root) == []
    good_sha = "a" * 40
    good_digest = "b" * 64
    write(root / ".github/workflows/good.yml", f"jobs:\n  x:\n    steps:\n      - uses: owner/action@{good_sha}\n      - uses: docker://alpine@sha256:{good_digest}\n")
    write(root / ".github/workflows/bad.yaml", "jobs:\n  x:\n    steps:\n      - uses: owner/action@v1\n      - uses: ./missing\n")
    write(root / ".github/actions/outer/action.yml", "runs:\n  using: composite\n  steps:\n    - uses: owner/nested@v2\n    - uses: ./local-no-manifest\n")
    (root / "local-no-manifest").mkdir()
    write(root / ".github/actions/valid/action.yaml", f"runs:\n  using: composite\n  steps:\n    - uses: owner/inner@{good_sha}\n")
    issues = validate_action_surfaces(root)
    assert issue_rules(issues) == {"ACTION_PIN", "ACTION_LOCAL"}
    assert len(executable_manifests(root)) == 4

    write(root / ".github/workflows/bad.yaml", "jobs:\n  x:\n    uses: ./.github/workflows/good.yml\n")
    write(root / ".github/actions/outer/action.yml", f"runs:\n  using: composite\n  steps:\n    - uses: owner/nested@{good_sha}\n    - uses: ./.github/actions/valid\n")
    assert validate_action_surfaces(root) == []


def test_action_surface_malformed_manifest_is_safe(tmp_path: Path) -> None:
    root = repo(tmp_path)
    write(root / ".github/workflows/x.yml", "[not: yaml")
    assert validate_action_surfaces(root) == []


def test_run_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = repo(tmp_path)
    dump(root / "registry/work-items/WORK-0001.yaml", work("WORK-0001"))
    dump(root / "registry/progress/matrix.yaml", {"phases": {}})
    assert run(root) == []
    output = tmp_path / "strict.json"
    assert main([str(root), "--json-out", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == []
    assert "0 error(s)" in capsys.readouterr().out

    dump(root / "registry/progress/matrix.yaml", {"phases": {"P": {"lots": {"L": {"sublots": {"S1": {"work_items": {"WORK-0001": {}}}, "S2": {"work_items": {"WORK-0001": {}}}}}}}}})
    assert main([str(root)]) == 1
    captured = capsys.readouterr()
    assert "PROGRESS_DUPLICATE" in captured.err
