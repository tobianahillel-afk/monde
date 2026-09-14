from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.t8_closure as t8


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    return root


def write_yaml(root: Path, path: str, value: dict) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def commit_all(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_policy_stability_detects_endpoint_and_change_revert(tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    write_yaml(root, t8.POLICY_PATH, {"version": 1})
    evidence = commit_all(root, "v1")
    assert t8.policy_stable_between(root, evidence, evidence)

    write_yaml(root, t8.POLICY_PATH, {"version": 2})
    changed = commit_all(root, "v2")
    assert not t8.policy_stable_between(root, evidence, changed)

    write_yaml(root, t8.POLICY_PATH, {"version": 1})
    reverted = commit_all(root, "revert")
    assert not t8.policy_stable_between(root, evidence, reverted)
    assert not t8.policy_stable_between(root, "f" * 40, reverted)

    git(root, "checkout", "-b", "side", evidence)
    write_yaml(root, "side.txt", {"x": 1})
    side = commit_all(root, "side")
    git(root, "checkout", "master")
    assert not t8.policy_stable_between(root, side, reverted)


def test_review_and_cold_read_continuous_helpers(monkeypatch, tmp_path: Path) -> None:
    review = {"artifact": {"commit_sha": "a" * 40}}
    test = {"execution": {"commit_sha": "b" * 40}}
    monkeypatch.setattr(t8.t7, "review_qualifies", lambda *args: True)
    monkeypatch.setattr(t8.t7, "cold_read_qualifies", lambda *args: True)
    monkeypatch.setattr(t8, "policy_stable_between", lambda *args: True)
    assert t8.review_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, review)
    assert t8.cold_read_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, test)
    monkeypatch.setattr(t8, "policy_stable_between", lambda *args: False)
    assert not t8.review_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, review)
    assert not t8.cold_read_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, test)
    monkeypatch.setattr(t8.t7, "review_qualifies", lambda *args: False)
    monkeypatch.setattr(t8.t7, "cold_read_qualifies", lambda *args: False)
    assert not t8.review_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, review)
    assert not t8.cold_read_qualifies_continuously(tmp_path, "c" * 40, {"id": "REQ-1"}, "d", 2, test)


def test_requirement_acceptance_invariant(monkeypatch, tmp_path: Path) -> None:
    requirement = {
        "id": "REQ-1",
        "content_identity": {"digest": "d"},
        "verification": {
            "acceptance_evidence": ["bad", "REVIEW-1"],
            "acceptance_cold_read_test_ids": ["bad", "TEST-1"],
        },
    }
    monkeypatch.setattr(t8.cg, "requirement_acceptance_satisfied", lambda *args: False)
    assert not t8.requirement_acceptance_invariant(tmp_path, "a" * 40, requirement)

    monkeypatch.setattr(t8.cg, "requirement_acceptance_satisfied", lambda *args: True)
    monkeypatch.setattr(t8.rc, "requirement_review_floor", lambda *args: (2, "WORK-1"))
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, _s, path: {"id": "REVIEW-1"} if "reviews" in path else {"id": "TEST-1"})
    monkeypatch.setattr(t8, "review_qualifies_continuously", lambda *args: True)
    monkeypatch.setattr(t8, "cold_read_qualifies_continuously", lambda *args: True)
    assert t8.requirement_acceptance_invariant(tmp_path, "a" * 40, requirement)
    monkeypatch.setattr(t8, "review_qualifies_continuously", lambda *args: False)
    assert not t8.requirement_acceptance_invariant(tmp_path, "a" * 40, requirement)
    monkeypatch.setattr(t8, "review_qualifies_continuously", lambda *args: True)
    monkeypatch.setattr(t8, "cold_read_qualifies_continuously", lambda *args: False)
    assert not t8.requirement_acceptance_invariant(tmp_path, "a" * 40, requirement)


def test_continuing_acceptance_revalidates_requirement_and_risk(monkeypatch, tmp_path: Path) -> None:
    paths = ["registry/requirements/REQ-1.yaml", "registry/risks/RISK-1.yaml", "README.md"]
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: paths)
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, _s, path: {"id": path, "status": "ACCEPTED"})
    monkeypatch.setattr(t8, "requirement_acceptance_invariant", lambda *args: False)
    monkeypatch.setattr(t8.cg, "risk_acceptance_satisfied", lambda *args: False)
    findings = t8.validate_continuing_acceptance(tmp_path, [("a", "b")])
    assert {item.rule for item in findings} == {"REQ_ACCEPTED_INVARIANT", "RISK_ACCEPTED_INVARIANT"}
    monkeypatch.setattr(t8, "requirement_acceptance_invariant", lambda *args: True)
    monkeypatch.setattr(t8.cg, "risk_acceptance_satisfied", lambda *args: True)
    assert t8.validate_continuing_acceptance(tmp_path, [("a", "b")]) == []

    def mixed(_r, sha, path):
        if path.endswith("REQ-1.yaml") and sha == "a":
            return {"status": "PROPOSED"}
        return {"status": "ACCEPTED"}
    monkeypatch.setattr(t8.cg, "show_yaml", mixed)
    assert t8.validate_continuing_acceptance(tmp_path, [("a", "b")]) == []


def test_completion_review_projection_and_immutability(monkeypatch, tmp_path: Path) -> None:
    assert t8.completion_review_projection(None) == {}
    base = {
        "status": "COMPLETE", "outcome": "APPROVE", "artifact": {"commit_sha": "a" * 40},
        "reviewer": {"actor": "r"}, "roles": ["SECURITY"], "scope": {"work_items": ["WORK-1"]},
        "findings": [], "checks": {"x": True}, "completed_at": "t",
        "verification_result": {"source": {"source_id": "s"}},
        "external_import": {"source_review_id": "PRR-1", "source_submitted_at": "t", "import_commit": "a" * 40},
    }
    changed = {**base, "checks": {"x": True, "y": True}}
    rebound = {**base, "external_import": {**base["external_import"], "import_commit": "b" * 40}}
    projected = t8.completion_review_projection(base)
    assert projected["checks"] == {"x": True}
    assert "import_commit" not in projected["external_import"]
    assert t8.completion_review_projection({**base, "external_import": "legacy"})["external_import"] == "legacy"

    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: ["registry/reviews/REVIEW-1.yaml", "README.md"])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: base if sha == "a" else changed)
    findings = t8.validate_complete_review_immutability(tmp_path, [("a", "b")])
    assert [item.rule for item in findings] == ["COMPLETE_REVIEW_COMPLETION_IMMUTABLE"]
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: base if sha == "a" else rebound)
    assert t8.validate_complete_review_immutability(tmp_path, [("a", "b")]) == []
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, _s, _p: {"status": "IN_PROGRESS"})
    assert t8.validate_complete_review_immutability(tmp_path, [("a", "b")]) == []


def matrix(work_id: str, status: str) -> dict:
    return {"phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {work_id: {"status": status}}}}}}}}}


def test_matrix_work_statuses_handles_valid_and_nonmapping_entries() -> None:
    data = matrix("WORK-1", "DONE")
    data["phases"]["bad"] = "x"
    data["phases"]["P"]["lots"]["bad"] = "x"
    data["phases"]["P"]["lots"]["L"]["sublots"]["bad"] = "x"
    data["phases"]["P"]["lots"]["L"]["sublots"]["S"]["work_items"]["WORK-X"] = "x"
    data["phases"]["P"]["lots"]["L"]["sublots"]["S"]["work_items"]["WORK-Y"] = {"status": 3}
    assert t8.matrix_work_statuses(data) == {"WORK-1": "DONE"}


def test_target_work_reopening_requires_target_scoped_trigger(monkeypatch, tmp_path: Path) -> None:
    target = "registry/work-items/WORK-1.yaml"
    other = "registry/work-items/WORK-2.yaml"
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: [other])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: {"id": "WORK-2", "review_plan": {"open_findings": [] if sha == "a" else ["F"]}})
    assert not t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")

    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: [target])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: {"id": "WORK-1", "review_plan": {"open_findings": [] if sha == "a" else ["F"]}})
    assert t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")

    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: {"id": "WORK-1", "review_plan": {"open_findings": []}, "scope_change": {} if sha == "a" else {"approved": True, "rationale": "new evidence"}})
    assert t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")

    review = "registry/reviews/REVIEW-1.yaml"
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: [review])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda *_args: {"status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": {"work_items": ["WORK-1"]}})
    assert t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")
    monkeypatch.setattr(t8.cg, "show_yaml", lambda *_args: {"status": "COMPLETE", "outcome": "APPROVE", "scope": {"work_items": ["WORK-1"]}})
    assert not t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")


def test_validate_work_reopenings_rejects_unrelated_trigger(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: matrix("WORK-1", "DONE" if sha == "a" else "IN_REVIEW"))
    monkeypatch.setattr(t8, "target_work_reopening_triggered", lambda *args: False)
    findings = t8.validate_work_reopenings(tmp_path, [("a", "b")])
    assert [item.rule for item in findings] == ["WORK_REOPENING_SCOPE"]
    monkeypatch.setattr(t8, "target_work_reopening_triggered", lambda *args: True)
    assert t8.validate_work_reopenings(tmp_path, [("a", "b")]) == []
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: [])
    assert t8.validate_work_reopenings(tmp_path, [("a", "b")]) == []


def test_run_and_main(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(t8.cg, "pr_commit_edges", lambda *args, **kwargs: ([], [("a", "b")]))
    monkeypatch.setattr(t8, "validate_continuing_acceptance", lambda *args: [t8.Finding("x", "A", "bad")])
    monkeypatch.setattr(t8, "validate_complete_review_immutability", lambda *args: [])
    monkeypatch.setattr(t8, "validate_work_reopenings", lambda *args: [])
    assert len(t8.run(tmp_path, "a", "b")) == 1
    out = tmp_path / "out.json"
    assert t8.main([str(tmp_path), "--base", "a", "--head", "b", "--json-out", str(out)]) == 1
    assert out.exists()
    assert "ERROR A" in capsys.readouterr().err
    monkeypatch.setattr(t8, "validate_continuing_acceptance", lambda *args: [])
    assert t8.main([str(tmp_path), "--base", "a", "--head", "b"]) == 0
