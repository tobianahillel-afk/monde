from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    assert count == 1, (path, count, old[:160])
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1) Existing authority regression now supplies the exact governed-repository permission resource.
replace_once(
    "tests/governance/test_final_l2_findings.py",
    '''def test_blocking_accepted_finding_requires_matrix_authority(tmp_path: Path) -> None:\n    policy = yaml.safe_load(Path("registry/acceptance-authority.yaml").read_text(encoding="utf-8"))\n''',
    '''def test_blocking_accepted_finding_requires_matrix_authority(tmp_path: Path) -> None:\n    git(tmp_path, "init")\n    git(tmp_path, "remote", "add", "origin", "https://github.com/owner/repo.git")\n    policy = yaml.safe_load(Path("registry/acceptance-authority.yaml").read_text(encoding="utf-8"))\n''',
)
replace_once(
    "tests/governance/test_final_l2_findings.py",
    '''"authority_evidence_ref": "https://api.github.com/repos/owner/repo"''',
    '''"authority_evidence_ref": "https://api.github.com/repos/owner/repo/collaborators/owner/permission"''',
)

# 2) This older acceptance test isolates evidence selection; digest recomputation is covered separately.
replace_once(
    "tests/governance/test_review0029_branches.py",
    '''def test_acceptance_cold_read_skips_failed_candidate_before_good_one(monkeypatch, tmp_path: Path) -> None:\n    digest = 'sha256:' + 'a' * 64\n''',
    '''def test_acceptance_cold_read_skips_failed_candidate_before_good_one(monkeypatch, tmp_path: Path) -> None:\n    monkeypatch.setattr(cg, "requirement_digest_matches", lambda *args: True)\n    digest = 'sha256:' + 'a' * 64\n''',
)

# 3) Keep the strict binding/evidence regression focused while acknowledging status is now part of the contract.
replace_once(
    "tests/governance/test_strict_contracts.py",
    '''def test_done_review_binding_and_test_evidence(tmp_path: Path) -> None:\n    root = repo(tmp_path)\n''',
    '''def test_done_review_binding_and_test_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:\n    root = repo(tmp_path)\n    import tools.governance.strict_contracts as sc\n    monkeypatch.setattr(sc, "git_commit_reachable", lambda *args: True)\n''',
)
replace_once(
    "tests/governance/test_strict_contracts.py",
    '''    assert issue_rules(validate_work_lifecycle(root)) == {"DONE_REVIEW_SCOPE", "DONE_TEST_EVIDENCE"}\n\n    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "scope": {"work_items": ["WORK-0002"]}})\n''',
    '''    assert issue_rules(validate_work_lifecycle(root)) == {"DONE_REVIEW_STATUS", "DONE_REVIEW_SCOPE", "DONE_TEST_EVIDENCE"}\n\n    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "status": "COMPLETE", "artifact": {"commit_sha": "0" * 40}, "scope": {"work_items": ["WORK-0002"]}})\n''',
)
replace_once(
    "tests/governance/test_strict_contracts.py",
    '''    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-0002"}})\n''',
    '''    dump(root / "registry/reviews/REVIEW-0001.yaml", {"id": "REVIEW-0001", "status": "COMPLETE", "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-0002", "commit_sha": "0" * 40}})\n''',
)

# 4) A non-COMPLETE review is excluded from hats and independence as well as rejected directly.
replace_once(
    "tests/governance/test_validate_repo_coverage.py",
    '''    assert [x.message for x in v.issues] == ["review REVIEW-1 is not complete"]\n''',
    '''    assert [x.message for x in v.issues] == [\n        "review REVIEW-1 is not COMPLETE approval evidence",\n        "completed reviews miss required hats ['SECURITY']",\n        "no completed review satisfies independence L2_TARGET",\n    ]\n''',
)

# Add explicit branch coverage for the new fail-closed helpers.
p = Path("tests/governance/test_review0030_findings.py")
text = p.read_text(encoding="utf-8")
append = r'''

import tools.governance.strict_contracts as sc


def test_jcs_complete_type_and_error_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    assert cg.jcs_serialize(None) == "null"
    assert cg.jcs_serialize(True) == "true"
    assert cg.jcs_serialize(False) == "false"
    assert cg.jcs_serialize("x") == '"x"'
    assert cg.jcs_serialize(12) == "12"
    assert cg.jcs_serialize([1, "x", None]) == '[1,"x",null]'
    assert cg.jcs_serialize({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert cg._ecmascript_number(1.0) == "1"
    assert cg._ecmascript_number(1.23e3) == "1230"
    assert cg._ecmascript_number(1.23e-5) == "0.0000123"
    assert cg._ecmascript_number(-1.23e30) == "-1.23e+30"
    with pytest.raises(ValueError):
        cg._ecmascript_number(True)
    with pytest.raises(ValueError):
        cg.jcs_serialize({1: "bad"})
    with pytest.raises(ValueError):
        cg.jcs_serialize({"\ud800": "bad"})
    with pytest.raises(ValueError):
        cg.jcs_serialize({1, 2})

    real_repr = __import__("builtins").repr
    monkeypatch.setattr("builtins.repr", lambda value: "x" if isinstance(value, float) else real_repr(value))
    with pytest.raises(ValueError):
        cg._ecmascript_number(1.5)


def test_requirement_projection_and_policy_fail_closed(tmp_path: Path) -> None:
    base = init_git(tmp_path)
    req = {
        "id": "REQ-1",
        "title": "T",
        "normative_statement": "N",
        "scope": {"in": ["x"], "out": []},
        "verification": {"method": "m"},
        "content_identity": {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": "sha256:" + "0" * 64},
    }
    with pytest.raises(ValueError):
        cg.requirement_normative_projection(req, {"included_fields": []})
    with pytest.raises(ValueError):
        cg.requirement_normative_projection(req, {"included_fields": [7]})
    with pytest.raises(ValueError):
        cg.requirement_normative_projection(req, {"included_fields": ["missing.path"]})
    with pytest.raises(ValueError):
        cg.requirement_normative_projection(
            {**req, "scope": {"in": ["x"]}},
            {"included_fields": ["scope.in", "scope.in.value"]},
        )

    dump(tmp_path / "registry/content-identity.yaml", content_identity_policy())
    commit(tmp_path, "identity policy")
    assert cg.recompute_requirement_digest(tmp_path, "HEAD", {**req, "content_identity": {"scheme": "OTHER"}}) is None

    for key, value in [
        ("algorithm", "SHA1"),
        ("encoding", "UTF-16"),
    ]:
        policy = content_identity_policy()
        policy["schemes"]["REQUIREMENT_NORMATIVE_V1"][key] = value
        dump(tmp_path / "registry/content-identity.yaml", policy)
        commit(tmp_path, f"bad {key}")
        assert cg.recompute_requirement_digest(tmp_path, "HEAD", req) is None

    policy = content_identity_policy()
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["canonicalization"]["standard"] = "OTHER"
    dump(tmp_path / "registry/content-identity.yaml", policy)
    commit(tmp_path, "bad canonical standard")
    assert cg.recompute_requirement_digest(tmp_path, "HEAD", req) is None

    policy = content_identity_policy()
    policy["schemes"]["REQUIREMENT_NORMATIVE_V1"]["canonicalization"]["encoding"] = "UTF-16"
    dump(tmp_path / "registry/content-identity.yaml", policy)
    commit(tmp_path, "bad canonical encoding")
    assert cg.recompute_requirement_digest(tmp_path, "HEAD", req) is None


def test_governed_repository_slug_variants_and_authority_types(tmp_path: Path) -> None:
    assert cg.governed_repository_slug(tmp_path) is None
    assert sc.governed_repository_slug(tmp_path) is None

    init_git(tmp_path, "git@github.com:owner/repo.git")
    assert cg.governed_repository_slug(tmp_path) == ("owner", "repo")
    assert sc.governed_repository_slug(tmp_path) == ("owner", "repo")

    git(tmp_path, "remote", "set-url", "origin", "ssh://git@github.com/acme/project.git")
    assert cg.governed_repository_slug(tmp_path) == ("acme", "project")
    assert sc.governed_repository_slug(tmp_path) == ("acme", "project")

    git(tmp_path, "remote", "set-url", "origin", "https://example.com/acme/project.git")
    assert cg.governed_repository_slug(tmp_path) is None
    assert sc.governed_repository_slug(tmp_path) is None

    git(tmp_path, "remote", "set-url", "origin", "https://github.com/too/many/parts.git")
    assert cg.governed_repository_slug(tmp_path) is None
    assert sc.governed_repository_slug(tmp_path) is None

    git(tmp_path, "remote", "set-url", "origin", "https://github.com/owner/repo.git")
    dump(tmp_path / "registry/work-items/W.yaml", {"id": "W"})
    dump(tmp_path / "registry/delegation.yaml", {"ok": True})
    commit(tmp_path, "authority refs")
    assert cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "WORK_ITEM_OWNER_BINDING", "registry/work-items/W.yaml")
    assert not cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "WORK_ITEM_OWNER_BINDING", "registry/work-items/missing.yaml")
    assert cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "GOVERNANCE_DELEGATION", "registry/delegation.yaml")
    assert cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "GOVERNANCE_SECURITY_DELEGATION", "registry/delegation.yaml")
    assert cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "EXPLICIT_REPOSITORY_OWNER_DECISION", "registry/delegation.yaml")
    assert not cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "GOVERNANCE_DELEGATION", "docs/no.yaml")
    assert not cg.authority_evidence_valid_at(tmp_path, "HEAD", "owner", "UNKNOWN", "registry/delegation.yaml")


def test_risk_acceptance_fail_closed_branches(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/status-machines.yaml", risk_machine())
    dump(tmp_path / "registry/acceptance-authority.yaml", authority_policy())
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "assurance": {"level": "A3"}})
    dump(tmp_path / "registry/work-items/WORK-2.yaml", {"id": "WORK-2", "assurance": {"level": "A2"}})
    sha = commit(tmp_path, "risk policy")
    ref = "https://api.github.com/repos/owner/repo/collaborators/owner/permission"
    good = accepted_risk(ref)

    machine = risk_machine()
    machine["registry_machines"]["risks"]["acceptance_preconditions"]["required_fields"] = []
    dump(tmp_path / "registry/status-machines.yaml", machine)
    sha = commit(tmp_path, "missing contract")
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, good)

    dump(tmp_path / "registry/status-machines.yaml", risk_machine())
    sha = commit(tmp_path, "restore contract")
    not_accepted = yaml.safe_load(yaml.safe_dump(good)); not_accepted["resolution"]["accepted"] = False
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, not_accepted)
    no_scope = yaml.safe_load(yaml.safe_dump(good)); no_scope["scope"]["work_items"] = []
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, no_scope)
    bad_scope = yaml.safe_load(yaml.safe_dump(good)); bad_scope["scope"]["work_items"] = [7]
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_scope)
    bad_work = yaml.safe_load(yaml.safe_dump(good)); bad_work["scope"]["work_items"] = ["WORK-X"]
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_work)

    dump(tmp_path / "registry/work-items/WORK-X.yaml", {"id": "WORK-X", "assurance": {"level": "AX"}})
    sha = commit(tmp_path, "bad assurance")
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_work)

    default_policy = authority_policy()
    default_policy["risk_acceptance"]["category_overrides"] = {}
    dump(tmp_path / "registry/acceptance-authority.yaml", default_policy)
    default_risk = yaml.safe_load(yaml.safe_dump(good))
    default_risk["category"] = "OPERATIONS"
    default_risk["resolution"]["authority_rule_id"] = "RISK_DEFAULT:A3:HIGH"
    sha = commit(tmp_path, "default matrix")
    assert cg.risk_acceptance_satisfied(tmp_path, sha, default_risk)

    bad_role = yaml.safe_load(yaml.safe_dump(default_risk)); bad_role["resolution"]["authority_role"] = "NOPE"
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_role)
    bad_type = yaml.safe_load(yaml.safe_dump(default_risk)); bad_type["resolution"]["authority_evidence_type"] = "NOPE"
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_type)
    bad_version = yaml.safe_load(yaml.safe_dump(default_risk)); bad_version["resolution"]["authority_matrix_version"] = 2
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, bad_version)


def test_git_commit_reachability_all_paths(tmp_path: Path) -> None:
    base = init_git(tmp_path)
    assert not sc.git_commit_exists(tmp_path, "short")
    assert sc.git_commit_exists(tmp_path, base)
    assert sc.git_commit_reachable(tmp_path, base)

    git(tmp_path, "checkout", "-b", "side")
    (tmp_path / "side.txt").write_text("side\n", encoding="utf-8")
    side = commit(tmp_path, "side")
    git(tmp_path, "checkout", "master")
    assert sc.git_commit_reachable(tmp_path, side)

    fake = "f" * 40
    assert not sc.git_commit_exists(tmp_path, fake)
    assert not sc.git_commit_reachable(tmp_path, fake)


def test_external_review_import_finalization_fail_closed_surface(tmp_path: Path) -> None:
    init_git(tmp_path)
    base_review = {"status": "COMPLETE", "artifact": {"commit_sha": "c" * 40}, "reviewer": {"context_id": "ctx"}, "outcome": "APPROVE"}
    assert sc.external_review_import_finalized(tmp_path, "R", base_review)
    assert not sc.external_review_import_finalized(tmp_path, "R", {**base_review, "external_import": "bad"})
    assert not sc.external_review_import_finalized(tmp_path, "R", {**base_review, "external_import": {"mode": "OTHER"}})
    short = {**base_review, "external_import": {"mode": "PREAUTHORIZED_EXTERNAL_COMPLETION", "import_commit": "short", "authorization_commit": "b" * 40}}
    assert not sc.external_review_import_finalized(tmp_path, "R", short)

    ext = {
        "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
        "authorization_commit": "b" * 40,
        "source_review_id": "SRC",
        "source_submitted_at": "2026-09-14T00:00:00Z",
        "import_commit": "a" * 40,
    }
    review = {**base_review, "external_import": ext}
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": ["bad", {"record_id": "OTHER"}]}}})
    assert not sc.external_review_import_finalized(tmp_path, "R", review)


def test_pass_test_execution_rejects_each_incomplete_dimension(tmp_path: Path) -> None:
    sha = init_git(tmp_path)
    base = {"status": "PASS", "execution": {"command_or_workflow": "pytest", "commit_sha": sha, "result": "PASS", "evidence": ["ci"]}}
    assert sc.pass_test_has_execution(tmp_path, base)
    for mutation in [
        {"status": "FAIL"},
        {"execution": "bad"},
        {"execution": {"command_or_workflow": "pytest", "commit_sha": sha, "result": "FAIL", "evidence": ["ci"]}},
        {"execution": {"command_or_workflow": "pytest", "commit_sha": "short", "result": "PASS", "evidence": ["ci"]}},
        {"execution": {"command_or_workflow": "pytest", "commit_sha": sha, "result": "PASS", "evidence": []}},
        {"execution": {"command_or_workflow": "", "commit_sha": sha, "result": "PASS", "evidence": ["ci"]}},
    ]:
        candidate = yaml.safe_load(yaml.safe_dump(base))
        candidate.update(mutation)
        assert not sc.pass_test_has_execution(tmp_path, candidate)
'''
assert "test_jcs_complete_type_and_error_surface" not in text
p.write_text(text + append, encoding="utf-8")
print("REVIEW-0030 test compatibility and coverage hotfix applied")
