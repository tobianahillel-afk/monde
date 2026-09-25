from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

import tools.governance.change_guard as cg
from tools.governance import context_manifest as cm
from tools.governance.strict_contracts import test_external_import_bound_and_consumed, validate_work_lifecycle

ROOT = Path(__file__).resolve().parents[2]
H_PATH = ROOT / ".github/scripts/governance_l2_hardening.py"
H_SPEC = importlib.util.spec_from_file_location("governance_l2_hardening", H_PATH)
assert H_SPEC is not None and H_SPEC.loader is not None
h = importlib.util.module_from_spec(H_SPEC)
sys.modules[H_SPEC.name] = h
H_SPEC.loader.exec_module(h)
F_PATH = ROOT / ".github/scripts/governance_l2_followup.py"
F_SPEC = importlib.util.spec_from_file_location("governance_l2_followup", F_PATH)
assert F_SPEC is not None and F_SPEC.loader is not None
f = importlib.util.module_from_spec(F_SPEC)
sys.modules[F_SPEC.name] = f
F_SPEC.loader.exec_module(f)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "followup@example.invalid")
    git(root, "config", "user.name", "followup")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def identity_policy() -> dict:
    return yaml.safe_load((ROOT / "registry/content-identity.yaml").read_text(encoding="utf-8"))


def requirement() -> tuple[dict, str]:
    value = {
        "id": "REQ-1",
        "title": "Bound revision",
        "type": "FUNCTIONAL",
        "normative_statement": "The system SHALL bind the reviewed revision.",
        "scope": {"in": ["proof"], "out": []},
        "depends_on": [],
        "conflicts_with": [],
        "semantics": {"subject": "proof"},
        "verification": {"method": "independent review"},
        "risk": {"criticality": "HIGH", "failure_impact": "false acceptance"},
        "status": "PROPOSED",
    }
    digest = cg.requirement_normative_digest(ROOT, value, identity_policy())
    assert digest is not None
    value["content_identity"] = {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}
    return value, digest


def cold_test(digest: str, execution_sha: str) -> dict:
    return {
        "status": "PASS",
        "protects": {"requirements": ["REQ-1"]},
        "execution": {"commit_sha": execution_sha},
        "acceptance_cold_read": {
            "qualifies": True,
            "executor": {"independence_level": "L2", "fresh_context": True, "authoring_context_separated": True},
            "requirements": {"REQ-1": {"content_digest": digest, "status_at_read": "PROPOSED"}},
            "required_outcomes": {
                "understood_without_author_reasoning": "PASS",
                "atomic_and_testable": "PASS",
                "dependencies_and_conflicts_checked": "PASS",
                "omissions_and_failure_modes_checked": "PASS",
                "evidence_plan_sufficient": "PASS",
            },
            "all_required_outcomes_pass": True,
        },
    }


def test_acceptance_review_requires_real_reachable_proposed_revision(tmp_path: Path, monkeypatch) -> None:
    init_git(tmp_path)
    req, digest = requirement()
    dump(tmp_path / "registry/content-identity.yaml", identity_policy())
    dump(tmp_path / "registry/requirements/REQ-1.yaml", req)
    reviewed = commit(tmp_path, "proposed revision")
    review = {"artifact": {"commit_sha": reviewed}}
    assert cg.review_requirement_revision_valid(tmp_path, reviewed, "REQ-1", digest, review)
    assert not cg.review_requirement_revision_valid(tmp_path, reviewed, "REQ-1", digest, {"artifact": {"commit_sha": "f" * 40}})
    req["status"] = "ACCEPTED"
    dump(tmp_path / "registry/requirements/REQ-1.yaml", req)
    accepted = commit(tmp_path, "accepted")
    assert not cg.review_requirement_revision_valid(tmp_path, accepted, "REQ-1", digest, {"artifact": {"commit_sha": accepted}})

    req["verification"].update({"acceptance_evidence": ["REVIEW-1"], "acceptance_cold_read_test_ids": ["TEST-1"]})
    records = {
        "registry/content-identity.yaml": identity_policy(),
        "registry/reviews/REVIEW-1.yaml": {
            "status": "COMPLETE",
            "outcome": "APPROVE",
            "artifact": {"commit_sha": "f" * 40},
            "reviewer": {"independence_level": "L2"},
            "scope": {"requirements": ["REQ-1"], "requirement_revisions": {"REQ-1": {"digest": digest, "status_at_review": "PROPOSED"}}},
        },
        "registry/tests/TEST-1.yaml": cold_test(digest, reviewed),
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    assert not cg.requirement_acceptance_satisfied(tmp_path, accepted, req)
    assert cg.commit_exists(tmp_path, reviewed)
    assert not cg.commit_exists(tmp_path, "short")


def test_risk_delegation_binds_actor_role_and_scope(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"risks": {"acceptance_preconditions": {"required_fields": [
        "resolution.accepted", "resolution.accepted_by", "resolution.authority_role", "resolution.authority_evidence_type",
        "resolution.authority_evidence_ref", "resolution.authority_matrix_version", "resolution.authority_rule_id",
        "resolution.acceptance_rationale", "resolution.accepted_at", "resolution.review_condition",
    ]}}}})
    policy = yaml.safe_load((ROOT / "registry/acceptance-authority.yaml").read_text(encoding="utf-8"))
    dump(tmp_path / "registry/acceptance-authority.yaml", policy)
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "assurance": {"level": "A3"}})
    delegation = {"actor": "alice", "role": "DESIGNATED_RISK_AUTHORITY", "scope": {"work_items": ["WORK-1"]}}
    dump(tmp_path / "registry/delegation.yaml", delegation)
    risk = {
        "id": "RISK-1", "category": "ENGINEERING", "scope": {"work_items": ["WORK-1"]}, "assessment": {"impact": "MEDIUM"},
        "resolution": {
            "accepted": True, "accepted_by": "alice", "authority_role": "DESIGNATED_RISK_AUTHORITY",
            "authority_evidence_type": "GOVERNANCE_DELEGATION", "authority_evidence_ref": "registry/delegation.yaml",
            "authority_matrix_version": 1, "authority_rule_id": "RISK_DEFAULT:A3:MEDIUM",
            "acceptance_rationale": "bounded", "accepted_at": "2026-09-14", "review_condition": "revisit",
        },
    }
    dump(tmp_path / "registry/risks/RISK-1.yaml", risk)
    head = commit(tmp_path, "delegated risk")
    assert cg.risk_acceptance_satisfied(tmp_path, head, risk)
    assert cg._values("x") == {"x"}
    assert cg._values(["x", 3]) == {"x"}
    assert cg._values(None) == set()
    delegation["role"] = "WRONG"
    dump(tmp_path / "registry/delegation.yaml", delegation)
    bad_role = commit(tmp_path, "wrong role")
    assert not cg.risk_acceptance_satisfied(tmp_path, bad_role, risk)
    delegation["role"] = "DESIGNATED_RISK_AUTHORITY"
    delegation["scope"] = {"work_items": ["WORK-OTHER"]}
    dump(tmp_path / "registry/delegation.yaml", delegation)
    bad_scope = commit(tmp_path, "wrong scope")
    assert not cg.risk_acceptance_satisfied(tmp_path, bad_scope, risk)


def test_test_import_authorization_applies_to_existing_transition(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / cg.GUARD_PATH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / cg.GUARD_PATH).write_text("# adopted\n", encoding="utf-8")
    auth = {
        "record_id": "TEST-1", "from_status": "PLANNED", "imported_status": "PASS", "execution_commit_sha": "e" * 40,
        "source_id": "RUN", "source_submitted_at": "2026-09-14T00:00:00Z", "executor_context_id": "ctx",
        "expected_result": "PASS", "one_shot": True, "consumed_by_commit": None,
    }
    machine = {"registry_machines": {"tests": {"initial": "PLANNED", "transitions": {"PLANNED": ["READY"], "READY": ["RUNNING"], "RUNNING": ["PASS"]}, "historical_import_exceptions": [], "external_execution_import_authorizations": [auth]}}}
    dump(tmp_path / "registry/status-machines.yaml", machine)
    dump(tmp_path / "registry/tests/TEST-1.yaml", {"id": "TEST-1", "status": "PLANNED"})
    base = commit(tmp_path, "authorize while planned")
    imported = {
        "id": "TEST-1", "status": "PASS",
        "acceptance_cold_read": {"source": {"source_id": "RUN", "submitted_at": "2026-09-14T00:00:00Z"}, "executor": {"context_id": "ctx"}},
        "execution": {"commit_sha": "e" * 40, "result": "PASS"},
        "external_import": {"authorization_source": f"registry/status-machines.yaml@{base}#registry_machines.tests.external_execution_import_authorizations.TEST-1", "import_commit": None},
    }
    dump(tmp_path / "registry/tests/TEST-1.yaml", imported)
    head = commit(tmp_path, "import external result")
    previous = {"id": "TEST-1", "status": "PLANNED"}
    assert cg.test_external_execution_transition_allowed(tmp_path, base, head, previous, imported)
    assert "STATE_TRANSITION" not in {item.rule for item in cg.validate(tmp_path, base, head)}
    imported["external_import"]["import_commit"] = head
    assert not cg.test_external_execution_transition_allowed(tmp_path, base, head, previous, imported)
    imported["external_import"] = {"authorization_source": "bad", "import_commit": None}
    assert not cg.test_external_execution_transition_allowed(tmp_path, base, head, previous, imported)


def test_test_external_import_cannot_be_an_alternate_initial_state(monkeypatch, tmp_path: Path) -> None:
    specs = {"initial": "PLANNED", "historical_import_exceptions": [{"record_id": "TEST-H", "imported_status": "PASS", "import_commit": "m"}]}
    monkeypatch.setattr(cg, "canonical_machine_spec", lambda *args: specs)
    assert cg.record_introduction_allowed(tmp_path, "p", "m", "h", "tests", {"id": "TEST-1", "status": "PLANNED"})
    assert cg.record_introduction_allowed(tmp_path, "p", "m", "h", "tests", {"id": "TEST-H", "status": "PASS"})
    assert not cg.record_introduction_allowed(tmp_path, "p", "m", "h", "tests", {"id": "TEST-NEW", "status": "PASS", "external_import": {"authorization_source": "x@y"}})


def import_test(import_commit: str, consumed: str | None) -> tuple[dict, dict]:
    test = {
        "id": "TEST-1", "status": "PASS",
        "acceptance_cold_read": {"source": {"source_id": "RUN", "submitted_at": "2026-09-14T00:00:00Z"}, "executor": {"context_id": "ctx"}},
        "external_import": {"authorization_source": "registry/status-machines.yaml@" + "a" * 40 + "#tests.TEST-1", "import_commit": import_commit},
        "execution": {"command_or_workflow": "ci", "commit_sha": "b" * 40, "result": "PASS", "evidence": ["proof"]},
    }
    auth = {"record_id": "TEST-1", "imported_status": "PASS", "execution_commit_sha": "b" * 40, "source_id": "RUN", "source_submitted_at": "2026-09-14T00:00:00Z", "executor_context_id": "ctx", "expected_result": "PASS", "one_shot": True, "consumed_by_commit": consumed}
    machine = {"registry_machines": {"tests": {"external_execution_import_authorizations": [auth]}}}
    return test, machine


def test_done_test_requires_import_binding_and_consumption(tmp_path: Path) -> None:
    import_commit = "c" * 40
    test, machine = import_test(import_commit, import_commit)
    assert test_external_import_bound_and_consumed(test, machine)
    assert test_external_import_bound_and_consumed({"status": "PASS"}, machine)
    test_bad = yaml.safe_load(yaml.safe_dump(test)); test_bad["external_import"] = "bad"
    assert not test_external_import_bound_and_consumed(test_bad, machine)
    _, unconsumed = import_test(import_commit, None)
    assert not test_external_import_bound_and_consumed(test, unconsumed)

    dump(tmp_path / "registry/status-machines.yaml", unconsumed)
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE", "depends_on": [], "review_plan": {"independence_level": "L0", "completed_reviews": []}, "required_tests": {"e2e": ["TEST-1"]}, "completion": {"specification_gates_checked": True}})
    assert "DONE_TEST_IMPORT" in {issue.rule for issue in validate_work_lifecycle(tmp_path)}


def test_followup_checks_real_test_import_materialization(tmp_path: Path) -> None:
    init_git(tmp_path)
    auth = {"record_id": "TEST-1", "from_status": "PLANNED", "imported_status": "PASS", "execution_commit_sha": "d" * 40, "source_id": "RUN", "source_submitted_at": "2026-09-14T00:00:00Z", "executor_context_id": "ctx", "expected_result": "PASS", "one_shot": True, "consumed_by_commit": None}
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"tests": {"external_execution_import_authorizations": [auth]}}})
    dump(tmp_path / "registry/tests/TEST-1.yaml", {"id": "TEST-1", "status": "PLANNED"})
    auth_sha = commit(tmp_path, "authorize")
    test = {"id": "TEST-1", "status": "PASS", "acceptance_cold_read": {"source": {"source_id": "RUN", "submitted_at": "2026-09-14T00:00:00Z"}, "executor": {"context_id": "ctx"}}, "external_import": {"authorization_source": f"registry/status-machines.yaml@{auth_sha}#tests.TEST-1", "import_commit": None}, "execution": {"commit_sha": "d" * 40, "result": "PASS"}}
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    imported = commit(tmp_path, "result import")
    test["external_import"]["import_commit"] = imported
    auth["consumed_by_commit"] = imported
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"tests": {"external_execution_import_authorizations": [auth]}}})
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE", "required_tests": {"e2e": ["TEST-1"]}})
    head = commit(tmp_path, "bind and consume")
    assert f.test_import_finalized(tmp_path, test, head, "registry/tests/TEST-1.yaml")
    assert f.validate_done_test_imports(tmp_path, head) == []
    test["external_import"]["import_commit"] = "f" * 40
    dump(tmp_path / "registry/tests/TEST-1.yaml", test)
    assert {item.rule for item in f.validate_done_test_imports(tmp_path, head)} == {"DONE_TEST_IMPORT_MATERIALIZATION"}


def test_context_changed_files_are_computed_from_merge_base(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / "tracked.yaml").write_text("old\n", encoding="utf-8")
    root = commit(tmp_path, "root")
    git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "tracked.yaml").write_text("same-final\n", encoding="utf-8")
    head = commit(tmp_path, "feature change")
    git(tmp_path, "checkout", "-b", "base-tip", root)
    (tmp_path / "tracked.yaml").write_text("same-final\n", encoding="utf-8")
    base_tip = commit(tmp_path, "base converges")
    assert "tracked.yaml" not in git(tmp_path, "diff", "--name-only", f"{base_tip}..{head}").splitlines()
    assert cm.changed(tmp_path, base_tip, head) == ["tracked.yaml"]
