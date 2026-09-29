from __future__ import annotations

from pathlib import Path

import tools.governance.t7_closure as t7


def test_text_and_first_commit_fail_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "git", lambda *args: (_ for _ in ()).throw(RuntimeError("x")))
    assert t7.text_at(tmp_path, "a", "x") is None
    monkeypatch.setattr(t7.cg, "git", lambda *args: "")
    assert t7.first_commit_matching(tmp_path, "h", "x", lambda text: True) is None


def test_predecessor_work_skips_ineligible_records(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "git", lambda *args: "registry/work-items/A.yaml\nregistry/work-items/B.yaml\nregistry/work-items/C.yaml\nregistry/work-items/_TEMPLATE.yaml\n")
    records = {
        "registry/work-items/A.yaml": {"status": "DONE", "assurance": {"level": "A3"}, "affected_paths": ["p"]},
        "registry/work-items/B.yaml": {"status": "IN_REVIEW", "assurance": {"level": "A2"}, "affected_paths": ["p"]},
        "registry/work-items/C.yaml": {"status": "IN_REVIEW", "assurance": {"level": "A3"}, "affected_paths": ["other"]},
    }
    monkeypatch.setattr(t7.cg, "show_yaml", lambda _r, _s, path: records.get(path))
    assert not t7.active_predecessor_work_covers(tmp_path, "s", "p")


def test_policy_guard_missing_adoption_and_pre_adoption_edge(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7, "t7_adoption_sha", lambda *_: None)
    assert t7.validate_policy_trust_anchors(tmp_path, "b", "h")[0].rule == "POLICY_TRUST_ANCHOR_ADOPTION"
    monkeypatch.setattr(t7, "t7_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t7.cg, "pr_commit_edges", lambda *a, **k: ([], [("old", "new")]))
    monkeypatch.setattr(t7.cg, "changed_files", lambda *a: ["registry/status-machines.yaml"])
    monkeypatch.setattr(t7.cg, "is_ancestor", lambda *a: False)
    assert t7.validate_policy_trust_anchors(tmp_path, "b", "h") == []


def test_adoption_boundary_missing_or_duplicate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "show_yaml", lambda *a: {"enforcement_adoptions": []})
    monkeypatch.setattr(t7, "first_commit_matching", lambda *a, **k: None)
    findings = t7.validate_adoption_boundaries(tmp_path, "h")
    assert len(findings) == len(t7.ADOPTION_RULES)
    monkeypatch.setattr(t7, "first_commit_matching", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(t7.cg, "show_yaml", lambda *a: {"enforcement_adoptions": [
        {"rule_id": next(iter(t7.ADOPTION_RULES)), "adoption_commit_sha": "a" * 40, "historical_only": True, "future_reuse_forbidden": True},
        {"rule_id": next(iter(t7.ADOPTION_RULES)), "adoption_commit_sha": "a" * 40, "historical_only": True, "future_reuse_forbidden": True},
    ]})
    assert t7.validate_adoption_boundaries(tmp_path, "h")


def test_requirement_co_satisfaction_requires_same_records(monkeypatch, tmp_path: Path) -> None:
    previous = {"id": "REQ-1", "status": "PROPOSED"}
    current = {
        "id": "REQ-1", "status": "ACCEPTED", "content_identity": {"digest": "d"},
        "verification": {"acceptance_evidence": ["REVIEW-1", "bad"], "acceptance_cold_read_test_ids": ["TEST-1", 1]},
    }
    review = {"id": "REVIEW-1"}
    test = {"id": "TEST-1"}
    monkeypatch.setattr(t7.cg, "pr_commit_edges", lambda *a, **k: ([], [("before", "after")]))
    monkeypatch.setattr(t7.cg, "changed_files", lambda *a: ["README.md", "registry/requirements/REQ-1.yaml"])
    def show(_root, sha, path):
        if path.endswith("REQ-1.yaml"):
            return previous if sha == "before" else current
        if path.endswith("REVIEW-1.yaml"):
            return review
        if path.endswith("TEST-1.yaml"):
            return test
        return {}
    monkeypatch.setattr(t7.cg, "show_yaml", show)
    monkeypatch.setattr(t7.rc, "requirement_review_floor", lambda *a: (3, "WORK-1"))
    monkeypatch.setattr(t7, "review_qualifies", lambda *a: False)
    monkeypatch.setattr(t7, "cold_read_qualifies", lambda *a: False)
    findings = t7.validate_requirement_co_satisfaction(tmp_path, "b", "h")
    assert {item.rule for item in findings} == {"REQ_REVIEW_CO_SATISFACTION", "REQ_COLD_READ_CO_SATISFACTION"}
    monkeypatch.setattr(t7, "review_qualifies", lambda *a: True)
    monkeypatch.setattr(t7, "cold_read_qualifies", lambda *a: True)
    assert t7.validate_requirement_co_satisfaction(tmp_path, "b", "h") == []


def test_requirement_validator_ignores_non_transition(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "pr_commit_edges", lambda *a, **k: ([], [("b", "a")]))
    monkeypatch.setattr(t7.cg, "changed_files", lambda *a: ["registry/requirements/REQ-1.yaml"])
    monkeypatch.setattr(t7.cg, "show_yaml", lambda *_: {"status": "PROPOSED"})
    assert t7.validate_requirement_co_satisfaction(tmp_path, "b", "h") == []


def test_actual_repo_and_owner_fail_closed_branches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "git", lambda *args: (_ for _ in ()).throw(RuntimeError("no remote")))
    assert t7.actual_git_repository(tmp_path) is None
    monkeypatch.setattr(t7, "actual_git_repository", lambda *_: None)
    assert t7.validate_repository_owner_anchor(tmp_path, "h")[0].rule == "REPOSITORY_OWNER_EXTERNAL_ANCHOR"

    monkeypatch.setattr(t7, "actual_git_repository", lambda *_: "acme/world")
    policy = {"governed_repository": {"full_name": "acme/world", "owner_login": "acme", "metadata_url": "https://api.github.com/repos/acme/world", "permission_proof": "TEST-1"}}
    proof = {"id": "TEST-1", "status": "PASS", "execution": {"result": "PASS"}, "environment": {"real_dependencies": "bad"}}
    monkeypatch.setattr(t7.cg, "show_yaml", lambda _r, _s, p: policy if p.endswith("acceptance-authority.yaml") else proof)
    monkeypatch.setattr(t7, "pass_test_execution_revision_valid", lambda *a: True)
    assert t7.validate_repository_owner_anchor(tmp_path, "h")


def test_main_json_and_runtime_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7, "run", lambda *a: [t7.Finding("p", "R", "m")])
    output = tmp_path / "out.json"
    assert t7.main([str(tmp_path), "--base", "b", "--head", "h", "--json-out", str(output)]) == 1
    assert output.exists()
    monkeypatch.setattr(t7, "run", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert t7.main([str(tmp_path), "--base", "b", "--head", "h"]) == 2
