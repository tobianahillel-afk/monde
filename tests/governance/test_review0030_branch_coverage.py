from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.change_guard as cg
from tools.governance.proof_contracts import requirement_normative_digest
from tools.governance.strict_contracts import pass_test_revision_valid, validate_work_lifecycle
from tools.governance.validate_repo import Record, Validator


def risk_policy() -> dict:
    return {
        "version": 1,
        "governed_repository": {
            "full_name": "owner/repo",
            "owner_login": "owner",
            "metadata_url": "https://api.github.com/repos/owner/repo",
            "permission_proof": "TEST-1",
        },
        "vocabulary": {
            "assurance_levels": ["A1", "A3"],
            "risk_categories": ["ENGINEERING"],
            "risk_impacts": ["LOW", "MEDIUM", "HIGH"],
            "authority_roles": {
                "WORK_OWNER": {"allowed_evidence_types": ["WORK_ITEM_OWNER_BINDING"]},
                "DESIGNATED_RISK_AUTHORITY": {"allowed_evidence_types": ["GOVERNANCE_DELEGATION"]},
                "REPOSITORY_OWNER": {"allowed_evidence_types": ["GITHUB_REPOSITORY_OWNER_PERMISSION"]},
            },
        },
        "risk_acceptance": {
            "default_matrix": {
                "A1": {"LOW": ["WORK_OWNER", "REPOSITORY_OWNER"]},
                "A3": {"MEDIUM": ["DESIGNATED_RISK_AUTHORITY", "REPOSITORY_OWNER"], "HIGH": ["REPOSITORY_OWNER"]},
            },
            "category_overrides": {},
        },
    }


def risk_spec() -> dict:
    return {
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
    }


def base_risk() -> dict:
    return {
        "id": "RISK-1",
        "category": "ENGINEERING",
        "scope": {"work_items": ["WORK-1"]},
        "assessment": {"impact": "HIGH"},
        "resolution": {
            "accepted": True,
            "accepted_by": "owner",
            "authority_role": "REPOSITORY_OWNER",
            "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION",
            "authority_evidence_ref": "https://api.github.com/repos/owner/repo",
            "authority_matrix_version": 1,
            "authority_rule_id": "RISK_DEFAULT:A3:HIGH",
            "acceptance_rationale": "bounded",
            "accepted_at": "2026-09-14",
            "review_condition": "scope change",
        },
    }


def records_for(risk: dict, *, assurance: str = "A3", owner: str = "owner", delegation: dict | None = None) -> dict:
    records = {
        "registry/status-machines.yaml": risk_spec(),
        "registry/acceptance-authority.yaml": risk_policy(),
        "registry/work-items/WORK-1.yaml": {"id": "WORK-1", "owner": owner, "assurance": {"level": assurance}},
    }
    if delegation is not None:
        records["registry/delegation.yaml"] = delegation
    return records


def evaluate(monkeypatch, tmp_path: Path, risk: dict, records: dict) -> bool:
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: records.get(path))
    return cg.risk_acceptance_satisfied(tmp_path, "sha", risk)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init_git(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "review0030-coverage@example.invalid")
    git(root, "config", "user.name", "review0030-coverage")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_risk_acceptance_preconditions_fail_closed(monkeypatch, tmp_path: Path) -> None:
    risk = base_risk()
    records = records_for(risk)
    bad = dict(risk); bad["resolution"] = "bad"
    assert not evaluate(monkeypatch, tmp_path, bad, records)
    bad = base_risk(); bad["resolution"]["accepted"] = False
    assert not evaluate(monkeypatch, tmp_path, bad, records)

    malformed_spec = records_for(risk)
    malformed_spec["registry/status-machines.yaml"]["registry_machines"]["risks"]["acceptance_preconditions"]["required_fields"] = ["bad"]
    assert not evaluate(monkeypatch, tmp_path, risk, malformed_spec)

    missing = base_risk(); missing["resolution"]["accepted_at"] = None
    assert not evaluate(monkeypatch, tmp_path, missing, records)

    ambiguous = base_risk(); ambiguous["scope"]["work_items"] = ["WORK-1", "WORK-2"]
    assert not evaluate(monkeypatch, tmp_path, ambiguous, records)


def test_risk_owner_role_rule_and_version_checks(monkeypatch, tmp_path: Path) -> None:
    risk = base_risk()
    records = records_for(risk)
    assert evaluate(monkeypatch, tmp_path, risk, records)

    bad_role = base_risk(); bad_role["resolution"]["authority_role"] = "WORK_OWNER"; bad_role["resolution"]["authority_evidence_type"] = "WORK_ITEM_OWNER_BINDING"
    assert not evaluate(monkeypatch, tmp_path, bad_role, records)

    bad_version = base_risk(); bad_version["resolution"]["authority_matrix_version"] = 2
    assert not evaluate(monkeypatch, tmp_path, bad_version, records)

    bad_rule = base_risk(); bad_rule["resolution"]["authority_rule_id"] = "RISK_DEFAULT:A3:MEDIUM"
    assert not evaluate(monkeypatch, tmp_path, bad_rule, records)


def test_risk_work_owner_and_delegation_evidence(monkeypatch, tmp_path: Path) -> None:
    work_owner = base_risk()
    work_owner["assessment"]["impact"] = "LOW"
    work_owner["resolution"].update({
        "accepted_by": "alice",
        "authority_role": "WORK_OWNER",
        "authority_evidence_type": "WORK_ITEM_OWNER_BINDING",
        "authority_evidence_ref": "registry/work-items/WORK-1.yaml",
        "authority_rule_id": "RISK_DEFAULT:A1:LOW",
    })
    records = records_for(work_owner, assurance="A1", owner="alice")
    assert evaluate(monkeypatch, tmp_path, work_owner, records)
    work_owner["resolution"]["authority_evidence_ref"] = "registry/work-items/OTHER.yaml"
    assert not evaluate(monkeypatch, tmp_path, work_owner, records)
    work_owner["resolution"]["authority_evidence_ref"] = "registry/work-items/WORK-1.yaml"
    records["registry/work-items/WORK-1.yaml"]["owner"] = "bob"
    assert not evaluate(monkeypatch, tmp_path, work_owner, records)

    delegated = base_risk()
    delegated["assessment"]["impact"] = "MEDIUM"
    delegated["resolution"].update({
        "accepted_by": "delegate",
        "authority_role": "DESIGNATED_RISK_AUTHORITY",
        "authority_evidence_type": "GOVERNANCE_DELEGATION",
        "authority_evidence_ref": "registry/delegation.yaml",
        "authority_rule_id": "RISK_DEFAULT:A3:MEDIUM",
    })
    records = records_for(delegated, delegation={"delegate": "delegate"})
    assert evaluate(monkeypatch, tmp_path, delegated, records)
    delegated["resolution"]["authority_evidence_ref"] = "https://example.invalid/delegation"
    assert not evaluate(monkeypatch, tmp_path, delegated, records)
    delegated["resolution"]["authority_evidence_ref"] = "registry/delegation.yaml"
    records["registry/delegation.yaml"] = {"delegate": "someone-else"}
    assert not evaluate(monkeypatch, tmp_path, delegated, records)

    delegated["resolution"]["authority_evidence_type"] = "UNKNOWN"
    assert not evaluate(monkeypatch, tmp_path, delegated, records)

    unsupported = base_risk()
    unsupported["resolution"]["authority_evidence_type"] = "CUSTOM_EVIDENCE"
    records = records_for(unsupported)
    records["registry/acceptance-authority.yaml"]["vocabulary"]["authority_roles"]["REPOSITORY_OWNER"]["allowed_evidence_types"] = ["CUSTOM_EVIDENCE"]
    assert not evaluate(monkeypatch, tmp_path, unsupported, records)


def test_requirement_acceptance_without_cold_read_fails_closed(monkeypatch, tmp_path: Path) -> None:
    identity = {
        "schemes": {
            "REQUIREMENT_NORMATIVE_V1": {
                "algorithm": "SHA256",
                "canonicalization": {"standard": "RFC_8785_JSON_CANONICALIZATION_SCHEME"},
                "included_fields": ["id"],
            }
        }
    }
    requirement = {"id": "REQ-1"}
    digest = requirement_normative_digest(tmp_path, requirement, identity)
    assert digest is not None
    requirement["content_identity"] = {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": digest}
    requirement["verification"] = {"acceptance_evidence": [], "acceptance_cold_read_test_ids": []}
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: identity if path == "registry/content-identity.yaml" else None)
    assert not cg.requirement_acceptance_satisfied(tmp_path, "head", requirement)


def test_change_guard_reports_invalid_risk_acceptance_transition(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / cg.GUARD_PATH).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / cg.GUARD_PATH).write_text("guard\n", encoding="utf-8")
    dump(
        tmp_path / "registry/status-machines.yaml",
        {
            "registry_machines": {
                "risks": {
                    "initial": "OPEN",
                    "transitions": {"OPEN": ["ACCEPTED"], "ACCEPTED": []},
                    "acceptance_preconditions": {"required_fields": ["resolution.accepted"]},
                }
            }
        },
    )
    risk = {
        "id": "RISK-1",
        "status": "OPEN",
        "category": "ENGINEERING",
        "scope": {"work_items": ["WORK-1"]},
        "assessment": {"impact": "HIGH"},
        "resolution": {"accepted": False},
    }
    dump(tmp_path / "registry/risks/RISK-1.yaml", risk)
    base = commit(tmp_path, "open risk")
    risk["status"] = "ACCEPTED"
    dump(tmp_path / "registry/risks/RISK-1.yaml", risk)
    head = commit(tmp_path, "accept risk without authority")
    assert "RISK_ACCEPTANCE_PRECONDITION" in {finding.rule for finding in cg.validate(tmp_path, base, head)}


def test_strict_review_sha_and_revision_branches(tmp_path: Path) -> None:
    init_git(tmp_path)
    (tmp_path / "proof.txt").write_text("proof", encoding="utf-8")
    tested = commit(tmp_path, "tested revision")
    assert pass_test_revision_valid(tmp_path, {"execution": {"commit_sha": tested}})

    dump(
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "status": "DONE",
            "depends_on": [],
            "review_plan": {"completed_reviews": ["REVIEW-1"]},
            "required_tests": {},
            "completion": {"specification_gates_checked": True},
        },
    )
    dump(
        tmp_path / "registry/reviews/REVIEW-1.yaml",
        {
            "id": "REVIEW-1",
            "status": "COMPLETE",
            "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-1", "commit_sha": "short"},
            "scope": {"work_items": ["WORK-1"]},
        },
    )
    assert "DONE_REVIEW_SHA" in {issue.rule for issue in validate_work_lifecycle(tmp_path)}


def test_validate_repo_reports_unresolved_blocking_review_finding(tmp_path: Path) -> None:
    validator = Validator(tmp_path)
    work = Record(
        "work-items",
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "review_plan": {"required_hats": [], "independence_level": "L0", "completed_reviews": ["REVIEW-1"]},
        },
    )
    review = Record(
        "reviews",
        tmp_path / "registry/reviews/REVIEW-1.yaml",
        {
            "id": "REVIEW-1",
            "status": "COMPLETE",
            "outcome": "APPROVE",
            "roles": [],
            "reviewer": {"independence_level": "L0"},
            "findings": [{"id": "F-1", "severity": "R2_MAJOR", "disposition": "OPEN"}],
        },
    )
    validator.by_id = {"REVIEW-1": review}
    validator.validate_review_evidence(work)
    assert any("retains blocking finding F-1" in issue.message for issue in validator.issues)


def test_duplicate_yaml_unhashable_key_is_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "record.yaml"
    path.write_text("? [a, b]\n: value\n", encoding="utf-8")
    validator = Validator(tmp_path)
    assert validator.load_yaml(path) is None
    assert validator.issues and validator.issues[0].rule == "YAML_PARSE"
