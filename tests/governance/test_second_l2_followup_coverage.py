from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_source_provenance_falls_through_partial_external() -> None:
    review = {
        "external_import": {"source_review_id": "SRC", "source_submitted_at": ""},
        "verification_result": {"source": {"source_id": "RUN", "submitted_at": "now"}, "executor": {"context_id": "ctx"}},
    }
    assert rc.review_source_provenance(review)
    review["verification_result"] = {"source": {}, "executor": "bad"}
    assert not rc.review_source_provenance(review)


def test_requirement_acceptance_skip_branches(monkeypatch, tmp_path: Path) -> None:
    files = ["README.md", "registry/requirements/REQ-1.yaml", "registry/requirements/REQ-2.yaml"]
    records = {
        ("b", "registry/requirements/REQ-1.yaml"): {"status": "PROPOSED"},
        ("h", "registry/requirements/REQ-1.yaml"): {"status": "PROPOSED"},
        ("b", "registry/requirements/REQ-2.yaml"): None,
        ("h", "registry/requirements/REQ-2.yaml"): {"status": "ACCEPTED"},
    }
    monkeypatch.setattr(cg, "changed_files", lambda root, before, after: files)
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get((sha, path)))
    assert rc.validate_requirement_acceptance(tmp_path, [("b", "h")]) == []


def test_historical_exception_shape_and_authorization_branches(monkeypatch, tmp_path: Path) -> None:
    record = {"id": "REQ-1", "status": "ACCEPTED"}
    assert not rc.historical_exception_match({"historical_import_exceptions": ["bad"]}, record, "h")
    assert not rc.historical_exception_match({"historical_import_exceptions": [{"record_id": "OTHER"}]}, record, "h")

    paths = [
        "README.md",
        "registry/progress/matrix.yaml",
        "registry/requirements/REQ-old.yaml",
        "registry/requirements/REQ-empty.yaml",
        "registry/requirements/REQ-initial.yaml",
        "registry/requirements/REQ-external.yaml",
        "registry/requirements/REQ-good.yaml",
    ]
    current = {
        "REQ-initial.yaml": {"id": "REQ-I", "status": "PROPOSED"},
        "REQ-external.yaml": {"id": "REQ-E", "status": "ACCEPTED", "external_import": {}},
        "REQ-good.yaml": {"id": "REQ-G", "status": "ACCEPTED"},
    }
    previous = {"REQ-old.yaml": {"id": "REQ-O", "status": "PROPOSED"}}
    good = {"historical_import_exceptions": [{
        "record_id": "REQ-G", "imported_status": "ACCEPTED", "import_commit": "h",
        "historical_only": True, "future_reuse_forbidden": True, "review_origin": "REVIEW-1/F-1",
    }]}
    monkeypatch.setattr(cg, "file_exists_at", lambda *args: True)
    monkeypatch.setattr(cg, "changed_files", lambda *args: paths)
    monkeypatch.setattr(cg, "registry_kind", lambda p: None if p == "README.md" else ("progress" if "progress/" in p else "requirements"))
    def show(root, sha, path):
        name = Path(path).name
        if sha == "b":
            return previous.get(name)
        return current.get(name)
    monkeypatch.setattr(cg, "show_yaml", show)
    monkeypatch.setattr(cg, "canonical_machine_spec", lambda root, sha, kind: {"initial": "PROPOSED", **(good if sha == "b" else {})})
    assert rc.validate_historical_import_authorization(tmp_path, [("b", "h")]) == []


def test_flatten_progress_malformed_shapes_and_descendant_branches() -> None:
    data = {
        "phases": {
            "BAD": "x",
            "P": {
                "status": 3,
                "lots": {
                    "BAD": "x",
                    "L": {
                        "status": 4,
                        "sublots": {
                            "BAD": "x",
                            "S": {"status": 5, "work_items": {"WORK-1": "bad", 3: {"status": "DONE"}, "WORK-2": {"status": 7}}},
                        },
                    },
                },
            },
        },
        "quality_dimensions": {"security": 3},
    }
    assert rc.flatten_progress(data) == {"work:3": "DONE"}
    assert rc.descendant_works(data, "progress:phase:MISSING") == set()
    nested = {"phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {3: {}, "WORK-X": {}}, "lots": {"bad": "x"}}}}}}}}
    assert rc.descendant_works(nested, "progress:sublot:P/L/S") == {"WORK-X"}


def test_reopening_evidence_negative_scope_and_progress_skip(monkeypatch, tmp_path: Path) -> None:
    matrix = {"phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-1": {"status": "IN_REVIEW"}}}}}}}}}
    records = {
        "registry/reviews/R.yaml": {"status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": "bad"},
        "registry/work-items/WORK-1.yaml": {"id": "WORK-1", "scope_change": "bad"},
    }
    monkeypatch.setattr(cg, "changed_files", lambda *args: ["registry/reviews/R.yaml", "registry/work-items/WORK-1.yaml"])
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    assert not rc.reopening_evidence_valid(tmp_path, "b", "h", "work:WORK-1", matrix)

    monkeypatch.setattr(cg, "changed_files", lambda *args: ["README.md"])
    assert rc.validate_progress_reopening(tmp_path, [("b", "h")]) == []


def test_done_review_substance_skip_branches(tmp_path: Path) -> None:
    dump(tmp_path / "registry/work-items/WORK-X.yaml", {"id": "WORK-X", "status": "IN_REVIEW"})
    dump(tmp_path / "registry/work-items/WORK-A.yaml", {
        "id": "WORK-A", "status": "DONE", "assurance": {"level": "A1"},
        "review_plan": {"independence_level": "L0", "completed_reviews": ["REVIEW-A"]},
    })
    dump(tmp_path / "registry/work-items/WORK-B.yaml", {
        "id": "WORK-B", "status": "DONE", "assurance": {"level": "A3"},
        "review_plan": {"independence_level": "L2_TARGET", "completed_reviews": ["REVIEW-B", "REVIEW-C"]},
    })
    dump(tmp_path / "registry/reviews/REVIEW-B.yaml", {"status": "OPEN", "reviewer": {"independence_level": "L2"}})
    dump(tmp_path / "registry/reviews/REVIEW-C.yaml", {"status": "COMPLETE", "reviewer": {"independence_level": "L1"}})
    assert rc.validate_done_review_substance(tmp_path) == []


def test_main_success_failure_and_runtime_error(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(rc, "run", lambda root, base, head: [])
    out = tmp_path / "out.json"
    assert rc.main([str(tmp_path), "--base", "b", "--head", "h", "--json-out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == "[]"
    assert "0 error(s)" in capsys.readouterr().out

    monkeypatch.setattr(rc, "run", lambda root, base, head: [rc.Finding("p", "RULE", "problem")])
    assert rc.main([str(tmp_path), "--base", "b", "--head", "h"]) == 1
    captured = capsys.readouterr()
    assert "ERROR RULE p: problem" in captured.err
    assert "1 error(s)" in captured.out

    def boom(root, base, head):
        raise RuntimeError("git exploded")
    monkeypatch.setattr(rc, "run", boom)
    assert rc.main([str(tmp_path), "--base", "b", "--head", "h"]) == 2
    assert "ERROR REVIEW_CLOSURE git exploded" in capsys.readouterr().err
