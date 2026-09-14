from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    count = s.count(old)
    assert count == 1, f"{label}: expected 1 occurrence, got {count}"
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tests/governance/test_current_gap_regressions.py",
    '    assert validate_review_findings("work.yaml", "REVIEW-1", review) == []\n',
    '    assert validate_review_findings(tmp_path, "work.yaml", "REVIEW-1", review, "A3") == []\n',
    "review finding signature",
)

replace_once(
    "tests/governance/test_strict_contracts.py",
    '    dump(root / "registry/tests/TEST-0001.yaml", {"id": "TEST-0001", "status": "PASS"})\n',
    '    dump(root / "registry/tests/TEST-0001.yaml", {"id": "TEST-0001", "status": "PASS", "execution": {"command_or_workflow": "pytest", "commit_sha": "0" * 40, "result": "PASS", "evidence": ["ci"]}})\n',
    "PASS fixture execution",
)

Path("tests/governance/test_review0029_branches.py").write_text(r'''from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import tools.governance.change_guard as cg
from tools.governance.strict_contracts import accepted_finding_authorized, pass_test_has_execution


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def run(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def commit(root: Path, message: str) -> str:
    run(root, "add", "-A")
    run(root, "commit", "-m", message)
    return run(root, "rev-parse", "HEAD")


def init_repo(root: Path) -> str:
    run(root, "init")
    run(root, "config", "user.email", "test@example.com")
    run(root, "config", "user.name", "test")
    dump(
        root / "registry/status-machines.yaml",
        {
            "registry_machines": {
                "work_items": {"initial": "PROPOSED", "transitions": {"PROPOSED": ["PLANNED"], "PLANNED": ["IN_PROGRESS"], "IN_PROGRESS": ["IN_REVIEW"], "IN_REVIEW": ["DONE"]}},
                "reviews": {"initial": "OPEN", "transitions": {"OPEN": ["IN_PROGRESS"], "IN_PROGRESS": ["COMPLETE"]}, "external_import_authorizations": []},
                "tests": {"initial": "PLANNED", "transitions": {"PLANNED": ["READY"], "READY": ["RUNNING"], "RUNNING": ["PASS", "FAIL"]}, "historical_import_exceptions": [], "external_execution_import_authorizations": []},
                "requirements": {"initial": "PROPOSED", "transitions": {"PROPOSED": ["ACCEPTED"]}},
            }
        },
    )
    return commit(root, "base")


def test_endpoint_helper_requires_merge_base(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "git", lambda *args, **kwargs: "")
    with pytest.raises(RuntimeError):
        cg.endpoint_changed_files(tmp_path, "base", "head")

    calls = []
    def fake_git(root, *args):
        calls.append(args)
        if args[0] == "merge-base":
            return "mergebase"
        return "a\nb\n"
    monkeypatch.setattr(cg, "git", fake_git)
    assert cg.endpoint_changed_files(tmp_path, "base", "head") == ["a", "b"]
    assert calls[0] == ("merge-base", "base", "head")


def test_machine_helpers_and_independence(tmp_path: Path) -> None:
    head = init_repo(tmp_path)
    assert cg.canonical_machine_spec(tmp_path, head, "tests")["initial"] == "PLANNED"
    assert cg.canonical_machine_spec(tmp_path, head, "missing") == {}
    assert cg.review_independence_rank("L3_TARGET") == 3
    assert cg.review_independence_rank("garbage") == -1


def test_historical_test_import_exception(tmp_path: Path) -> None:
    base = init_repo(tmp_path)
    machine = yaml.safe_load((tmp_path / "registry/status-machines.yaml").read_text())
    machine["registry_machines"]["tests"]["historical_import_exceptions"] = [
        {"record_id": "TEST-1", "imported_status": "PASS", "import_commit": "PLACEHOLDER"}
    ]
    dump(tmp_path / "registry/status-machines.yaml", machine)
    pre = commit(tmp_path, "policy")
    dump(tmp_path / "registry/tests/TEST-1.yaml", {"id": "TEST-1", "status": "PASS"})
    candidate = commit(tmp_path, "materialize")
    machine = yaml.safe_load((tmp_path / "registry/status-machines.yaml").read_text())
    machine["registry_machines"]["tests"]["historical_import_exceptions"][0]["import_commit"] = candidate
    dump(tmp_path / "registry/status-machines.yaml", machine)
    policy = commit(tmp_path, "bind historical exception")
    current = {"id": "TEST-1", "status": "PASS"}
    assert cg.historical_import_allowed(tmp_path, pre, candidate, policy, "tests", current)
    assert not cg.historical_import_allowed(tmp_path, pre, candidate, policy, "experiments", current)


def test_review_one_shot_import_branches(tmp_path: Path) -> None:
    init_repo(tmp_path)
    machine = yaml.safe_load((tmp_path / "registry/status-machines.yaml").read_text())
    machine["registry_machines"]["reviews"]["external_import_authorizations"] = [{
        "record_id": "REVIEW-1", "imported_status": "COMPLETE", "artifact_commit_sha": "a" * 40,
        "source_review_id": "SRC", "reviewer_context_id": "ctx", "expected_outcome": "CHANGES_REQUIRED",
        "one_shot": True, "consumed_by_commit": None,
    }]
    dump(tmp_path / "registry/status-machines.yaml", machine)
    auth = commit(tmp_path, "auth")
    current = {
        "id": "REVIEW-1", "status": "COMPLETE", "artifact": {"commit_sha": "a" * 40},
        "reviewer": {"context_id": "ctx"}, "outcome": "CHANGES_REQUIRED",
        "external_import": {"authorization_commit": auth, "source_review_id": "SRC"},
    }
    assert cg.historical_import_allowed(tmp_path, auth, auth, auth, "reviews", current)
    bad = dict(current); bad["external_import"] = {"authorization_commit": "short", "source_review_id": "SRC"}
    assert not cg.historical_import_allowed(tmp_path, auth, auth, auth, "reviews", bad)
    bad = dict(current); bad["outcome"] = "APPROVE"
    assert not cg.historical_import_allowed(tmp_path, auth, auth, auth, "reviews", bad)


def test_test_one_shot_import_branches(tmp_path: Path) -> None:
    init_repo(tmp_path)
    machine = yaml.safe_load((tmp_path / "registry/status-machines.yaml").read_text())
    machine["registry_machines"]["tests"]["external_execution_import_authorizations"] = [{
        "record_id": "TEST-1", "imported_status": "PASS", "execution_commit_sha": "b" * 40,
        "source_id": "RUN", "expected_result": "PASS", "one_shot": True, "consumed_by_commit": None,
    }]
    dump(tmp_path / "registry/status-machines.yaml", machine)
    auth = commit(tmp_path, "auth")
    current = {
        "id": "TEST-1", "status": "PASS", "execution": {"commit_sha": "b" * 40, "result": "PASS"},
        "external_import": {"authorization_source": "registry/status-machines.yaml@tests.external_execution_import_authorizations"},
        "acceptance_cold_read": {"source": {"source_id": "RUN"}},
    }
    assert cg.historical_import_allowed(tmp_path, auth, auth, auth, "tests", current)
    bad = dict(current); bad["external_import"] = {"authorization_source": "no-at-sign"}
    assert not cg.historical_import_allowed(tmp_path, auth, auth, auth, "tests", bad)


def test_record_introduction_initial_and_exception(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "canonical_machine_spec", lambda *args: {"initial": "OPEN"})
    assert cg.record_introduction_allowed(tmp_path, "p", "m", "h", "reviews", {"id": "R", "status": "OPEN"})
    monkeypatch.setattr(cg, "historical_import_allowed", lambda *args: True)
    assert cg.record_introduction_allowed(tmp_path, "p", "m", "h", "reviews", {"id": "R", "status": "COMPLETE"})


def test_requirement_acceptance_helper_negative_and_positive(monkeypatch, tmp_path: Path) -> None:
    bad = {"id": "REQ-1", "content_identity": {"scheme": "bad", "digest": "nope"}}
    assert not cg.requirement_acceptance_satisfied(tmp_path, "h", bad)

    digest = "sha256:" + "a" * 64
    req = {"id": "REQ-1", "content_identity": {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}, "verification": {"acceptance_evidence": ["junk", "REVIEW-1"], "acceptance_cold_read_test_ids": ["junk", "TEST-1"]}}
    records = {
        "registry/reviews/REVIEW-1.yaml": {"status": "COMPLETE", "outcome": "APPROVE", "reviewer": {"independence_level": "L2"}, "scope": {"requirements": ["REQ-1"], "requirement_revisions": {"REQ-1": {"digest": digest, "status_at_review": "PROPOSED"}}}},
        "registry/tests/TEST-1.yaml": {"status": "PASS", "protects": {"requirements": ["REQ-1"]}, "execution": {"commit_sha": "b" * 40}, "acceptance_cold_read": {"qualifies": True, "executor": {"independence_level": "L2", "fresh_context": True, "authoring_context_separated": True}, "requirements": {"REQ-1": {"content_digest": digest, "status_at_read": "PROPOSED"}}, "required_outcomes": {"understood_without_author_reasoning": "PASS", "atomic_and_testable": "PASS", "dependencies_and_conflicts_checked": "PASS", "omissions_and_failure_modes_checked": "PASS", "evidence_plan_sufficient": "PASS"}, "all_required_outcomes_pass": True}},
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    assert cg.requirement_acceptance_satisfied(tmp_path, "h", req)
    records["registry/reviews/REVIEW-1.yaml"]["outcome"] = "CHANGES_REQUIRED"
    assert not cg.requirement_acceptance_satisfied(tmp_path, "h", req)


def test_test_semantic_projection_splits_contract_from_result() -> None:
    base = {"name": "n", "type": "UNIT", "protects": {"contracts": ["c"]}, "cases": {"happy": ["x"]}, "execution": {"command_or_workflow": "pytest", "commit_sha": "a" * 40, "result": "PASS", "evidence": ["one"]}}
    changed_meta = yaml.safe_load(yaml.safe_dump(base)); changed_meta["execution"]["evidence"] = ["two"]
    assert cg.test_semantic_projection(base) == cg.test_semantic_projection(changed_meta)
    changed_contract = yaml.safe_load(yaml.safe_dump(base)); changed_contract["cases"] = {"happy": ["different"]}
    assert cg.test_semantic_projection(base) != cg.test_semantic_projection(changed_contract)
    assert cg.test_semantic_projection(None) == {}


def test_pass_execution_helper() -> None:
    assert not pass_test_has_execution({"status": "PASS"})
    assert pass_test_has_execution({"status": "PASS", "execution": {"command_or_workflow": "pytest", "commit_sha": "a" * 40, "result": "PASS", "evidence": ["ci"]}})


def test_authority_helper_branches(tmp_path: Path) -> None:
    policy = {
        "version": 1,
        "vocabulary": {"authority_roles": {"REPOSITORY_OWNER": {"allowed_evidence_types": ["GITHUB_REPOSITORY_OWNER_PERMISSION"]}, "WORK_OWNER": {"allowed_evidence_types": ["WORK_ITEM_OWNER_BINDING"]}, "DESIGNATED_RISK_AUTHORITY": {"allowed_evidence_types": ["GOVERNANCE_DELEGATION"]}}},
        "finding_acceptance": {"matrix": {"A3": {"R2_MAJOR": ["REPOSITORY_OWNER", "DESIGNATED_RISK_AUTHORITY"]}}},
    }
    dump(tmp_path / "registry/acceptance-authority.yaml", policy)
    base = {"severity": "R2_MAJOR", "acceptance": {"accepted_by": "owner", "authority_role": "REPOSITORY_OWNER", "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION", "authority_evidence_ref": "https://api.github.com/repos/owner/repo", "authority_matrix_version": 1, "authority_rule_id": "FINDING:A3:R2_MAJOR", "rationale": "x", "accepted_at": "now", "review_condition": "later"}}
    assert accepted_finding_authorized(tmp_path, "A3", base)
    missing = yaml.safe_load(yaml.safe_dump(base)); missing["acceptance"]["rationale"] = ""
    assert not accepted_finding_authorized(tmp_path, "A3", missing)
    bad_role = yaml.safe_load(yaml.safe_dump(base)); bad_role["acceptance"]["authority_role"] = "WORK_OWNER"; bad_role["acceptance"]["authority_evidence_type"] = "WORK_ITEM_OWNER_BINDING"
    assert not accepted_finding_authorized(tmp_path, "A3", bad_role)
    bad_version = yaml.safe_load(yaml.safe_dump(base)); bad_version["acceptance"]["authority_matrix_version"] = 2
    assert not accepted_finding_authorized(tmp_path, "A3", bad_version)
    bad_ref = yaml.safe_load(yaml.safe_dump(base)); bad_ref["acceptance"]["authority_evidence_ref"] = "not-github"
    assert not accepted_finding_authorized(tmp_path, "A3", bad_ref)
    work = yaml.safe_load(yaml.safe_dump(base)); work["acceptance"].update({"accepted_by": "x", "authority_role": "WORK_OWNER", "authority_evidence_type": "WORK_ITEM_OWNER_BINDING", "authority_evidence_ref": "registry/work-items/W.yaml"}); policy["finding_acceptance"]["matrix"]["A3"]["R2_MAJOR"].append("WORK_OWNER"); dump(tmp_path / "registry/acceptance-authority.yaml", policy); dump(tmp_path / "registry/work-items/W.yaml", {"id": "W"})
    assert accepted_finding_authorized(tmp_path, "A3", work)
    delegated = yaml.safe_load(yaml.safe_dump(base)); delegated["acceptance"].update({"accepted_by": "x", "authority_role": "DESIGNATED_RISK_AUTHORITY", "authority_evidence_type": "GOVERNANCE_DELEGATION", "authority_evidence_ref": "registry/delegation.yaml"}); dump(tmp_path / "registry/delegation.yaml", {"ok": True})
    assert accepted_finding_authorized(tmp_path, "A3", delegated)
    delegated["acceptance"]["authority_evidence_type"] = "UNKNOWN"
    assert not accepted_finding_authorized(tmp_path, "A3", delegated)
''', encoding="utf-8")
