from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.t7_closure as t7


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit_all(root: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=root, check=True, stdout=subprocess.DEVNULL)
    return git(root, "rev-parse", "HEAD")


def init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "remote", "add", "origin", "https://github.com/acme/world.git")
    return root


def write_yaml(root: Path, path: str, value: dict) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_first_commit_matching_and_policy_predecessor_guard(tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    write_yaml(root, "registry/status-machines.yaml", {"version": 1})
    write_yaml(root, "registry/acceptance-authority.yaml", {"version": 1})
    write_yaml(root, "registry/content-identity.yaml", {"version": 1})
    write_yaml(root, "registry/work-items/WORK-1.yaml", {
        "id": "WORK-1", "status": "IN_REVIEW", "assurance": {"level": "A3"}, "affected_paths": []
    })
    base = commit_all(root, "base")

    t7_path = root / t7.T7_PATH
    t7_path.parent.mkdir(parents=True, exist_ok=True)
    t7_path.write_text("def validate_policy_trust_anchors():\n    pass\n", encoding="utf-8")
    adoption = commit_all(root, "adopt t7")
    assert t7.t7_adoption_sha(root, adoption) == adoption

    write_yaml(root, "registry/status-machines.yaml", {"version": 2})
    bad = commit_all(root, "bad policy")
    findings = t7.validate_policy_trust_anchors(root, base, bad)
    assert {item.rule for item in findings} == {"POLICY_PREDECESSOR_AUTHORITY"}

    write_yaml(root, "registry/work-items/WORK-1.yaml", {
        "id": "WORK-1", "status": "IN_REVIEW", "assurance": {"level": "A3"},
        "affected_paths": ["registry/status-machines.yaml"],
    })
    authorized = commit_all(root, "authorize predecessor")
    write_yaml(root, "registry/status-machines.yaml", {"version": 3})
    good = commit_all(root, "good policy")
    assert t7.validate_policy_trust_anchors(root, authorized, good) == []


def test_policy_cannot_change_in_t7_adoption_commit(tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    write_yaml(root, "registry/status-machines.yaml", {"version": 1})
    base = commit_all(root, "base")
    target = root / t7.T7_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def validate_policy_trust_anchors():\n    pass\n", encoding="utf-8")
    write_yaml(root, "registry/status-machines.yaml", {"version": 2})
    head = commit_all(root, "self authorize")
    findings = t7.validate_policy_trust_anchors(root, base, head)
    assert any(item.rule == "POLICY_SELF_AUTHORIZATION" for item in findings)


def test_adoption_boundaries_are_derived_from_git_history(tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    hardening = root / ".github/scripts/governance_l2_hardening.py"
    hardening.parent.mkdir(parents=True, exist_ok=True)
    hardening.write_text("# baseline\n", encoding="utf-8")
    workflow = root / ".github/workflows/_governance-core.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("name: core\n", encoding="utf-8")
    commit_all(root, "base")
    hardening.write_text("def validate_progress_lifecycle():\n    pass\n", encoding="utf-8")
    lifecycle = commit_all(root, "lifecycle")
    workflow.write_text("run: python -m tools.governance.review_closure_gate\n", encoding="utf-8")
    reopening = commit_all(root, "reopening")
    write_yaml(root, "registry/integration-provenance.yaml", {
        "enforcement_adoptions": [
            {"rule_id": "PROGRESS_LIFECYCLE_EDGE_ENFORCEMENT_V1", "adoption_commit_sha": lifecycle,
             "historical_only": True, "future_reuse_forbidden": True},
            {"rule_id": "PROGRESS_REOPENING_EVIDENCE_V1", "adoption_commit_sha": reopening,
             "historical_only": True, "future_reuse_forbidden": True},
        ]
    })
    head = commit_all(root, "markers")
    assert t7.validate_adoption_boundaries(root, head) == []
    data = yaml.safe_load((root / "registry/integration-provenance.yaml").read_text())
    data["enforcement_adoptions"][0]["adoption_commit_sha"] = head
    write_yaml(root, "registry/integration-provenance.yaml", data)
    moved = commit_all(root, "move marker")
    assert any(item.rule == "ADOPTION_HISTORY_BINDING" for item in t7.validate_adoption_boundaries(root, moved))


def test_review_and_cold_read_require_same_evidence_contract(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path
    requirement = {"id": "REQ-1"}
    review = {
        "status": "COMPLETE", "outcome": "APPROVE",
        "reviewer": {"actor": "r", "context_id": "ctx", "independence_level": "L3"},
        "completed_at": "2026-01-01", "roles": ["SECURITY"], "checks": {"x": True},
        "verification_result": {"source": {"source_id": "s", "submitted_at": "t"}, "executor": {"context_id": "e"}},
        "scope": {"requirements": ["REQ-1"], "requirement_revisions": {"REQ-1": {"digest": "d", "status_at_review": "PROPOSED"}}},
        "artifact": {"commit_sha": "a" * 40},
    }
    monkeypatch.setattr(t7.cg, "review_requirement_revision_valid", lambda *args: True)
    monkeypatch.setattr(t7, "policy_blob", lambda _root, sha: "same" if sha else None)
    assert t7.review_qualifies(root, "b" * 40, requirement, "d", 3, review)
    review["scope"]["requirement_revisions"]["REQ-1"]["digest"] = "wrong"
    assert not t7.review_qualifies(root, "b" * 40, requirement, "d", 3, review)

    outcomes = {key: "PASS" for key in t7.REQUIRED_COLD_OUTCOMES}
    test = {
        "id": "TEST-1", "status": "PASS", "protects": {"requirements": ["REQ-1"]},
        "execution": {"result": "PASS", "commit_sha": "c" * 40},
        "acceptance_cold_read": {
            "qualifies": True,
            "requirements": {"REQ-1": {"content_digest": "d", "status_at_read": "PROPOSED"}},
            "source": {"source_id": "s", "submitted_at": "t"},
            "executor": {"context_id": "e", "independence_level": "L3", "fresh_context": True, "authoring_context_separated": True},
            "required_outcomes": outcomes,
            "all_required_outcomes_pass": True,
        },
    }
    monkeypatch.setattr(t7, "pass_test_execution_revision_valid", lambda *args: True)
    monkeypatch.setattr(t7.cg, "show_yaml", lambda _root, sha, path: ({"version": 1} if path.endswith("content-identity.yaml") else {"id": "REQ-1", "status": "PROPOSED"}))
    monkeypatch.setattr(t7, "requirement_normative_digest", lambda *args: "d")
    assert t7.cold_read_qualifies(root, "b" * 40, requirement, "d", 3, test)
    test["acceptance_cold_read"]["executor"]["independence_level"] = "L2"
    assert not t7.cold_read_qualifies(root, "b" * 40, requirement, "d", 3, test)


def test_policy_revision_must_match(monkeypatch, tmp_path: Path) -> None:
    review = {
        "status": "COMPLETE", "outcome": "APPROVE",
        "reviewer": {"actor": "r", "context_id": "ctx", "independence_level": "L3"},
        "completed_at": "t", "roles": ["SECURITY"], "checks": {"x": True},
        "verification_result": {"source": {"source_id": "s", "submitted_at": "t"}, "executor": {"context_id": "e"}},
        "scope": {"requirements": ["REQ-1"], "requirement_revisions": {"REQ-1": {"digest": "d", "status_at_review": "PROPOSED"}}},
        "artifact": {"commit_sha": "a" * 40},
    }
    monkeypatch.setattr(t7.cg, "review_requirement_revision_valid", lambda *args: True)
    monkeypatch.setattr(t7, "policy_blob", lambda _root, sha: "old" if sha == "a" * 40 else "new")
    assert not t7.review_qualifies(tmp_path, "b" * 40, {"id": "REQ-1"}, "d", 3, review)


def test_repository_owner_anchor_uses_actual_remote_and_reachable_proof(monkeypatch, tmp_path: Path) -> None:
    root = init_repo(tmp_path)
    head = "a" * 40
    policy = {"governed_repository": {
        "full_name": "acme/world", "owner_login": "acme",
        "metadata_url": "https://api.github.com/repos/acme/world", "permission_proof": "TEST-7",
    }}
    proof = {
        "id": "TEST-7", "status": "PASS", "execution": {"result": "PASS", "commit_sha": "b" * 40},
        "environment": {"real_dependencies": ["acme/world", "GitHub collaborator permission for repository owner"]},
    }
    monkeypatch.setattr(t7.cg, "show_yaml", lambda _root, _sha, path: policy if path.endswith("acceptance-authority.yaml") else proof)
    monkeypatch.setattr(t7, "pass_test_execution_revision_valid", lambda *args: True)
    assert t7.validate_repository_owner_anchor(root, head) == []
    policy["governed_repository"]["full_name"] = "evil/other"
    assert t7.validate_repository_owner_anchor(root, head)[0].rule == "REPOSITORY_OWNER_EXTERNAL_ANCHOR"


def test_run_and_main_fail_closed(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(t7, "validate_policy_trust_anchors", lambda *args: [t7.Finding("x", "A", "bad")])
    monkeypatch.setattr(t7, "validate_adoption_boundaries", lambda *args: [])
    monkeypatch.setattr(t7, "validate_requirement_co_satisfaction", lambda *args: [])
    monkeypatch.setattr(t7, "validate_repository_owner_anchor", lambda *args: [])
    assert len(t7.run(tmp_path, "a", "b")) == 1
    assert t7.main([str(tmp_path), "--base", "a", "--head", "b"]) == 1
    assert "ERROR A" in capsys.readouterr().err
