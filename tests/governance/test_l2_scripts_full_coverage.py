from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = ROOT / ".github/scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h = load("governance_l2_hardening", "governance_l2_hardening.py")
f = load("governance_l2_followup", "governance_l2_followup.py")
g = load("governance_l2_gate", "governance_l2_gate.py")

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def test_hardening_low_level_git_and_history_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for stderr, expected in [("boom", "boom"), ("", "git command failed")]:
        monkeypatch.setattr(h.subprocess, "run", lambda *a, stderr=stderr, **k: SimpleNamespace(returncode=1, stderr=stderr, stdout=""))
        with pytest.raises(RuntimeError, match=expected):
            h.git(tmp_path, "status")

    monkeypatch.setattr(h, "commit_parents", lambda *a: [])
    with pytest.raises(RuntimeError, match="has no parent"):
        h.comparison_parent(tmp_path, SHA_A, SHA_B)

    monkeypatch.setattr(h, "commit_parents", lambda *a: [SHA_A, SHA_C])
    assert h.comparison_parent(tmp_path, SHA_A, SHA_B) == SHA_A
    monkeypatch.setattr(h, "commit_parents", lambda *a: [SHA_C, SHA_B])
    monkeypatch.setattr(h, "is_ancestor", lambda root, base, parent: parent == SHA_B)
    assert h.comparison_parent(tmp_path, SHA_A, SHA_C) == SHA_B
    monkeypatch.setattr(h, "is_ancestor", lambda *a: False)
    assert h.comparison_parent(tmp_path, SHA_A, SHA_C) == SHA_C

    def fake_git(_root: Path, *args: str) -> str:
        if args[0] == "merge-base":
            return SHA_A + "\n"
        if args[0] == "rev-list":
            return SHA_B + "\n" + SHA_C + "\n"
        raise AssertionError(args)

    monkeypatch.setattr(h, "git", fake_git)
    monkeypatch.setattr(h, "comparison_parent", lambda root, base, sha: SHA_A if sha == SHA_B else SHA_B)
    assert h.pr_edges(tmp_path, SHA_A, SHA_C) == [(SHA_A, SHA_B), (SHA_B, SHA_C)]


def test_hardening_status_and_projection_defensive_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "git", lambda *a: SHA_A + "\n" + SHA_B + "\n" + SHA_C + "\n")
    monkeypatch.setattr(h, "commit_parents", lambda root, sha: [] if sha == SHA_C else [SHA_A])

    states = {
        SHA_A: None,
        SHA_B: {"status": "OPEN"},
        SHA_C: {"status": "COMPLETE"},
    }
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: states.get(sha))
    assert h.first_status_commit(tmp_path, "registry/reviews/R.yaml", "COMPLETE", SHA_C) == SHA_C

    states[SHA_C] = {"status": "OPEN"}
    assert h.first_status_commit(tmp_path, "registry/reviews/R.yaml", "COMPLETE", SHA_C) is None

    projection = h.review_semantic_projection(
        {
            "status": "COMPLETE",
            "outcome": "APPROVE",
            "artifact": {},
            "reviewer": "legacy",
            "roles": [],
            "scope": {},
            "findings": ["bad", {"id": "F", "severity": "R2_MAJOR", "noise": 1}],
        }
    )
    assert projection["reviewer"] == "legacy"
    assert projection["findings"] == [{"id": "F", "severity": "R2_MAJOR"}]
    assert h.review_semantic_projection(None) == {}


def test_authority_evidence_all_fail_closed_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    policy = {
        "governed_repository": {
            "permission_proof": "TEST-1",
            "metadata_url": "https://api.github.com/repos/o/r",
            "owner_login": "owner",
            "full_name": "o/r",
        }
    }
    owner_acceptance = {
        "accepted_by": "owner",
        "authority_role": "REPOSITORY_OWNER",
        "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION",
        "authority_evidence_ref": "https://api.github.com/repos/o/r",
    }
    monkeypatch.setattr(h, "load_mapping", lambda path: {"id": "TEST-1", "status": "PASS"})
    assert h.authority_evidence_valid(tmp_path, "WORK-1", owner_acceptance, policy)
    monkeypatch.setattr(h, "load_mapping", lambda path: {})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", owner_acceptance, policy)

    base = {
        "accepted_by": "alice",
        "authority_role": "WORK_OWNER",
        "authority_evidence_type": "WORK_ITEM_OWNER_BINDING",
        "authority_evidence_ref": "not-registry",
    }
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", base, policy)
    base["authority_evidence_ref"] = "registry/work-items/WORK-1.yaml"
    monkeypatch.setattr(h, "load_mapping", lambda path: {})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", base, policy)
    monkeypatch.setattr(h, "load_mapping", lambda path: {"owner": "alice"})
    assert h.authority_evidence_valid(tmp_path, "WORK-1", base, policy)

    delegated = {
        "accepted_by": "alice",
        "authority_role": "SECURITY_AUTHORITY",
        "authority_evidence_type": "UNKNOWN",
        "authority_evidence_ref": "registry/delegations/D.yaml",
    }
    monkeypatch.setattr(h, "load_mapping", lambda path: {"actor": "alice"})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", delegated, policy)
    delegated["authority_evidence_type"] = "GOVERNANCE_DELEGATION"
    monkeypatch.setattr(h, "load_mapping", lambda path: {"actor": "bob", "role": "SECURITY_AUTHORITY", "scope": {"work_items": ["WORK-1"]}})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", delegated, policy)
    monkeypatch.setattr(h, "load_mapping", lambda path: {"actor": "alice", "role": "OTHER", "scope": {"work_items": ["WORK-1"]}})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", delegated, policy)
    monkeypatch.setattr(h, "load_mapping", lambda path: {"actor": "alice", "role": "SECURITY_AUTHORITY", "scope": "bad"})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", delegated, policy)
    monkeypatch.setattr(h, "load_mapping", lambda path: {"actor": "alice", "role": "SECURITY_AUTHORITY", "scope": {"repositories": ["o/r"]}})
    assert h.authority_evidence_valid(tmp_path, "WORK-1", delegated, policy)


def _review() -> dict:
    return {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "artifact": {"commit_sha": SHA_A},
        "reviewer": {"context_id": "ctx"},
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
            "import_commit": SHA_B,
            "authorization_commit": SHA_A,
            "source_review_id": "src",
            "source_submitted_at": "2026-09-14T00:00:00Z",
        },
    }


def _review_auth(consumed):
    return {
        "record_id": "REVIEW-1",
        "imported_status": "COMPLETE",
        "artifact_commit_sha": SHA_A,
        "source_review_id": "src",
        "source_submitted_at": "2026-09-14T00:00:00Z",
        "reviewer_context_id": "ctx",
        "expected_outcome": "APPROVE",
        "one_shot": True,
        "consumed_by_commit": consumed,
    }


def test_review_import_finalized_branch_matrix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert h.review_import_finalized(tmp_path, {}, SHA_C, "r")
    assert not h.review_import_finalized(tmp_path, {"external_import": "bad"}, SHA_C, "r")
    bad_mode = _review(); bad_mode["external_import"]["mode"] = "other"
    assert not h.review_import_finalized(tmp_path, bad_mode, SHA_C, "r")
    bad_sha = _review(); bad_sha["external_import"]["import_commit"] = "x"
    assert not h.review_import_finalized(tmp_path, bad_sha, SHA_C, "r")

    review = _review()
    monkeypatch.setattr(h, "git_ok", lambda *a: False)
    assert not h.review_import_finalized(tmp_path, review, SHA_C, "r")
    monkeypatch.setattr(h, "git_ok", lambda *a: True)
    monkeypatch.setattr(h, "first_status_commit", lambda *a: SHA_C)
    assert not h.review_import_finalized(tmp_path, review, SHA_C, "r")
    monkeypatch.setattr(h, "first_status_commit", lambda *a: SHA_B)
    monkeypatch.setattr(h, "is_ancestor", lambda *a: False)
    assert not h.review_import_finalized(tmp_path, review, SHA_C, "r")
    monkeypatch.setattr(h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(
        h,
        "show_yaml",
        lambda root, sha, path: {"registry_machines": {"reviews": {"external_import_authorizations": [_review_auth(None if sha == SHA_A else SHA_B)]}}},
    )
    assert h.review_import_finalized(tmp_path, review, SHA_C, "r")


def _test_record() -> dict:
    return {
        "id": "TEST-1",
        "status": "PASS",
        "acceptance_cold_read": {
            "source": {"source_id": "src", "submitted_at": "2026-09-14T00:00:00Z"},
            "executor": {"context_id": "ctx"},
        },
        "execution": {"commit_sha": SHA_C, "result": "PASS"},
        "external_import": {
            "authorization_source": f"registry/status-machines.yaml@{SHA_A}#x",
            "import_commit": SHA_B,
        },
    }


def _test_auth(consumed):
    return {
        "record_id": "TEST-1",
        "imported_status": "PASS",
        "execution_commit_sha": SHA_C,
        "source_id": "src",
        "source_submitted_at": "2026-09-14T00:00:00Z",
        "executor_context_id": "ctx",
        "expected_result": "PASS",
        "one_shot": True,
        "consumed_by_commit": consumed,
    }


def test_test_import_finalized_branch_matrix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert h.test_import_finalized(tmp_path, {}, SHA_C, "t")
    assert not h.test_import_finalized(tmp_path, {"external_import": "bad"}, SHA_C, "t")
    bad = _test_record(); bad["external_import"]["authorization_source"] = "bad"
    assert not h.test_import_finalized(tmp_path, bad, SHA_C, "t")
    bad = _test_record(); bad["external_import"]["import_commit"] = "bad"
    assert not h.test_import_finalized(tmp_path, bad, SHA_C, "t")

    test = _test_record()
    monkeypatch.setattr(h, "git_ok", lambda *a: False)
    assert not h.test_import_finalized(tmp_path, test, SHA_C, "t")
    monkeypatch.setattr(h, "git_ok", lambda *a: True)
    monkeypatch.setattr(h, "first_status_commit", lambda *a: SHA_C)
    assert not h.test_import_finalized(tmp_path, test, SHA_C, "t")
    monkeypatch.setattr(h, "first_status_commit", lambda *a: SHA_B)
    monkeypatch.setattr(h, "is_ancestor", lambda *a: False)
    assert not h.test_import_finalized(tmp_path, test, SHA_C, "t")
    monkeypatch.setattr(h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(
        h,
        "show_yaml",
        lambda root, sha, path: {"registry_machines": {"tests": {"external_execution_import_authorizations": [_test_auth(None if sha == SHA_A else SHA_B)]}}},
    )
    assert h.test_import_finalized(tmp_path, test, SHA_C, "t")


def test_requirement_and_progress_validators_cover_skip_delete_invalid_and_reopen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "changed_files", lambda *a: ["README.md", "registry/requirements/REQ-1.yaml"])

    def req_yaml(root: Path, sha: str, path: str):
        if path.endswith("REQ-1.yaml"):
            return {"status": "PROPOSED"} if sha == SHA_A else {
                "status": "ACCEPTED",
                "verification": {"acceptance_evidence": ["REVIEW-1"], "acceptance_cold_read_test_ids": ["TEST-1"]},
            }
        if "reviews" in path:
            return _review()
        if "tests" in path:
            return _test_record()
        return {}

    monkeypatch.setattr(h, "show_yaml", req_yaml)
    monkeypatch.setattr(h, "review_import_finalized", lambda *a: False)
    monkeypatch.setattr(h, "pass_test_execution_revision_valid", lambda *a: False)
    rules = {x.rule for x in h.validate_requirement_acceptance_proof(tmp_path, [(SHA_A, SHA_B)])}
    assert rules == {"REQ_REVIEW_IMPORT_FINALIZATION", "REQ_COLD_READ_REVISION", "REQ_COLD_READ_IMPORT"}

    before = {"quality_dimensions": {"q": "DONE", "same": "READY"}}
    after_delete = {"quality_dimensions": {"same": "READY"}}
    machine = {"progress": {"initial": "PLANNED", "transitions": {"DONE": ["IN_REVIEW"], "PLANNED": ["READY"]}}, "registry_machines": {"work_items": {"initial": "PLANNED", "transitions": {}}}}
    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: machine if path.endswith("status-machines.yaml") else (before if sha == SHA_A else after_delete))
    assert {x.rule for x in h.validate_progress_lifecycle(tmp_path, [(SHA_A, SHA_B)])} == {"PROGRESS_DELETE"}

    after_invalid = {"quality_dimensions": {"q": "BLOCKED", "same": "READY"}}
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: machine if path.endswith("status-machines.yaml") else (before if sha == SHA_A else after_invalid))
    assert {x.rule for x in h.validate_progress_lifecycle(tmp_path, [(SHA_A, SHA_B)])} == {"PROGRESS_TRANSITION"}

    after_reopen = {"quality_dimensions": {"q": "IN_REVIEW", "same": "READY"}}
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: machine if path.endswith("status-machines.yaml") else (before if sha == SHA_A else after_reopen))
    monkeypatch.setattr(h, "reopening_triggered", lambda *a: False)
    assert {x.rule for x in h.validate_progress_lifecycle(tmp_path, [(SHA_A, SHA_B)])} == {"PROGRESS_REOPENING"}
    monkeypatch.setattr(h, "reopening_triggered", lambda *a: True)
    assert h.validate_progress_lifecycle(tmp_path, [(SHA_A, SHA_B)]) == []
    monkeypatch.setattr(h, "changed_files", lambda *a: ["README.md"])
    assert h.validate_progress_lifecycle(tmp_path, [(SHA_A, SHA_B)]) == []


def test_flatten_and_reopening_trigger_defensive_shapes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = {
        "phases": {
            "bad": "x",
            "P": {
                "status": "IN_PROGRESS",
                "lots": {
                    "bad": "x",
                    "L": {
                        "status": "IN_PROGRESS",
                        "sublots": {
                            "bad": "x",
                            "S": {"status": "IN_PROGRESS", "work_items": {"bad": "x", "WORK-1": {"status": "DONE", "gate": "PASS", "n": 1}}},
                        },
                    },
                },
            },
        },
        "quality_dimensions": {"q": "PASS", "n": 1},
    }
    flat = h.flatten_progress(data)
    assert flat["work:WORK-1"] == "DONE"
    assert flat["progress:work:WORK-1:gate"] == "PASS"

    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/work-items/WORK-2.yaml"])
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: {"id": "WORK-2", "review_plan": {"open_findings": ["F"]}})
    assert not h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")

    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/work-items/WORK-1.yaml"])
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: {"id": "WORK-1", "review_plan": {"open_findings": [] if sha == SHA_A else ["F"]}})
    assert h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")

    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: {"id": "WORK-1", "scope_change": {} if sha == SHA_A else {"approved": True, "rationale": "new"}})
    assert h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")

    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/reviews/REVIEW-1.yaml"])
    monkeypatch.setattr(h, "show_yaml", lambda *a: {"status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "scope": {"work_items": ["WORK-1"]}})
    assert h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")
    assert h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:quality:q")


def test_squash_done_and_orchestration_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "load_mapping", lambda path: {"squash_integrations": ["bad", {}, {"historical_only": True, "future_reuse_forbidden": True}]})
    assert {x.rule for x in h.validate_squash_flags(tmp_path)} == {"SQUASH_PROVENANCE_SHAPE", "SQUASH_PROVENANCE_REUSE"}
    monkeypatch.setattr(
        h,
        "load_mapping",
        lambda path: (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {},
    )

    work_dir = tmp_path / "registry/work-items"; work_dir.mkdir(parents=True)
    review_dir = tmp_path / "registry/reviews"; review_dir.mkdir(parents=True)
    (work_dir / "WORK-0.yaml").write_text(yaml.safe_dump({"id": "WORK-0", "status": "IN_PROGRESS"}), encoding="utf-8")
    (work_dir / "WORK-1.yaml").write_text(yaml.safe_dump({
        "id": "WORK-1", "status": "DONE", "assurance": {"level": "A3"},
        "implementation_plan": {"tasks": ["bad", {"status": "IN_PROGRESS"}], "planned_runs": [{"status": "DONE"}]},
        "review_plan": {"completed_reviews": ["REVIEW-1"]},
    }), encoding="utf-8")
    (review_dir / "REVIEW-1.yaml").write_text(yaml.safe_dump({
        "id": "REVIEW-1", "status": "COMPLETE", "findings": ["bad", {"severity": "R4_MINOR", "disposition": "ACCEPTED"}, {"id": "F", "severity": "R2_MAJOR", "disposition": "ACCEPTED", "acceptance": {}}]
    }), encoding="utf-8")
    monkeypatch.setattr(h, "review_import_finalized", lambda *a: False)
    monkeypatch.setattr(h, "accepted_finding_authorized", lambda *a: False)
    rules = {x.rule for x in h.validate_done_tasks_runs_and_authority(tmp_path, SHA_A)}
    assert rules == {"DONE_TASK_RUN", "REVIEW_IMPORT_MATERIALIZATION", "FINDING_ACCEPTANCE_AUTHORITY"}

    validators = [
        "validate_checkout_ref", "validate_completed_review_immutability", "validate_requirement_acceptance_proof",
        "validate_progress_lifecycle", "validate_squash_flags", "validate_done_tasks_runs_and_authority",
    ]
    monkeypatch.setattr(h, "pr_edges", lambda *a: [(SHA_A, SHA_B)])
    for name in validators:
        monkeypatch.setattr(h, name, lambda *a, name=name: [h.Finding(name, name, name)])
    assert len(h.run(tmp_path, SHA_A, SHA_B)) == len(validators)


def test_hardening_main_success_findings_json_and_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.json"
    monkeypatch.setattr(h, "run", lambda *a: [h.Finding("p", "R", "m")])
    assert h.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B, "--json-out", str(out)]) == 1
    assert '"rule": "R"' in out.read_text(encoding="utf-8")
    assert "ERROR R p: m" in capsys.readouterr().err
    monkeypatch.setattr(h, "run", lambda *a: [])
    assert h.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 0
    monkeypatch.setattr(h, "run", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert h.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 2


def test_followup_tree_import_iter_and_done_work_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(f.h, "git_ok", lambda *a: False)
    assert f.tree_sha(tmp_path, SHA_A) is None
    monkeypatch.setattr(f.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(f.h, "git", lambda *a: "bad")
    assert f.tree_sha(tmp_path, SHA_A) is None
    monkeypatch.setattr(f.h, "git", lambda *a: SHA_C)
    assert f.tree_sha(tmp_path, SHA_A) == SHA_C

    assert list(f.iter_test_ids("use TEST-1 and TEST-2")) == ["TEST-1", "TEST-2"]
    assert list(f.iter_test_ids({"x": ["TEST-3", 4]})) == ["TEST-3"]
    assert list(f.iter_test_ids(3)) == []

    monkeypatch.setattr(f.h, "test_import_finalized", lambda *a: True)
    assert f.test_import_finalized(tmp_path, {}, SHA_A, "p")
    monkeypatch.setattr(f.h, "test_import_finalized", lambda *a: False)
    monkeypatch.setattr(f, "test_squash_materialization_valid", lambda *a: False)
    assert not f.test_import_finalized(tmp_path, _test_record(), SHA_A, "p")
    monkeypatch.setattr(f, "test_squash_materialization_valid", lambda *a: True)
    bad = _test_record(); bad["external_import"]["authorization_source"] = "bad"
    assert not f.test_import_finalized(tmp_path, bad, SHA_A, "p")

    work_dir = tmp_path / "registry/work-items"; work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "WORK-0.yaml").write_text("x", encoding="utf-8")
    (work_dir / "WORK-1.yaml").write_text("x", encoding="utf-8")
    mappings = {
        "WORK-0.yaml": {"id": "WORK-0", "status": "IN_PROGRESS"},
        "WORK-1.yaml": {"id": "WORK-1", "status": "DONE", "required_tests": {"x": ["TEST-1", "TEST-1"]}},
        "TEST-1.yaml": {"id": "TEST-1", "external_import": {}},
    }
    monkeypatch.setattr(f.h, "load_mapping", lambda path: mappings.get(path.name, {}))
    monkeypatch.setattr(f, "test_import_finalized", lambda *a: False)
    findings = f.validate_done_test_imports(tmp_path, SHA_A)
    assert [x.rule for x in findings] == ["DONE_TEST_IMPORT_MATERIALIZATION"]
    assert f.run(tmp_path, SHA_B, SHA_A) == findings


def test_followup_squash_and_finalized_success_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    test = _test_record()
    monkeypatch.setattr(f.h, "load_mapping", lambda *a: {"squash_integrations": ["bad", {"eligible_test_ids": []}, {
        "eligible_test_ids": ["TEST-1"], "source_head_sha": SHA_B, "integrated_commit_sha": SHA_C,
        "expected_tree_sha": SHA_A, "historical_only": True, "future_reuse_forbidden": True,
    }]})
    monkeypatch.setattr(f.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(f, "tree_sha", lambda root, sha: SHA_A)
    monkeypatch.setattr(f.h, "first_status_commit", lambda *a: SHA_B)
    assert f.test_squash_materialization_valid(tmp_path, test, SHA_C, "p")

    monkeypatch.setattr(f.h, "test_import_finalized", lambda *a: False)
    monkeypatch.setattr(f, "test_squash_materialization_valid", lambda *a: True)
    monkeypatch.setattr(f.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(f.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(
        f.h,
        "show_yaml",
        lambda root, sha, path: {"registry_machines": {"tests": {"external_execution_import_authorizations": [_test_auth(None if sha == SHA_A else SHA_B)]}}},
    )
    assert f.test_import_finalized(tmp_path, test, SHA_C, "p")


def test_gate_tree_adoption_squash_finalization_run_and_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(g.h, "git_ok", lambda *a: False)
    assert g.tree_sha(tmp_path, SHA_A) is None
    monkeypatch.setattr(g.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(g.h, "git", lambda *a: "bad")
    assert g.tree_sha(tmp_path, SHA_A) is None
    monkeypatch.setattr(g.h, "git", lambda *a: SHA_C)
    assert g.tree_sha(tmp_path, SHA_A) == SHA_C

    monkeypatch.setattr(g.h, "load_mapping", lambda *a: {"enforcement_adoptions": ["bad", {"rule_id": "other"}, {
        "rule_id": g.RULE_ID, "adoption_commit_sha": SHA_A, "guard_path": ".github/scripts/governance_l2_hardening.py",
        "historical_only": True, "future_reuse_forbidden": True,
    }]})
    monkeypatch.setattr(g.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(g.h, "commit_parents", lambda *a: [SHA_B])
    monkeypatch.setattr(g.h, "changed_files", lambda *a: [])
    assert g.progress_adoption_sha(tmp_path, SHA_C) == SHA_A
    monkeypatch.setattr(g.h, "commit_parents", lambda *a: [])
    assert g.progress_adoption_sha(tmp_path, SHA_C) is None

    review = _review()
    monkeypatch.setattr(g.h, "load_mapping", lambda *a: {"squash_integrations": [{
        "eligible_review_ids": ["REVIEW-1"], "source_head_sha": SHA_B, "integrated_commit_sha": SHA_C,
        "expected_tree_sha": SHA_A, "historical_only": True, "future_reuse_forbidden": True,
    }]})
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(g, "tree_sha", lambda root, sha: SHA_A)
    monkeypatch.setattr(g.h, "first_status_commit", lambda *a: SHA_B)
    assert g.review_squash_materialization_valid(tmp_path, review, SHA_C, "p")

    monkeypatch.setattr(g, "BASE_REVIEW_IMPORT_FINALIZED", lambda *a: True)
    assert g.review_import_finalized(tmp_path, review, SHA_C, "p")
    monkeypatch.setattr(g, "BASE_REVIEW_IMPORT_FINALIZED", lambda *a: False)
    monkeypatch.setattr(g, "review_squash_materialization_valid", lambda *a: False)
    assert not g.review_import_finalized(tmp_path, review, SHA_C, "p")
    monkeypatch.setattr(g, "review_squash_materialization_valid", lambda *a: True)
    malformed = _review(); malformed["external_import"] = "bad"
    assert not g.review_import_finalized(tmp_path, malformed, SHA_C, "p")

    monkeypatch.setattr(g.h, "pr_edges", lambda *a: [(SHA_A, SHA_B)])
    monkeypatch.setattr(g.h, "validate_checkout_ref", lambda *a: [])
    monkeypatch.setattr(g.h, "validate_completed_review_immutability", lambda *a: [])
    monkeypatch.setattr(g, "progress_adoption_sha", lambda *a: None)
    for name in ["validate_requirement_acceptance_proof", "validate_progress_lifecycle", "validate_squash_flags", "validate_done_tasks_runs_and_authority"]:
        monkeypatch.setattr(g.h, name, lambda *a: [])
    monkeypatch.setattr(g.f, "run", lambda *a: [])
    findings = g.run(tmp_path, SHA_A, SHA_B)
    assert [x.rule for x in findings] == ["ENFORCEMENT_ADOPTION"]

    monkeypatch.setattr(g, "progress_adoption_sha", lambda *a: SHA_A)
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    assert g.run(tmp_path, SHA_A, SHA_B) == []

    out = tmp_path / "gate.json"
    monkeypatch.setattr(g, "run", lambda *a: [g.h.Finding("p", "R", "m")])
    assert g.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B, "--json-out", str(out)]) == 1
    assert out.exists()
    assert "ERROR R p: m" in capsys.readouterr().err
    monkeypatch.setattr(g, "run", lambda *a: [])
    assert g.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 0
    monkeypatch.setattr(g, "run", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert g.main([str(tmp_path), "--base", SHA_A, "--head", SHA_B]) == 2
