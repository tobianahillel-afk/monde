from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.t9_closure as t9


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


def test_policy_full_history_detects_side_branch_change_hidden_by_merge(tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    write_yaml(root, t9.POLICY_PATH, {"version": 1})
    evidence = commit_all(root, "base")
    git(root, "checkout", "-b", "side")
    write_yaml(root, t9.POLICY_PATH, {"version": 2})
    commit_all(root, "policy side change")
    git(root, "checkout", "master")
    (root / "main.txt").write_text("main\n", encoding="utf-8")
    commit_all(root, "main")
    git(root, "merge", "--no-ff", "side", "-m", "merge side")
    write_yaml(root, t9.POLICY_PATH, {"version": 1})
    acceptance = commit_all(root, "restore endpoint bytes")
    assert not t9.policy_stable_full_history(root, evidence, acceptance)
    assert not t9.policy_stable_full_history(root, "f" * 40, acceptance)


def test_review_and_test_import_finalization_helpers(monkeypatch, tmp_path: Path) -> None:
    review = {"id": "REVIEW-1"}
    test = {"id": "TEST-1"}
    assert t9.review_import_finalized(tmp_path, review, "h", "registry/reviews/REVIEW-1.yaml")
    assert t9.test_import_finalized(tmp_path, test, "h", "registry/tests/TEST-1.yaml")
    assert not t9.review_import_finalized(tmp_path, {"external_import": "bad"}, "h", "p")
    assert not t9.test_import_finalized(tmp_path, {"external_import": "bad"}, "h", "p")

    r = {"id": "REVIEW-1", "status": "COMPLETE", "outcome": "APPROVE", "artifact": {"commit_sha": "a" * 40}, "reviewer": {"context_id": "ctx"}, "external_import": {"mode": "PREAUTHORIZED_EXTERNAL_COMPLETION", "import_commit": "b" * 40, "authorization_commit": "a" * 40, "source_review_id": "PRR", "source_submitted_at": "t"}}
    monkeypatch.setattr(t9.cg, "commit_exists", lambda *_: True)
    monkeypatch.setattr(t9, "_first_status_commit", lambda *_: "b" * 40)
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    before = {"registry_machines": {"reviews": {"external_import_authorizations": [{"record_id": "REVIEW-1", "imported_status": "COMPLETE", "artifact_commit_sha": "a" * 40, "source_review_id": "PRR", "source_submitted_at": "t", "reviewer_context_id": "ctx", "expected_outcome": "APPROVE", "one_shot": True, "consumed_by_commit": None}]}}}
    after = {"registry_machines": {"reviews": {"external_import_authorizations": [{**before["registry_machines"]["reviews"]["external_import_authorizations"][0], "consumed_by_commit": "b" * 40}]}}}
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _root, sha, _path: before if sha == "a" * 40 else after)
    assert t9.review_import_finalized(tmp_path, r, "h", "p")
    r["external_import"]["import_commit"] = "c" * 40
    assert not t9.review_import_finalized(tmp_path, r, "h", "p")


def test_requirement_acceptance_requires_full_history_and_finalized_imports(monkeypatch, tmp_path: Path) -> None:
    requirement = {"id": "REQ-1", "status": "ACCEPTED", "content_identity": {"digest": "d"}, "verification": {"acceptance_evidence": ["REVIEW-1"], "acceptance_cold_read_test_ids": ["TEST-1"]}}
    monkeypatch.setattr(t9.cg, "requirement_acceptance_satisfied", lambda *_: True)
    monkeypatch.setattr(t9.rc, "requirement_review_floor", lambda *_: (2, "WORK-1"))
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, _s, path: {"id": "REVIEW-1"} if "reviews" in path else {"id": "TEST-1"})
    monkeypatch.setattr(t9, "review_qualifies", lambda *_: True)
    monkeypatch.setattr(t9, "cold_read_qualifies", lambda *_: True)
    assert t9.requirement_acceptance_invariant(tmp_path, "h", requirement)
    monkeypatch.setattr(t9, "review_qualifies", lambda *_: False)
    assert not t9.requirement_acceptance_invariant(tmp_path, "h", requirement)
    monkeypatch.setattr(t9.cg, "requirement_acceptance_satisfied", lambda *_: False)
    assert not t9.requirement_acceptance_invariant(tmp_path, "h", requirement)


def test_review_and_cold_qualifiers_require_policy_and_import(monkeypatch, tmp_path: Path) -> None:
    review = {"id": "REVIEW-1", "artifact": {"commit_sha": "a" * 40}}
    test = {"id": "TEST-1", "execution": {"commit_sha": "b" * 40}}
    monkeypatch.setattr(t9.t7, "review_qualifies", lambda *_: True)
    monkeypatch.setattr(t9.t7, "cold_read_qualifies", lambda *_: True)
    monkeypatch.setattr(t9, "policy_stable_full_history", lambda *_: True)
    monkeypatch.setattr(t9, "review_import_finalized", lambda *_: True)
    monkeypatch.setattr(t9, "test_import_finalized", lambda *_: True)
    assert t9.review_qualifies(tmp_path, "h", {"id": "REQ-1"}, "d", 2, review)
    assert t9.cold_read_qualifies(tmp_path, "h", {"id": "REQ-1"}, "d", 2, test)
    monkeypatch.setattr(t9, "review_import_finalized", lambda *_: False)
    assert not t9.review_qualifies(tmp_path, "h", {"id": "REQ-1"}, "d", 2, review)
    monkeypatch.setattr(t9, "test_import_finalized", lambda *_: False)
    assert not t9.cold_read_qualifies(tmp_path, "h", {"id": "REQ-1"}, "d", 2, test)


def test_validate_requirement_acceptance(monkeypatch, tmp_path: Path) -> None:
    path = "registry/requirements/REQ-1.yaml"
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [path, "README.md"])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, _s, p: {"id": "REQ-1", "status": "ACCEPTED"} if p == path else {})
    monkeypatch.setattr(t9, "requirement_acceptance_invariant", lambda *_: False)
    assert [x.rule for x in t9.validate_requirement_acceptance(tmp_path, [("a", "b")])] == ["REQ_ACCEPTANCE_T9"]
    monkeypatch.setattr(t9, "requirement_acceptance_invariant", lambda *_: True)
    assert t9.validate_requirement_acceptance(tmp_path, [("a", "b")]) == []


def test_import_commit_only_allows_single_finalization(monkeypatch, tmp_path: Path) -> None:
    path = "registry/reviews/REVIEW-1.yaml"
    base = {"status": "COMPLETE", "external_import": {"import_commit": None}}
    final = {"status": "COMPLETE", "external_import": {"import_commit": "a" * 40}}
    rebound = {"status": "COMPLETE", "external_import": {"import_commit": "b" * 40}}
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [path])
    monkeypatch.setattr(t9, "review_import_finalized", lambda *_: True)
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: base if sha == "x" else final)
    assert t9.validate_import_commit_immutability(tmp_path, [("x", "y")]) == []
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: final if sha == "x" else rebound)
    assert [x.rule for x in t9.validate_import_commit_immutability(tmp_path, [("x", "y")])] == ["REVIEW_IMPORT_COMMIT_IMMUTABLE"]
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, _s, _p: {"status": "IN_PROGRESS"})
    assert t9.validate_import_commit_immutability(tmp_path, [("x", "y")]) == []


def test_base_preexisting_policy_authority_and_adoption(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: ["registry/content-identity.yaml"])
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9, "base_preexisting_work_covers", lambda *_: False)
    assert [x.rule for x in t9.validate_base_preexisting_policy_authority(tmp_path, "base", "head")] == ["POLICY_BASE_AUTHORITY"]
    monkeypatch.setattr(t9, "base_preexisting_work_covers", lambda *_: True)
    assert t9.validate_base_preexisting_policy_authority(tmp_path, "base", "head") == []
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: None)
    assert t9.validate_base_preexisting_policy_authority(tmp_path, "base", "head")[0].rule == "T9_ADOPTION"


def test_new_reopening_trigger_requires_added_identity(monkeypatch, tmp_path: Path) -> None:
    work = "registry/work-items/WORK-1.yaml"
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [work])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"review_plan": {"open_findings": ["A", "B"] if sha == "before" else ["B", "A"]}, "scope_change": {"approved": True, "rationale": "old"}})
    assert not t9.new_reopening_trigger(tmp_path, "before", "after", "WORK-1")
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"review_plan": {"open_findings": ["A"] if sha == "before" else ["A", "C"]}, "scope_change": {}})
    assert t9.new_reopening_trigger(tmp_path, "before", "after", "WORK-1")
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"review_plan": {"open_findings": []}, "scope_change": {"approved": False} if sha == "before" else {"approved": True, "rationale": "new"}})
    assert t9.new_reopening_trigger(tmp_path, "before", "after", "WORK-1")


def test_validate_new_reopening_triggers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-1": {"status": "DONE" if sha == "pre" else "IN_REVIEW"}}}}}}}}})
    monkeypatch.setattr(t9, "new_reopening_trigger", lambda *_: False)
    assert [x.rule for x in t9.validate_new_reopening_triggers(tmp_path, "base", "head")] == ["WORK_REOPENING_NEW_TRIGGER"]
    monkeypatch.setattr(t9, "new_reopening_trigger", lambda *_: True)
    assert t9.validate_new_reopening_triggers(tmp_path, "base", "head") == []


def test_run_and_main(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("a", "b")]))
    monkeypatch.setattr(t9, "validate_requirement_acceptance", lambda *_: [t9.Finding("x", "A", "bad")])
    monkeypatch.setattr(t9, "validate_import_commit_immutability", lambda *_: [])
    monkeypatch.setattr(t9, "validate_base_preexisting_policy_authority", lambda *_: [])
    monkeypatch.setattr(t9, "validate_new_reopening_triggers", lambda *_: [])
    assert len(t9.run(tmp_path, "a", "b")) == 1
    out = tmp_path / "out.json"
    assert t9.main([str(tmp_path), "--base", "a", "--head", "b", "--json-out", str(out)]) == 1
    assert out.exists()
    assert "ERROR A" in capsys.readouterr().err
    monkeypatch.setattr(t9, "validate_requirement_acceptance", lambda *_: [])
    assert t9.main([str(tmp_path), "--base", "a", "--head", "b"]) == 0
