from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import tools.governance.proof_contracts as pc


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True).stdout.strip()


def init_git(root: Path) -> str:
    git(root, "init")
    git(root, "config", "user.email", "proof@example.invalid")
    git(root, "config", "user.name", "proof")
    (root / "x").write_text("1", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    return git(root, "rev-parse", "HEAD")


def test_mapping_and_git_helpers_cover_failure_and_success(tmp_path: Path) -> None:
    assert pc.load_mapping(tmp_path / "missing.yaml") == {}
    (tmp_path / "list.yaml").write_text("- x\n", encoding="utf-8")
    assert pc.load_mapping(tmp_path / "list.yaml") == {}
    (tmp_path / "ok.yaml").write_text("a: 1\n", encoding="utf-8")
    assert pc.load_mapping(tmp_path / "ok.yaml") == {"a": 1}

    assert not pc.git_commit_exists(tmp_path, "short")
    base = init_git(tmp_path)
    assert pc.git_commit_exists(tmp_path, base)
    assert pc.current_head(tmp_path) == base
    assert pc.git_commit_is_ancestor(tmp_path, base, base)
    assert not pc.git_commit_is_ancestor(tmp_path, "f" * 40, base)

    test = {"execution": {"commit_sha": base}}
    assert pc.pass_test_execution_revision_valid(tmp_path, test)
    assert not pc.pass_test_execution_revision_valid(tmp_path, {"execution": {"commit_sha": "f" * 40}})
    assert pc.current_head(tmp_path / "not-a-repo") is None


def test_nested_projection_and_digest_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = {"a": {"b": 1}, "flat": 2}
    target: dict = {}
    assert pc._copy_nested_path(source, target, "a.b")
    assert target == {"a": {"b": 1}}
    assert not pc._copy_nested_path(source, {}, "a.missing")
    assert not pc._copy_nested_path(source, {}, "missing.x")
    assert not pc._copy_nested_path(source, {"a": "collision"}, "a.b")

    req = {"id": "REQ-1"}
    assert pc.requirement_normative_digest(tmp_path, req, {"schemes": {}}) is None
    assert pc.requirement_normative_digest(tmp_path, req, {"schemes": {"REQUIREMENT_NORMATIVE_V1": {"algorithm": "MD5"}}}) is None
    policy = {"schemes": {"REQUIREMENT_NORMATIVE_V1": {"algorithm": "SHA256", "canonicalization": {"standard": "wrong"}, "included_fields": ["id"]}}}
    assert pc.requirement_normative_digest(tmp_path, req, policy) is None
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["canonicalization"]["standard"] = "RFC_8785_JSON_CANONICALIZATION_SCHEME"
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["included_fields"] = []
    assert pc.requirement_normative_digest(tmp_path, req, policy) is None
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["included_fields"] = [42]
    assert pc.requirement_normative_digest(tmp_path, req, policy) is None
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["included_fields"] = ["missing"]
    assert pc.requirement_normative_digest(tmp_path, req, policy) is None
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["included_fields"] = ["id"]
    assert pc.requirement_normative_digest(tmp_path, req, policy).startswith("sha256:")

    def explode(value: object) -> bytes:
        raise ValueError("bad canonical value")

    monkeypatch.setattr(pc.rfc8785, "dumps", explode)
    assert pc.requirement_normative_digest(tmp_path, req, policy) is None


def test_owner_evidence_all_required_bindings() -> None:
    policy = {"governed_repository": {"full_name": "owner/repo", "owner_login": "owner", "metadata_url": "https://api.github.com/repos/owner/repo", "permission_proof": "TEST-1"}}
    good = {"authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION", "authority_evidence_ref": "https://api.github.com/repos/owner/repo", "accepted_by": "owner"}
    assert pc.repository_owner_evidence_valid(good, policy)
    for key, value in (
        ("authority_evidence_type", "OTHER"),
        ("authority_evidence_ref", "https://api.github.com/repos/owner/other"),
        ("accepted_by", "other"),
    ):
        bad = dict(good); bad[key] = value
        assert not pc.repository_owner_evidence_valid(bad, policy)
    for field, value in (("full_name", None), ("full_name", ""), ("permission_proof", None), ("permission_proof", "")):
        bad_policy = {"governed_repository": dict(policy["governed_repository"])}
        bad_policy["governed_repository"][field] = value
        assert not pc.repository_owner_evidence_valid(good, bad_policy)


def test_external_review_finalization_branches() -> None:
    assert pc.review_external_import_finalized({}, {})
    assert not pc.review_external_import_finalized({"external_import": "bad"}, {})
    assert not pc.review_external_import_finalized({"external_import": {"mode": "OTHER"}}, {})
    review = {"id": "REVIEW-1", "status": "COMPLETE", "outcome": "APPROVE", "artifact": {"commit_sha": "b" * 40}, "reviewer": {"context_id": "ctx"}, "external_import": {"mode": "PREAUTHORIZED_EXTERNAL_COMPLETION", "authorization_commit": "c" * 40, "source_review_id": "SRC", "import_commit": "short"}}
    assert not pc.review_external_import_finalized(review, {})
    review["external_import"]["import_commit"] = "a" * 40
    machine = {"registry_machines": {"reviews": {"external_import_authorizations": ["bad", {"record_id": "OTHER"}]}}}
    assert not pc.review_external_import_finalized(review, machine)
    machine["registry_machines"]["reviews"]["external_import_authorizations"].append({"record_id": "REVIEW-1", "imported_status": "COMPLETE", "artifact_commit_sha": "b" * 40, "source_review_id": "SRC", "reviewer_context_id": "ctx", "expected_outcome": "APPROVE", "one_shot": True, "consumed_by_commit": "a" * 40})
    assert pc.review_external_import_finalized(review, machine)


def test_risk_rule_resolution_fail_closed_and_override() -> None:
    policy = {
        "vocabulary": {"assurance_levels": ["A3"], "risk_categories": ["ENGINEERING", "SECURITY"], "risk_impacts": ["HIGH"]},
        "risk_acceptance": {
            "default_matrix": {"A3": {"HIGH": ["REPOSITORY_OWNER"]}},
            "category_overrides": {"SECURITY": {"A3": {"HIGH": ["DESIGNATED_SECURITY_AUTHORITY"]}}},
        },
    }
    work = {"assurance": {"level": "A3"}}
    loader = lambda path: work
    base = {"scope": {"work_items": ["WORK-1"]}, "category": "ENGINEERING", "assessment": {"impact": "HIGH"}}
    assert pc.resolve_risk_authority_rule(Path("."), base, policy, loader) == ("RISK_DEFAULT:A3:HIGH", ["REPOSITORY_OWNER"])
    override = {**base, "category": "SECURITY"}
    assert pc.resolve_risk_authority_rule(Path("."), override, policy, loader) == ("RISK_CATEGORY:SECURITY:A3:HIGH", ["DESIGNATED_SECURITY_AUTHORITY"])
    assert pc.resolve_risk_authority_rule(Path("."), {**base, "scope": {"work_items": []}}, policy, loader) is None
    assert pc.resolve_risk_authority_rule(Path("."), {**base, "scope": {"work_items": ["A", "B"]}}, policy, loader) is None
    assert pc.resolve_risk_authority_rule(Path("."), base, policy, lambda path: None) is None
    assert pc.resolve_risk_authority_rule(Path("."), base, policy, lambda path: {"assurance": {"level": "A9"}}) is None
    assert pc.resolve_risk_authority_rule(Path("."), {**base, "category": "UNKNOWN"}, policy, loader) is None
    assert pc.resolve_risk_authority_rule(Path("."), {**base, "assessment": {"impact": "LOW"}}, policy, loader) is None
    no_rule = {"vocabulary": policy["vocabulary"], "risk_acceptance": {"default_matrix": {}, "category_overrides": {}}}
    assert pc.resolve_risk_authority_rule(Path("."), base, no_rule, loader) is None
