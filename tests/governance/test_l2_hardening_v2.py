from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

MODULE_PATH = Path(__file__).resolve().parents[2] / ".github/scripts/governance_l2_hardening.py"
SPEC = importlib.util.spec_from_file_location("governance_l2_hardening", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
h = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = h
SPEC.loader.exec_module(h)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "l2-hardening@example.invalid")
    git(root, "config", "user.name", "l2-hardening")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_checkout_guard_requires_exact_head(tmp_path: Path) -> None:
    wf = {"jobs": {"validate": {"steps": [{"uses": "actions/checkout@" + "a" * 40, "with": {"ref": h.CHECKOUT_REF}}]}}}
    dump(tmp_path / ".github/workflows/_governance-core.yml", wf)
    assert h.validate_checkout_ref(tmp_path) == []
    wf["jobs"]["validate"]["steps"][0]["with"].pop("ref")
    dump(tmp_path / ".github/workflows/_governance-core.yml", wf)
    assert {x.rule for x in h.validate_checkout_ref(tmp_path)} == {"EXACT_HEAD_CHECKOUT"}


def test_complete_review_semantics_are_immutable(tmp_path: Path) -> None:
    init_git(tmp_path)
    review = {"id": "REVIEW-1", "status": "COMPLETE", "outcome": "CHANGES_REQUIRED", "artifact": {"commit_sha": "a" * 40}, "reviewer": {"context_id": "ctx", "independence_level": "L2"}, "roles": ["SECURITY"], "scope": {"work_items": ["WORK-1"]}, "findings": []}
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    before = commit(tmp_path, "complete")
    review["outcome"] = "APPROVE"
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    after = commit(tmp_path, "rewrite")
    assert {x.rule for x in h.validate_completed_review_immutability(tmp_path, [(before, after)])} == {"COMPLETE_REVIEW_IMMUTABLE"}


def policy() -> dict:
    return {"version": 1, "governed_repository": {"full_name": "owner/monde", "owner_login": "owner", "metadata_url": "https://api.github.com/repos/owner/monde", "permission_proof": "TEST-7"}, "vocabulary": {"authority_roles": {"DESIGNATED_RISK_AUTHORITY": {"allowed_evidence_types": ["GOVERNANCE_DELEGATION"]}}}, "finding_acceptance": {"matrix": {"A3": {"R2_MAJOR": ["DESIGNATED_RISK_AUTHORITY"]}}}}


def test_delegation_binds_actor_role_and_scope(tmp_path: Path) -> None:
    p = policy()
    ref = "registry/delegations/D-1.yaml"
    acceptance = {"accepted_by": "alice", "authority_role": "DESIGNATED_RISK_AUTHORITY", "authority_evidence_type": "GOVERNANCE_DELEGATION", "authority_evidence_ref": ref}
    dump(tmp_path / ref, {"actor": "alice", "role": "DESIGNATED_RISK_AUTHORITY", "scope": {"work_items": ["WORK-1"]}})
    assert h.authority_evidence_valid(tmp_path, "WORK-1", acceptance, p)
    dump(tmp_path / ref, {"actor": "mallory", "role": "DESIGNATED_RISK_AUTHORITY", "scope": {"work_items": ["WORK-1"]}})
    assert not h.authority_evidence_valid(tmp_path, "WORK-1", acceptance, p)


def test_review_import_requires_real_first_complete_commit(tmp_path: Path) -> None:
    init_git(tmp_path)
    review = {"id": "REVIEW-1", "status": "COMPLETE", "outcome": "APPROVE", "artifact": {"commit_sha": "b" * 40}, "reviewer": {"context_id": "ctx"}, "external_import": {"mode": "PREAUTHORIZED_EXTERNAL_COMPLETION", "authorization_commit": None, "source_review_id": "SRC", "source_submitted_at": "2026-09-14T00:00:00Z", "import_commit": None}}
    auth = {"record_id": "REVIEW-1", "imported_status": "COMPLETE", "artifact_commit_sha": "b" * 40, "source_review_id": "SRC", "source_submitted_at": "2026-09-14T00:00:00Z", "reviewer_context_id": "ctx", "expected_outcome": "APPROVE", "one_shot": True, "consumed_by_commit": None}
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    auth_sha = commit(tmp_path, "authorize")
    review["external_import"]["authorization_commit"] = auth_sha
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    import_sha = commit(tmp_path, "import")
    review["external_import"]["import_commit"] = import_sha
    auth["consumed_by_commit"] = import_sha
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    head = commit(tmp_path, "bind")
    assert h.review_import_finalized(tmp_path, review, head, "registry/reviews/REVIEW-1.yaml")
    review["external_import"]["import_commit"] = head
    assert not h.review_import_finalized(tmp_path, review, head, "registry/reviews/REVIEW-1.yaml")


def test_test_import_requires_real_first_pass_commit(tmp_path: Path) -> None:
    init_git(tmp_path)
    test = {"id": "TEST-1", "status": "PLANNED", "acceptance_cold_read": {"source": {"source_id": "SRC", "submitted_at": "2026-09-14T00:00:00Z"}, "executor": {"context_id": "ctx"}}, "execution": {"commit_sha": "b" * 40, "result": "PASS"}, "external_import": {"authorization_source": None, "import_commit": None}}
    auth = {"record_id": "TEST-1", "imported_status": "PASS", "execution_commit_sha": "b" * 40, "source_id": "SRC", "source_submitted_at": "2026-09-14T00:00:00Z", "executor_context_id": "ctx", "expected_result": "PASS", "one_shot": True, "consumed_by_commit": None}
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"tests": {"external_execution_import_authorizations": [auth]}}})
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    auth_sha = commit(tmp_path, "authorize")
    test["external_import"]["authorization_source"] = f"registry/status-machines.yaml@{auth_sha}#tests.TEST-1"
    test["status"] = "PASS"
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    import_sha = commit(tmp_path, "import pass")
    test["external_import"]["import_commit"] = import_sha
    auth["consumed_by_commit"] = import_sha
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"tests": {"external_execution_import_authorizations": [auth]}}})
    head = commit(tmp_path, "bind")
    assert h.test_import_finalized(tmp_path, test, head, "registry/tests/TEST-1.yaml")


def test_requirement_acceptance_rechecks_import_and_revision(monkeypatch, tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/requirements/REQ-1.yaml", {"id": "REQ-1", "status": "PROPOSED"})
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", {"id": "REVIEW-1", "status": "COMPLETE"})
    dump(tmp_path / "registry/tests/TEST-1.yaml", {"id": "TEST-1", "status": "PASS"})
    before = commit(tmp_path, "proposed")
    dump(tmp_path / "registry/requirements/REQ-1.yaml", {"id": "REQ-1", "status": "ACCEPTED", "verification": {"acceptance_evidence": ["REVIEW-1"], "acceptance_cold_read_test_ids": ["TEST-1"]}})
    after = commit(tmp_path, "accept")
    monkeypatch.setattr(h, "review_import_finalized", lambda *a, **k: False)
    monkeypatch.setattr(h, "pass_test_execution_revision_valid", lambda *a, **k: False)
    monkeypatch.setattr(h, "test_import_finalized", lambda *a, **k: False)
    assert {x.rule for x in h.validate_requirement_acceptance_proof(tmp_path, [(before, after)])} == {"REQ_REVIEW_IMPORT_FINALIZATION", "REQ_COLD_READ_REVISION", "REQ_COLD_READ_IMPORT"}


def machine() -> dict:
    return {"registry_machines": {"work_items": {"initial": "PROPOSED", "transitions": {"PROPOSED": ["PLANNED"], "PLANNED": ["IN_PROGRESS"], "IN_PROGRESS": ["IN_REVIEW"], "IN_REVIEW": ["DONE"], "DONE": []}}}, "progress": {"initial": "NOT_STARTED", "transitions": {"NOT_STARTED": ["PLANNED", "IN_PROGRESS", "DONE"], "PLANNED": ["IN_PROGRESS", "DONE"], "IN_PROGRESS": ["IN_REVIEW", "DONE"], "IN_REVIEW": ["DONE"], "DONE": ["IN_REVIEW", "DEPRECATED"]}}}


def matrix(review: str) -> dict:
    return {"phases": {"P": {"status": "IN_PROGRESS", "lots": {"L": {"status": "IN_PROGRESS", "sublots": {"S": {"status": "IN_REVIEW", "work_items": {"WORK-1": {"status": "IN_REVIEW", "review": review}}}}}}}}, "quality_dimensions": {}}


def test_progress_reopening_needs_trigger(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/status-machines.yaml", machine())
    dump(tmp_path / "registry/progress/matrix.yaml", matrix("DONE"))
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "IN_REVIEW", "review_plan": {"open_findings": []}})
    before = commit(tmp_path, "done")
    dump(tmp_path / "registry/progress/matrix.yaml", matrix("IN_REVIEW"))
    after = commit(tmp_path, "silent reopen")
    assert {x.rule for x in h.validate_progress_lifecycle(tmp_path, [(before, after)])} == {"PROGRESS_REOPENING"}


def test_progress_invalid_edge_rejected(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/status-machines.yaml", machine())
    dump(tmp_path / "registry/progress/matrix.yaml", matrix("DONE"))
    before = commit(tmp_path, "done")
    dump(tmp_path / "registry/progress/matrix.yaml", matrix("PARTIAL"))
    after = commit(tmp_path, "invalid")
    assert {x.rule for x in h.validate_progress_lifecycle(tmp_path, [(before, after)])} == {"PROGRESS_TRANSITION"}


def test_squash_flags_required(tmp_path: Path) -> None:
    dump(tmp_path / "registry/integration-provenance.yaml", {"squash_integrations": [{"historical_only": True, "future_reuse_forbidden": True}]})
    assert h.validate_squash_flags(tmp_path) == []
    dump(tmp_path / "registry/integration-provenance.yaml", {"squash_integrations": [{"historical_only": False, "future_reuse_forbidden": True}]})
    assert {x.rule for x in h.validate_squash_flags(tmp_path)} == {"SQUASH_PROVENANCE_REUSE"}


def test_done_work_requires_terminal_tasks_and_runs(tmp_path: Path) -> None:
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE", "implementation_plan": {"tasks": [{"id": "T1", "status": "IN_PROGRESS"}], "planned_runs": [{"id": "R1", "status": "DONE"}]}, "review_plan": {"completed_reviews": []}, "assurance": {"level": "A3"}})
    assert {x.rule for x in h.validate_done_tasks_runs_and_authority(tmp_path, "a" * 40)} == {"DONE_TASK_RUN"}


def test_accepted_finding_needs_scoped_authority(tmp_path: Path) -> None:
    dump(tmp_path / "registry/acceptance-authority.yaml", policy())
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE", "assurance": {"level": "A3"}, "implementation_plan": {"tasks": [{"id": "T1", "status": "DONE"}], "planned_runs": [{"id": "R1", "status": "DONE"}]}, "review_plan": {"completed_reviews": ["REVIEW-1"]}})
    acceptance = {"accepted_by": "alice", "authority_role": "DESIGNATED_RISK_AUTHORITY", "authority_evidence_type": "GOVERNANCE_DELEGATION", "authority_evidence_ref": "registry/delegations/D-1.yaml", "authority_matrix_version": 1, "authority_rule_id": "FINDING:A3:R2_MAJOR", "rationale": "x", "accepted_at": "2026-09-14", "review_condition": "later"}
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", {"id": "REVIEW-1", "status": "COMPLETE", "findings": [{"id": "F-1", "severity": "R2_MAJOR", "disposition": "ACCEPTED", "acceptance": acceptance}]})
    dump(tmp_path / "registry/delegations/D-1.yaml", {"actor": "alice", "role": "DESIGNATED_RISK_AUTHORITY", "scope": {"work_items": ["WORK-2"]}})
    assert "FINDING_ACCEPTANCE_AUTHORITY" in {x.rule for x in h.validate_done_tasks_runs_and_authority(tmp_path, "a" * 40)}
