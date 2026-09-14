from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


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


def review_record() -> dict:
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


def review_auth(consumed):
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


def test_hardening_loop_and_review_skip_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "git", lambda *a: SHA_A + "\n" + SHA_C + "\n")
    monkeypatch.setattr(h, "commit_parents", lambda root, sha: [SHA_B] if sha == SHA_A else [])

    def status_yaml(root: Path, sha: str, path: str):
        if sha in {SHA_A, SHA_B}:
            return {"status": "COMPLETE"}
        return {"status": "OPEN"}

    monkeypatch.setattr(h, "show_yaml", status_yaml)
    assert h.first_status_commit(tmp_path, "registry/reviews/R.yaml", "COMPLETE", SHA_C) is None

    monkeypatch.setattr(h, "changed_files", lambda *a: ["README.md", "registry/reviews/R.yaml"])
    calls = {"n": 0}

    def review_yaml(root: Path, sha: str, path: str):
        calls["n"] += 1
        if calls["n"] <= 2:
            return {"status": "OPEN"}
        return {"status": "COMPLETE", "outcome": "APPROVE", "reviewer": {}, "findings": []}

    monkeypatch.setattr(h, "show_yaml", review_yaml)
    assert h.validate_completed_review_immutability(tmp_path, [(SHA_A, SHA_B), (SHA_B, SHA_C)]) == []


def test_hardening_requirement_and_flatten_false_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/requirements/REQ-1.yaml"])
    monkeypatch.setattr(h, "show_yaml", lambda root, sha, path: {"status": "PROPOSED"})
    assert h.validate_requirement_acceptance_proof(tmp_path, [(SHA_A, SHA_B)]) == []

    current = {
        "status": "ACCEPTED",
        "verification": {
            "acceptance_evidence": ["REVIEW-1", "REVIEW-2"],
            "acceptance_cold_read_test_ids": ["TEST-1", "TEST-2"],
        },
    }

    def accepted_yaml(root: Path, sha: str, path: str):
        if path.endswith("REQ-1.yaml"):
            return {"status": "PROPOSED"} if sha == SHA_A else current
        return {}

    monkeypatch.setattr(h, "show_yaml", accepted_yaml)
    monkeypatch.setattr(h, "review_import_finalized", lambda root, review, head, path: path.endswith("REVIEW-1.yaml"))
    monkeypatch.setattr(h, "pass_test_execution_revision_valid", lambda root, test, head: True)
    monkeypatch.setattr(h, "test_import_finalized", lambda root, test, head, path: path.endswith("TEST-1.yaml"))
    rules = [item.rule for item in h.validate_requirement_acceptance_proof(tmp_path, [(SHA_A, SHA_B)])]
    assert rules == ["REQ_REVIEW_IMPORT_FINALIZATION", "REQ_COLD_READ_IMPORT"]

    flat = h.flatten_progress(
        {
            "phases": {
                "P": {
                    "lots": {
                        "L": {
                            "sublots": {
                                "S": {"work_items": {"WORK-1": {"status": 1, "other": 2}}}
                            }
                        }
                    }
                }
            },
            "quality_dimensions": {"q": 1},
        }
    )
    assert flat == {}


def test_hardening_reopening_noop_and_authorized_acceptance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(h, "changed_files", lambda *a: ["registry/work-items/WORK-1.yaml", "README.md", "registry/reviews/R.yaml"])

    def yaml_state(root: Path, sha: str, path: str):
        if path.startswith("registry/work-items/"):
            return {
                "id": "WORK-1",
                "review_plan": {"open_findings": []},
                "scope_change": {"approved": False},
            }
        if path.startswith("registry/reviews/"):
            return {"status": "COMPLETE", "outcome": "APPROVE", "scope": {"work_items": ["WORK-1"]}}
        return {}

    monkeypatch.setattr(h, "show_yaml", yaml_state)
    assert not h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")

    work_dir = tmp_path / "registry/work-items"
    review_dir = tmp_path / "registry/reviews"
    work_dir.mkdir(parents=True)
    review_dir.mkdir(parents=True)
    (work_dir / "WORK-1.yaml").write_text(
        "id: WORK-1\nstatus: DONE\nassurance:\n  level: A3\nreview_plan:\n  completed_reviews: [REVIEW-1]\nimplementation_plan:\n  tasks: []\n  planned_runs: []\n",
        encoding="utf-8",
    )
    (review_dir / "REVIEW-1.yaml").write_text(
        "id: REVIEW-1\nstatus: COMPLETE\nfindings:\n  - id: F-1\n    severity: R2_MAJOR\n    disposition: ACCEPTED\n    acceptance: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(h, "review_import_finalized", lambda *a: True)
    monkeypatch.setattr(h, "accepted_finding_authorized", lambda *a: True)
    assert h.validate_done_tasks_runs_and_authority(tmp_path, SHA_A) == []


def test_followup_residual_returns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = {"id": "TEST-1", "status": "PASS", "external_import": {"import_commit": "bad"}}
    assert not f.test_squash_materialization_valid(tmp_path, bad, SHA_C, "p")

    test = {"id": "TEST-1", "status": "PASS", "external_import": {"import_commit": SHA_A}}
    monkeypatch.setattr(
        f.h,
        "load_mapping",
        lambda *a: {
            "squash_integrations": [
                {"eligible_test_ids": ["TEST-1"], "historical_only": False},
            ]
        },
    )
    assert not f.test_squash_materialization_valid(tmp_path, test, SHA_C, "p")

    monkeypatch.setattr(
        f.h,
        "load_mapping",
        lambda *a: {
            "squash_integrations": [
                {
                    "eligible_test_ids": ["TEST-1"],
                    "source_head_sha": SHA_B,
                    "integrated_commit_sha": SHA_C,
                    "expected_tree_sha": SHA_A,
                    "historical_only": True,
                    "future_reuse_forbidden": True,
                }
            ]
        },
    )
    monkeypatch.setattr(f.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(f, "tree_sha", lambda *a: SHA_A)
    monkeypatch.setattr(f.h, "first_status_commit", lambda *a: SHA_C)
    assert not f.test_squash_materialization_valid(tmp_path, test, SHA_C, "p")

    full = {
        "id": "TEST-1",
        "status": "PASS",
        "external_import": {
            "authorization_source": f"registry/status-machines.yaml@{SHA_A}#x",
            "import_commit": SHA_B,
        },
    }
    monkeypatch.setattr(f.h, "test_import_finalized", lambda *a: False)
    monkeypatch.setattr(f, "test_squash_materialization_valid", lambda *a: True)
    monkeypatch.setattr(f.h, "git_ok", lambda *a: False)
    assert not f.test_import_finalized(tmp_path, full, SHA_C, "p")


def test_gate_residual_failure_and_success_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        g.h,
        "load_mapping",
        lambda *a: {
            "enforcement_adoptions": [
                {
                    "rule_id": g.RULE_ID,
                    "adoption_commit_sha": "bad",
                    "guard_path": ".github/scripts/governance_l2_hardening.py",
                    "historical_only": True,
                    "future_reuse_forbidden": True,
                }
            ]
        },
    )
    assert g.progress_adoption_sha(tmp_path, SHA_C) is None

    bad_review = review_record()
    bad_review["external_import"]["import_commit"] = "bad"
    assert not g.review_squash_materialization_valid(tmp_path, bad_review, SHA_C, "p")

    review = review_record()
    monkeypatch.setattr(g.h, "load_mapping", lambda *a: {"squash_integrations": [{"eligible_review_ids": ["REVIEW-1"], "historical_only": False}]})
    assert not g.review_squash_materialization_valid(tmp_path, review, SHA_C, "p")

    monkeypatch.setattr(
        g.h,
        "load_mapping",
        lambda *a: {
            "squash_integrations": [
                {
                    "eligible_review_ids": ["REVIEW-1"],
                    "source_head_sha": SHA_B,
                    "integrated_commit_sha": SHA_C,
                    "expected_tree_sha": SHA_A,
                    "historical_only": True,
                    "future_reuse_forbidden": True,
                }
            ]
        },
    )
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(g, "tree_sha", lambda *a: SHA_A)
    monkeypatch.setattr(g.h, "first_status_commit", lambda *a: SHA_C)
    assert not g.review_squash_materialization_valid(tmp_path, review, SHA_C, "p")

    monkeypatch.setattr(g, "BASE_REVIEW_IMPORT_FINALIZED", lambda *a: False)
    monkeypatch.setattr(g, "review_squash_materialization_valid", lambda *a: True)
    wrong_mode = review_record()
    wrong_mode["external_import"]["mode"] = "other"
    assert not g.review_import_finalized(tmp_path, wrong_mode, SHA_C, "p")

    monkeypatch.setattr(g.h, "git_ok", lambda *a: False)
    assert not g.review_import_finalized(tmp_path, review_record(), SHA_C, "p")

    monkeypatch.setattr(g.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(
        g.h,
        "show_yaml",
        lambda root, sha, path: {
            "registry_machines": {
                "reviews": {
                    "external_import_authorizations": [review_auth(None if sha == SHA_A else SHA_B)]
                }
            }
        },
    )
    assert g.review_import_finalized(tmp_path, review_record(), SHA_C, "p")


def test_script_entrypoints_execute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for filename in ["governance_l2_hardening.py", "governance_l2_gate.py"]:
        path = ROOT / ".github/scripts" / filename
        monkeypatch.setattr(sys, "argv", [str(path), str(tmp_path), "--base", SHA_A, "--head", SHA_B])
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(str(path), run_name="__main__")
        assert exc.value.code == 2
