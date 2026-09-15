from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import tools.governance.change_guard as cg
from tools.governance.proof_contracts import (
    pass_test_execution_revision_valid,
    requirement_normative_digest,
    review_external_import_finalized,
)
from tools.governance.strict_contracts import accepted_finding_authorized, validate_work_lifecycle
from tools.governance.validate_repo import Validator


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "review0030@example.invalid")
    git(root, "config", "user.name", "review0030")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_duplicate_yaml_keys_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "registry/work-items/WORK-1.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("id: WORK-1\nstatus: PLANNED\nstatus: DONE\n", encoding="utf-8")
    validator = Validator(tmp_path)
    assert validator.load_yaml(path) is None
    assert "YAML_PARSE" in {issue.rule for issue in validator.issues}


def test_repository_owner_authority_is_bound_to_governed_repo(tmp_path: Path) -> None:
    policy = yaml.safe_load(Path("registry/acceptance-authority.yaml").read_text(encoding="utf-8"))
    dump(tmp_path / "registry/acceptance-authority.yaml", policy)
    finding = {
        "severity": "R2_MAJOR",
        "acceptance": {
            "accepted_by": "tobianahillel-afk",
            "authority_role": "REPOSITORY_OWNER",
            "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION",
            "authority_evidence_ref": "https://api.github.com/repos/tobianahillel-afk/monde",
            "authority_matrix_version": 1,
            "authority_rule_id": "FINDING:A3:R2_MAJOR",
            "rationale": "owner decision",
            "accepted_at": "2026-09-14",
            "review_condition": "revisit on contract change",
        },
    }
    assert accepted_finding_authorized(tmp_path, "A3", finding)
    finding["acceptance"]["authority_evidence_ref"] = "https://api.github.com/repos/tobianahillel-afk/unrelated"
    assert not accepted_finding_authorized(tmp_path, "A3", finding)


def test_external_review_must_be_bound_and_consumed() -> None:
    import_commit = "a" * 40
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "artifact": {"commit_sha": "b" * 40},
        "reviewer": {"context_id": "ctx"},
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
            "authorization_commit": "c" * 40,
            "source_review_id": "SRC",
            "import_commit": import_commit,
        },
    }
    machine = {
        "registry_machines": {
            "reviews": {
                "external_import_authorizations": [
                    {
                        "record_id": "REVIEW-1",
                        "imported_status": "COMPLETE",
                        "artifact_commit_sha": "b" * 40,
                        "source_review_id": "SRC",
                        "reviewer_context_id": "ctx",
                        "expected_outcome": "APPROVE",
                        "one_shot": True,
                        "consumed_by_commit": import_commit,
                    }
                ]
            }
        }
    }
    assert review_external_import_finalized(review, machine)
    machine["registry_machines"]["reviews"]["external_import_authorizations"][0]["consumed_by_commit"] = None
    assert not review_external_import_finalized(review, machine)


def test_pass_test_execution_revision_must_exist_and_be_reachable(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / "proof.txt").write_text("one", encoding="utf-8")
    tested = commit(tmp_path, "tested")
    (tmp_path / "proof.txt").write_text("two", encoding="utf-8")
    head = commit(tmp_path, "head")
    test = {"execution": {"commit_sha": tested}}
    assert pass_test_execution_revision_valid(tmp_path, test, head)
    test["execution"]["commit_sha"] = "f" * 40
    assert not pass_test_execution_revision_valid(tmp_path, test, head)


def test_requirement_acceptance_recomputes_jcs_digest(monkeypatch, tmp_path: Path) -> None:
    identity = yaml.safe_load(Path("registry/content-identity.yaml").read_text(encoding="utf-8"))
    requirement = {
        "id": "REQ-1",
        "title": "Canonical identity",
        "type": "FUNCTIONAL",
        "normative_statement": "The system SHALL bind evidence.",
        "scope": {"in": ["proof"], "out": []},
        "depends_on": [],
        "conflicts_with": [],
        "semantics": {"subject": "proof"},
        "verification": {"method": "review"},
        "risk": {"criticality": "HIGH", "failure_impact": "false acceptance"},
    }
    digest = requirement_normative_digest(tmp_path, requirement, identity)
    assert digest is not None
    requirement["content_identity"] = {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}
    requirement["verification"].update(
        {"acceptance_evidence": ["REVIEW-1"], "acceptance_cold_read_test_ids": ["TEST-1"]}
    )
    records = {
        "registry/content-identity.yaml": identity,
        "registry/reviews/REVIEW-1.yaml": {
            "status": "COMPLETE",
            "outcome": "APPROVE",
            "reviewer": {"independence_level": "L2"},
            "scope": {
                "requirements": ["REQ-1"],
                "requirement_revisions": {"REQ-1": {"digest": digest, "status_at_review": "PROPOSED"}},
            },
        },
        "registry/tests/TEST-1.yaml": {
            "status": "PASS",
            "protects": {"requirements": ["REQ-1"]},
            "execution": {"commit_sha": "d" * 40},
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
        },
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    assert cg.requirement_acceptance_satisfied(tmp_path, "head", requirement)
    requirement["normative_statement"] = "The system SHALL accept anything."
    assert not cg.requirement_acceptance_satisfied(tmp_path, "head", requirement)


def test_risk_acceptance_requires_unique_owning_work_and_authority(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(
        tmp_path / "registry/status-machines.yaml",
        {
            "registry_machines": {
                "risks": {
                    "acceptance_preconditions": {
                        "required_fields": [
                            "resolution.accepted",
                            "resolution.accepted_by",
                            "resolution.authority_role",
                            "resolution.authority_evidence_type",
                            "resolution.authority_evidence_ref",
                            "resolution.authority_matrix_version",
                            "resolution.authority_rule_id",
                            "resolution.acceptance_rationale",
                            "resolution.accepted_at",
                            "resolution.review_condition",
                        ]
                    }
                }
            }
        },
    )
    policy = yaml.safe_load(Path("registry/acceptance-authority.yaml").read_text(encoding="utf-8"))
    dump(tmp_path / "registry/acceptance-authority.yaml", policy)
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {"id": "WORK-1", "status": "IN_REVIEW", "owner": "tobianahillel-afk", "assurance": {"level": "A3"}},
    )
    risk = {
        "id": "RISK-1",
        "status": "ACCEPTED",
        "category": "ENGINEERING",
        "scope": {"work_items": ["WORK-1"]},
        "assessment": {"impact": "HIGH"},
        "resolution": {
            "accepted": True,
            "accepted_by": "tobianahillel-afk",
            "authority_role": "REPOSITORY_OWNER",
            "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION",
            "authority_evidence_ref": "https://api.github.com/repos/tobianahillel-afk/monde",
            "authority_matrix_version": 1,
            "authority_rule_id": "RISK_DEFAULT:A3:HIGH",
            "acceptance_rationale": "bounded residual risk",
            "accepted_at": "2026-09-14",
            "review_condition": "review on scope change",
        },
    }
    dump(tmp_path / "registry/risks/RISK-1.yaml", risk)
    head = commit(tmp_path, "risk")
    assert cg.risk_acceptance_satisfied(tmp_path, head, risk)
    risk["scope"]["work_items"] = ["WORK-1", "WORK-2"]
    assert not cg.risk_acceptance_satisfied(tmp_path, head, risk)


def test_closed_review_never_satisfies_done_completion(tmp_path: Path) -> None:
    dump(
        tmp_path / "registry/reviews/REVIEW-1.yaml",
        {
            "id": "REVIEW-1",
            "status": "CLOSED",
            "outcome": "APPROVE",
            "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-1", "commit_sha": "a" * 40},
            "scope": {"work_items": ["WORK-1"]},
        },
    )
    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "DONE",
            "depends_on": [],
            "review_plan": {"independence_level": "L0", "completed_reviews": ["REVIEW-1"]},
            "required_tests": {},
            "completion": {"specification_gates_checked": True},
        },
    )
    assert "DONE_REVIEW_STATE" in {issue.rule for issue in validate_work_lifecycle(tmp_path)}
