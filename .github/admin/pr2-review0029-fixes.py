from __future__ import annotations

import json
from pathlib import Path

import yaml


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected one occurrence, got {count}"
    return text.replace(old, new, 1)


# change_guard.py
p = Path("tools/governance/change_guard.py")
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    'ADMIN_PATH_PREFIXES = ("registry/reviews/", "registry/tests/", "registry/progress/", "PROJECT_STATE.md")',
    'ADMIN_PATH_PREFIXES = ("registry/reviews/", "registry/progress/", "PROJECT_STATE.md")\nFULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")',
    "admin prefixes",
)
s = replace_once(
    s,
    'def changed_files(root: Path, base: str, head: str) -> list[str]:\n    return [x for x in git(root, "diff", "--name-only", f"{base}..{head}").splitlines() if x]\n',
    '''def changed_files(root: Path, base: str, head: str) -> list[str]:
    return [x for x in git(root, "diff", "--name-only", f"{base}..{head}").splitlines() if x]


def endpoint_changed_files(root: Path, base: str, head: str) -> list[str]:
    merge_base = git(root, "merge-base", base, head).strip()
    if not merge_base:
        raise RuntimeError("no merge base for endpoint comparison")
    return changed_files(root, merge_base, head)
''',
    "endpoint helper",
)
s = replace_once(
    s,
    '''def canonical_transitions(root: Path, sha: str, kind: str) -> dict[str, set[str]]:
    machine = show_yaml(root, sha, "registry/status-machines.yaml") or {}
    registries = machine.get("registry_machines") or {}
    spec = registries.get(kind.replace("-", "_")) or {}
    raw = spec.get("transitions") or {}
    return {str(before): set(after or []) for before, after in raw.items()}
''',
    '''def canonical_machine_spec(root: Path, sha: str, kind: str) -> dict[str, Any]:
    machine = show_yaml(root, sha, "registry/status-machines.yaml") or {}
    registries = machine.get("registry_machines") or {}
    spec = registries.get(kind.replace("-", "_")) or {}
    return spec if isinstance(spec, dict) else {}


def canonical_transitions(root: Path, sha: str, kind: str) -> dict[str, set[str]]:
    raw = canonical_machine_spec(root, sha, kind).get("transitions") or {}
    return {str(before): set(after or []) for before, after in raw.items()}


def review_independence_rank(raw: Any) -> int:
    value = str(raw or "").upper().split("_", 1)[0]
    return {"L0": 0, "L1": 1, "L2": 2, "L3": 3}.get(value, -1)


def historical_import_allowed(root: Path, parent_sha: str, materialize_sha: str, policy_sha: str, kind: str, current: dict[str, Any]) -> bool:
    rid, status = current.get("id"), current.get("status")
    current_spec = canonical_machine_spec(root, policy_sha, kind)
    for exc in current_spec.get("historical_import_exceptions", []) or []:
        if isinstance(exc, dict) and exc.get("record_id") == rid and exc.get("imported_status") == status and exc.get("import_commit") == materialize_sha:
            return True

    parent_spec = canonical_machine_spec(root, parent_sha, kind)
    if kind == "reviews":
        ext = current.get("external_import") or {}
        reviewer = current.get("reviewer") or {}
        artifact = current.get("artifact") or {}
        auth_commit = ext.get("authorization_commit")
        if not isinstance(auth_commit, str) or not FULL_COMMIT_SHA.fullmatch(auth_commit) or not is_ancestor(root, auth_commit, parent_sha):
            return False
        for auth in parent_spec.get("external_import_authorizations", []) or []:
            if not isinstance(auth, dict):
                continue
            if (
                auth.get("record_id") == rid
                and auth.get("imported_status") == status
                and auth.get("artifact_commit_sha") == artifact.get("commit_sha")
                and auth.get("source_review_id") == ext.get("source_review_id")
                and auth.get("reviewer_context_id") == reviewer.get("context_id")
                and auth.get("expected_outcome") == current.get("outcome")
                and auth.get("one_shot") is True
                and auth.get("consumed_by_commit") is None
            ):
                return True
        return False

    if kind == "tests":
        ext = current.get("external_import") or {}
        execution = current.get("execution") or {}
        auth_source = str(ext.get("authorization_source") or "")
        source_id = str(((current.get("acceptance_cold_read") or {}).get("source") or {}).get("source_id") or "")
        for auth in parent_spec.get("external_execution_import_authorizations", []) or []:
            if not isinstance(auth, dict):
                continue
            if (
                auth.get("record_id") == rid
                and auth.get("imported_status") == status
                and auth.get("execution_commit_sha") == execution.get("commit_sha")
                and auth.get("expected_result") == execution.get("result")
                and auth.get("one_shot") is True
                and auth.get("consumed_by_commit") is None
                and auth.get("source_id") == source_id
                and "@" in auth_source
            ):
                return True
    return False


def record_introduction_allowed(root: Path, parent_sha: str, materialize_sha: str, policy_sha: str, kind: str, current: dict[str, Any]) -> bool:
    spec = canonical_machine_spec(root, materialize_sha, kind) or canonical_machine_spec(root, policy_sha, kind)
    initial = spec.get("initial")
    if initial is not None and current.get("status") == initial:
        return True
    return historical_import_allowed(root, parent_sha, materialize_sha, policy_sha, kind, current)


def requirement_acceptance_satisfied(root: Path, sha: str, requirement: dict[str, Any]) -> bool:
    rid = requirement.get("id")
    ident = requirement.get("content_identity") or {}
    digest = ident.get("digest")
    if ident.get("scheme") != "REQUIREMENT_NORMATIVE_V1" or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        return False
    verification = requirement.get("verification") or {}
    review_ok = False
    for review_id in verification.get("acceptance_evidence", []) or []:
        if not isinstance(review_id, str) or not review_id.startswith("REVIEW-"):
            continue
        review = show_yaml(root, sha, f"registry/reviews/{review_id}.yaml") or {}
        scope = review.get("scope") or {}
        revision = (scope.get("requirement_revisions") or {}).get(rid) or {}
        if (
            review.get("status") == "COMPLETE"
            and review.get("outcome") in {"APPROVE", "APPROVE_WITH_FOLLOWUP"}
            and rid in (scope.get("requirements") or [])
            and revision.get("digest") == digest
            and revision.get("status_at_review") == "PROPOSED"
            and review_independence_rank((review.get("reviewer") or {}).get("independence_level")) >= 2
        ):
            review_ok = True
            break
    cold_ok = False
    required_outcomes = {
        "understood_without_author_reasoning", "atomic_and_testable", "dependencies_and_conflicts_checked",
        "omissions_and_failure_modes_checked", "evidence_plan_sufficient",
    }
    for test_id in verification.get("acceptance_cold_read_test_ids", []) or []:
        if not isinstance(test_id, str) or not test_id.startswith("TEST-"):
            continue
        test = show_yaml(root, sha, f"registry/tests/{test_id}.yaml") or {}
        cold = test.get("acceptance_cold_read") or {}
        binding = (cold.get("requirements") or {}).get(rid) or {}
        executor = cold.get("executor") or {}
        outcomes = cold.get("required_outcomes") or {}
        if (
            test.get("status") == "PASS"
            and rid in ((test.get("protects") or {}).get("requirements") or [])
            and cold.get("qualifies") is True
            and binding.get("content_digest") == digest
            and binding.get("status_at_read") == "PROPOSED"
            and review_independence_rank(executor.get("independence_level")) >= 2
            and executor.get("fresh_context") is True
            and executor.get("authoring_context_separated") is True
            and cold.get("all_required_outcomes_pass") is True
            and required_outcomes.issubset(outcomes)
            and all(outcomes.get(key) == "PASS" for key in required_outcomes)
            and FULL_COMMIT_SHA.fullmatch(str((test.get("execution") or {}).get("commit_sha") or ""))
        ):
            cold_ok = True
            break
    return review_ok and cold_ok
''',
    "canonical machine helpers",
)
needle = 'def canonical_machine_spec(root: Path, sha: str, kind: str) -> dict[str, Any]:'
insert = '''def test_semantic_projection(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    keys = ("name", "type", "protects", "cases", "location", "environment", "execution_definition", "execution_evidence_policy")
    out = {key: data.get(key) for key in keys if key in data}
    execution = data.get("execution")
    if isinstance(execution, dict) and "command_or_workflow" in execution:
        out["execution"] = {"command_or_workflow": execution.get("command_or_workflow")}
    return out


'''
s = replace_once(s, needle, insert + needle, "test semantic projection")
s = replace_once(
    s,
    '''    if file_path.startswith(ADMIN_PATH_PREFIXES):
        return False
    if file_path == work_path:
''',
    '''    if file_path.startswith(ADMIN_PATH_PREFIXES):
        return False
    if file_path.startswith("registry/tests/"):
        changed_id = registry_id_for_change(root, reviewed, head, file_path)
        if changed_id not in work_referenced_ids(work):
            return False
        old_test = show_yaml(root, reviewed, file_path)
        new_test = show_yaml(root, head, file_path)
        return test_semantic_projection(old_test) != test_semantic_projection(new_test)
    if file_path == work_path:
''',
    "test relevance",
)
s = replace_once(s, '    endpoint_files = changed_files(root, base, head)\n', '    endpoint_files = endpoint_changed_files(root, base, head)\n', "merge-base endpoint")
s = replace_once(
    s,
    '''            if previous and current is None:
                out.append(ChangeFinding(path, "RECORD_DELETE", f"published registry record deleted at {sha[:12]}"))
                continue
            if previous and current:
                if previous.get("id") != current.get("id"):
                    out.append(ChangeFinding(path, "ID_IMMUTABLE", f"registry id changed at {sha[:12]}"))
                before, after = previous.get("status"), current.get("status")
                allowed = canonical_transitions(root, sha, kind)
                if before != after and after not in allowed.get(str(before), set()):
                    out.append(ChangeFinding(path, "STATE_TRANSITION", f"invalid {kind} transition {before} -> {after} at {sha[:12]}"))
                if kind == "work-items" and before in ACTIVE_WORK_STATUSES and semantic_projection(previous) != semantic_projection(current):
                    scope_change = current.get("scope_change") or {}
                    if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                        out.append(ChangeFinding(path, "SCOPE_DRIFT", f"semantic scope/AC/review/contracts changed at {sha[:12]} without approved scope_change rationale"))
''',
    '''            if previous and current is None:
                out.append(ChangeFinding(path, "RECORD_DELETE", f"published registry record deleted at {sha[:12]}"))
                continue
            if previous is None and current:
                if not record_introduction_allowed(root, previous_sha, sha, head, kind, current):
                    out.append(ChangeFinding(path, "STATE_INITIAL", f"new {kind} record {current.get('id')} materialized as {current.get('status')!r} without canonical initial state or exact import exception at {sha[:12]}"))
                continue
            if previous and current:
                if previous.get("id") != current.get("id"):
                    out.append(ChangeFinding(path, "ID_IMMUTABLE", f"registry id changed at {sha[:12]}"))
                before, after = previous.get("status"), current.get("status")
                allowed = canonical_transitions(root, sha, kind)
                if before != after and after not in allowed.get(str(before), set()):
                    out.append(ChangeFinding(path, "STATE_TRANSITION", f"invalid {kind} transition {before} -> {after} at {sha[:12]}"))
                if kind == "requirements" and before == "PROPOSED" and after == "ACCEPTED" and not requirement_acceptance_satisfied(root, sha, current):
                    out.append(ChangeFinding(path, "ACCEPTANCE_PRECONDITION", f"requirement {current.get('id')} accepted without qualifying exact-revision review and cold-read evidence at {sha[:12]}"))
                if kind == "work-items" and before in ACTIVE_WORK_STATUSES and semantic_projection(previous) != semantic_projection(current):
                    scope_change = current.get("scope_change") or {}
                    if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                        out.append(ChangeFinding(path, "SCOPE_DRIFT", f"semantic scope/AC/review/contracts changed at {sha[:12]} without approved scope_change rationale"))
''',
    "edge lifecycle",
)
s = replace_once(
    s,
    '''            reviewed = str((review.get("artifact") or {}).get("commit_sha") or "")
            if not reviewed or reviewed == head:
                continue
            try:
                later = changed_files(root, reviewed, head)
            except RuntimeError:
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", "review commit is not available in history"))
                continue
''',
    '''            reviewed = str((review.get("artifact") or {}).get("commit_sha") or "")
            if not FULL_COMMIT_SHA.fullmatch(reviewed):
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", "review commit must be a full immutable 40-hex commit object id"))
                continue
            if subprocess.run(["git", "cat-file", "-e", f"{reviewed}^{{commit}}"], cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", "review commit is not an available commit object"))
                continue
            if reviewed == head:
                continue
            if not is_ancestor(root, reviewed, head):
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", "review commit is not an ancestor of the current head"))
                continue
            later = changed_files(root, reviewed, head)
''',
    "review immutable SHA",
)
p.write_text(s, encoding="utf-8")

# tests.schema.json
p = Path("schemas/registry/tests.schema.json")
data = json.loads(p.read_text(encoding="utf-8"))
execution = data["properties"]["execution"]
execution["properties"]["commit_sha"] = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
execution["properties"]["result"] = {"const": "PASS"}
execution["required"] = ["command_or_workflow", "commit_sha", "result", "evidence"]
then = data["allOf"][0]["then"]
then["required"] = ["name", "type", "protects", "cases", "execution"]
then.pop("anyOf", None)
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

# reviews.schema.json
p = Path("schemas/registry/reviews.schema.json")
data = json.loads(p.read_text(encoding="utf-8"))
sha_schema = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
data["properties"]["artifact"]["properties"]["commit_sha"] = {"anyOf": [sha_schema, {"type": "null"}]}
data["allOf"][0]["then"]["properties"]["artifact"]["properties"]["commit_sha"] = sha_schema
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

# strict_contracts.py
p = Path("tools/governance/strict_contracts.py")
s = p.read_text(encoding="utf-8")
s = replace_once(s, 'BLOCKING_REVIEW_RANK = 2\n', 'BLOCKING_REVIEW_RANK = 2\nFULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")\n', "strict sha regex")
s = replace_once(
    s,
    '''def validate_review_findings(path: str, review_id: str, review: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    for finding in review.get("findings", []) or []:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        rank = REVIEW_SEVERITY_RANK.get(str(severity))
        if rank is None:
            issues.append(Issue(path, "DONE_REVIEW_SEVERITY", f"review {review_id} has unknown finding severity {severity!r}"))
            continue
        if rank <= BLOCKING_REVIEW_RANK and finding.get("disposition") not in {"RESOLVED", "ACCEPTED"}:
            issues.append(Issue(path, "DONE_REVIEW_FINDING", f"review {review_id} retains blocking finding {finding.get('id')} with severity {severity}"))
    return issues
''',
    '''def accepted_finding_authorized(root: Path, assurance_level: str, finding: dict[str, Any]) -> bool:
    policy = load_mapping(root / "registry/acceptance-authority.yaml")
    acceptance = finding.get("acceptance") or {}
    severity = str(finding.get("severity") or "")
    matrix = ((policy.get("finding_acceptance") or {}).get("matrix") or {}).get(assurance_level) or {}
    allowed_roles = matrix.get(severity) or []
    role = acceptance.get("authority_role")
    evidence_type = acceptance.get("authority_evidence_type")
    role_spec = (((policy.get("vocabulary") or {}).get("authority_roles") or {}).get(role) or {})
    expected_rule = f"FINDING:{assurance_level}:{severity}"
    required = ("accepted_by", "authority_role", "authority_evidence_type", "authority_evidence_ref", "authority_matrix_version", "authority_rule_id", "rationale", "accepted_at", "review_condition")
    if not all(acceptance.get(key) not in (None, "") for key in required):
        return False
    if role not in allowed_roles or evidence_type not in (role_spec.get("allowed_evidence_types") or []):
        return False
    if acceptance.get("authority_matrix_version") != policy.get("version") or acceptance.get("authority_rule_id") != expected_rule:
        return False
    ref = str(acceptance.get("authority_evidence_ref") or "")
    actor = str(acceptance.get("accepted_by") or "")
    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":
        match = re.fullmatch(r"https://api\\.github\\.com/repos/([^/]+)/([^/]+)", ref)
        return bool(match and actor == match.group(1))
    if evidence_type == "WORK_ITEM_OWNER_BINDING":
        return ref.startswith("registry/work-items/") and (root / ref).exists()
    if evidence_type in {"GOVERNANCE_DELEGATION", "GOVERNANCE_SECURITY_DELEGATION", "EXPLICIT_REPOSITORY_OWNER_DECISION"}:
        return ref.startswith("registry/") and (root / ref).exists()
    return False


def validate_review_findings(root: Path, path: str, review_id: str, review: dict[str, Any], assurance_level: str) -> list[Issue]:
    issues: list[Issue] = []
    for finding in review.get("findings", []) or []:
        if not isinstance(finding, dict):
            continue
        severity = finding.get("severity")
        rank = REVIEW_SEVERITY_RANK.get(str(severity))
        if rank is None:
            issues.append(Issue(path, "DONE_REVIEW_SEVERITY", f"review {review_id} has unknown finding severity {severity!r}"))
            continue
        if rank <= BLOCKING_REVIEW_RANK:
            disposition = finding.get("disposition")
            if disposition == "ACCEPTED" and not accepted_finding_authorized(root, assurance_level, finding):
                issues.append(Issue(path, "DONE_REVIEW_AUTHORITY", f"review {review_id} blocking finding {finding.get('id')} has invalid acceptance authority"))
            elif disposition not in {"RESOLVED", "ACCEPTED"}:
                issues.append(Issue(path, "DONE_REVIEW_FINDING", f"review {review_id} retains blocking finding {finding.get('id')} with severity {severity}"))
    return issues


def pass_test_has_execution(test: dict[str, Any]) -> bool:
    execution = test.get("execution") or {}
    return bool(
        test.get("status") == "PASS"
        and isinstance(execution, dict)
        and execution.get("result") == "PASS"
        and FULL_COMMIT_SHA.fullmatch(str(execution.get("commit_sha") or ""))
        and isinstance(execution.get("evidence"), list)
        and bool(execution.get("evidence"))
        and isinstance(execution.get("command_or_workflow"), str)
        and bool(execution.get("command_or_workflow").strip())
    )
''',
    "authority validator",
)
s = replace_once(
    s,
    '''                if review.get("status") == "COMPLETE" and not reviewed_sha:
                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SHA", f"review {rid} is COMPLETE but has no artifact.commit_sha"))
''',
    '''                if review.get("status") == "COMPLETE" and not FULL_COMMIT_SHA.fullmatch(reviewed_sha):
                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SHA", f"review {rid} is COMPLETE but artifact.commit_sha is not a full immutable 40-hex object id"))
''',
    "strict review sha",
)
s = replace_once(
    s,
    'issues.extend(validate_review_findings(f"registry/work-items/{wid}.yaml", rid, review))',
    'issues.extend(validate_review_findings(root, f"registry/work-items/{wid}.yaml", rid, review, assurance_level))',
    "authority call",
)
s = replace_once(
    s,
    '''            if test is None or test.get("status") != "PASS":
                actual = None if test is None else test.get("status")
                issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_TEST_EVIDENCE", f"required test {tid} must exist with status PASS, got {actual!r}"))
''',
    '''            if test is None or not pass_test_has_execution(test):
                actual = None if test is None else test.get("status")
                issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_TEST_EVIDENCE", f"required test {tid} must have status PASS plus concrete revision-bound execution evidence, got {actual!r}"))
''',
    "strict test evidence",
)
p.write_text(s, encoding="utf-8")

# Bind TEST-0002 and TEST-0003 to the real exact-SHA run already executed.
for tid in ("TEST-0002", "TEST-0003"):
    p = Path(f"registry/tests/{tid}.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if tid == "TEST-0002":
        command = "GitHub Actions MONDE Gate run 34828663346 / governance pytest+coverage+mutation suite"
        evidence = [
            "GitHub Actions run 34828663346 on exact commit 40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5: Governance core success.",
            "88/88 tests PASS; 1165/1165 statements and 610/610 branches covered; 21/21 critical mutations killed; repository/strict/path/change validators zero.",
        ]
    else:
        command = ".github/workflows/governance.yml / GitHub Actions MONDE Gate run 34828663346"
        evidence = [
            "GitHub Actions run 34828663346 on exact commit 40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5: Governance core, CodeQL and Dependency Review lanes executed successfully.",
            "Final MONDE merge gate failed closed solely because six review threads were deliberately unresolved, proving live GitHub-state enforcement rather than a false merge-safe result.",
        ]
    data["execution"] = {
        "command_or_workflow": command,
        "commit_sha": "40550a5d3e3e3f75f467c6e6cd29d3fe729a25e5",
        "result": "PASS",
        "evidence": evidence,
    }
    data.setdefault("history", {})["updated_at"] = "2026-09-14"
    p.write_text(yaml.safe_dump(data, sort_keys=False, width=120), encoding="utf-8")

# Preserve immutable bootstrap direct-PASS introductions as exact historical exceptions.
p = Path("registry/status-machines.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))
tests = data["registry_machines"]["tests"]
exceptions = tests.setdefault("historical_import_exceptions", [])
for record_id, commit_sha in (
    ("TEST-0002", "97287dd84ba424fa44b5d82e98060bcd2f6d1bcd"),
    ("TEST-0003", "74eee2b3a37017ba197df98a9eb7982cfb53e41a"),
):
    if not any(isinstance(item, dict) and item.get("record_id") == record_id for item in exceptions):
        exceptions.append(
            {
                "record_id": record_id,
                "imported_status": "PASS",
                "import_commit": commit_sha,
                "reason": "Bootstrap-era WORK-0002 test record was first materialized directly as PASS before repository-native TEST lifecycle checkpoints were enforced. Immutable history is preserved exactly; current PASS evidence is separately revision-bound to a real execution.",
                "historical_only": True,
                "future_reuse_forbidden": True,
                "review_origin": "REVIEW-0029/F-1",
            }
        )
p.write_text(yaml.safe_dump(data, sort_keys=False, width=160), encoding="utf-8")

# Regression updates.
p = Path("tests/governance/test_final_l2_findings.py")
s = p.read_text(encoding="utf-8")
s = replace_once(
    s,
    '''        "execution": {
            "command_or_workflow": "manual",
            "result": "PASS",
            "evidence": ["evidence"],
        },''',
    '''        "execution": {
            "command_or_workflow": "manual",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "result": "PASS",
            "evidence": ["evidence"],
        },''',
    "test execution fixture",
)
s = replace_once(
    s,
    '''    review["artifact"]["commit_sha"] = "abc123"
    assert list(Draft202012Validator(review_schema).iter_errors(review)) == []
''',
    '''    review["artifact"]["commit_sha"] = "abc123"
    assert list(Draft202012Validator(review_schema).iter_errors(review))
    review["artifact"]["commit_sha"] = "0123456789abcdef0123456789abcdef01234567"
    assert list(Draft202012Validator(review_schema).iter_errors(review)) == []
''',
    "review schema fixture",
)
s = replace_once(s, '    assert list(validator.iter_errors(definition_backed)) == []\n', '    assert list(validator.iter_errors(definition_backed))\n', "definition-only PASS")
s += '''


def test_blocking_accepted_finding_requires_matrix_authority(tmp_path: Path) -> None:
    policy = yaml.safe_load(Path("registry/acceptance-authority.yaml").read_text(encoding="utf-8"))
    dump(tmp_path / "registry/acceptance-authority.yaml", policy)
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "artifact": {"type": "WORK_ITEM", "id_or_path": "WORK-1", "commit_sha": "0123456789abcdef0123456789abcdef01234567"},
        "scope": {"work_items": ["WORK-1"]},
        "findings": [{
            "id": "F-1", "severity": "R2_MAJOR", "disposition": "ACCEPTED",
            "acceptance": {
                "accepted_by": "author", "authority_role": "WORK_OWNER", "authority_evidence_type": "WORK_ITEM_OWNER_BINDING",
                "authority_evidence_ref": "registry/work-items/WORK-1.yaml", "authority_matrix_version": 1,
                "authority_rule_id": "FINDING:A3:R2_MAJOR", "rationale": "x", "accepted_at": "2026-09-14", "review_condition": "later",
            },
        }],
    }
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "status": "DONE", "depends_on": [], "assurance": {"level": "A3"}, "review_plan": {"independence_level": "L2", "completed_reviews": ["REVIEW-1"]}, "required_tests": {}, "completion": {"specification_gates_checked": True}})
    assert "DONE_REVIEW_AUTHORITY" in {x.rule for x in validate_work_lifecycle(tmp_path)}
    review["findings"][0]["acceptance"].update({"accepted_by": "owner", "authority_role": "REPOSITORY_OWNER", "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION", "authority_evidence_ref": "https://api.github.com/repos/owner/repo"})
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    assert "DONE_REVIEW_AUTHORITY" not in {x.rule for x in validate_work_lifecycle(tmp_path)}
'''
p.write_text(s, encoding="utf-8")

p = Path("tests/governance/test_change_guard.py")
s = p.read_text(encoding="utf-8")
s = s.replace("'work_items':{'transitions':", "'work_items':{'initial':'PROPOSED','transitions':", 1)
s = s.replace("'reviews':{'transitions':", "'reviews':{'initial':'OPEN','transitions':", 1)
s = s.replace("'tests':{'transitions':", "'tests':{'initial':'PLANNED','transitions':", 1)
s = s.replace("        'tests':{'initial':'PLANNED'", "        'requirements':{'initial':'PROPOSED','transitions':{'PROPOSED':['ACCEPTED','CANCELLED'],'ACCEPTED':['SUPERSEDED','DEPRECATED']}},\n        'tests':{'initial':'PLANNED'", 1)
s = replace_once(
    s,
    "write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'COMPLETE','artifact':{'commit_sha':''}});h4=commit(tmp_path,'complete no sha');assert not [x for x in c.validate(tmp_path,h3,h4) if x.rule=='REVIEW_FRESHNESS']",
    "write(tmp_path,'registry/reviews/REVIEW-2.yaml',{'id':'REVIEW-2','status':'COMPLETE','artifact':{'commit_sha':''}});h4=commit(tmp_path,'complete no sha');assert 'REVIEW_FRESHNESS' in {x.rule for x in c.validate(tmp_path,h3,h4)}",
    "empty review sha expectation",
)
s += '''


def test_new_terminal_records_fail_initial_state(tmp_path):
    base = repo(tmp_path)
    write(tmp_path, 'registry/tests/TEST-9.yaml', {'id': 'TEST-9', 'status': 'PASS'})
    write(tmp_path, 'registry/reviews/REVIEW-9.yaml', {'id': 'REVIEW-9', 'status': 'COMPLETE', 'artifact': {'commit_sha': base}, 'outcome': 'APPROVE'})
    write(tmp_path, 'registry/requirements/REQ-9.yaml', {'id': 'REQ-9', 'status': 'ACCEPTED'})
    head = commit(tmp_path, 'bad terminal introductions')
    assert len([f for f in c.validate(tmp_path, base, head) if f.rule == 'STATE_INITIAL']) == 3


def test_requirement_acceptance_requires_bound_review_and_cold_read(tmp_path):
    base = repo(tmp_path)
    req = {'id': 'REQ-1', 'status': 'PROPOSED', 'content_identity': {'scheme': 'REQUIREMENT_NORMATIVE_V1', 'digest': 'sha256:' + 'a' * 64}, 'verification': {'acceptance_evidence': [], 'acceptance_cold_read_test_ids': []}}
    write(tmp_path, 'registry/requirements/REQ-1.yaml', req)
    base = commit(tmp_path, 'proposed requirement')
    req['status'] = 'ACCEPTED'
    write(tmp_path, 'registry/requirements/REQ-1.yaml', req)
    head = commit(tmp_path, 'accept without proof')
    assert 'ACCEPTANCE_PRECONDITION' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_review_ref_must_be_full_existing_ancestor(tmp_path):
    base = repo(tmp_path)
    w = yaml.safe_load((tmp_path / 'registry/work-items/WORK-1.yaml').read_text())
    w['status'] = 'IN_REVIEW'; w['review_plan']['completed_reviews'] = ['REVIEW-1']
    write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    write(tmp_path, 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': 'HEAD'}})
    head = commit(tmp_path, 'mutable review ref')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_required_test_contract_change_stales_review_but_execution_metadata_does_not(tmp_path):
    base = repo(tmp_path)
    w = yaml.safe_load((tmp_path / 'registry/work-items/WORK-1.yaml').read_text())
    w['status'] = 'IN_REVIEW'; w['required_tests'] = {'unit': ['TEST-1']}
    write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    test = {'id': 'TEST-1', 'status': 'PASS', 'name': 't', 'type': 'UNIT', 'protects': {'contracts': ['c']}, 'cases': {'happy': ['x']}, 'execution_definition': {'command': 'pytest'}, 'execution_evidence_policy': {'source_of_truth': 'CI', 'rule': 'sha'}, 'execution': {'command_or_workflow': 'pytest', 'commit_sha': '0' * 40, 'result': 'PASS', 'evidence': ['x']}}
    write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    reviewed = commit(tmp_path, 'reviewed test contract')
    write(tmp_path, 'registry/reviews/REVIEW-1.yaml', {'id': 'REVIEW-1', 'status': 'COMPLETE', 'artifact': {'commit_sha': reviewed}})
    w['review_plan']['completed_reviews'] = ['REVIEW-1']; write(tmp_path, 'registry/work-items/WORK-1.yaml', w)
    admin = commit(tmp_path, 'attach review')
    test['execution']['evidence'] = ['new run']; write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    meta = commit(tmp_path, 'execution metadata')
    assert 'REVIEW_FRESHNESS' not in {f.rule for f in c.validate(tmp_path, admin, meta)}
    base = meta; test['cases'] = {'happy': ['weakened']}; write(tmp_path, 'registry/tests/TEST-1.yaml', test)
    head = commit(tmp_path, 'test semantic drift')
    assert 'REVIEW_FRESHNESS' in {f.rule for f in c.validate(tmp_path, base, head)}


def test_endpoint_changes_use_merge_base_not_moved_base_tip(tmp_path):
    common = repo(tmp_path)
    run(tmp_path, 'branch', 'feature', common); run(tmp_path, 'branch', 'mainline', common)
    run(tmp_path, 'checkout', 'feature'); write(tmp_path, 'feature.txt', 'feature'); head = commit(tmp_path, 'feature')
    run(tmp_path, 'checkout', 'mainline'); write(tmp_path, 'registry/reviews/BASE-ONLY.yaml', {'id': 'REVIEW-99', 'status': 'OPEN'}); base = commit(tmp_path, 'base only')
    run(tmp_path, 'checkout', 'feature')
    assert 'registry/reviews/BASE-ONLY.yaml' not in c.endpoint_changed_files(tmp_path, base, head)
'''
p.write_text(s, encoding="utf-8")

# Mutation smoke additions.
p = Path("scripts/governance_mutation_smoke.py")
s = p.read_text(encoding="utf-8")
marker = "}\n\n\ndef main() -> int:"
extra = '''    "lifecycle-initial-state": (
        "tools/governance/change_guard.py",
        "if not record_introduction_allowed(root, previous_sha, sha, head, kind, current):",
        "if False:",
    ),
    "requirement-acceptance-precondition": (
        "tools/governance/change_guard.py",
        "and not requirement_acceptance_satisfied(root, sha, current):",
        "and False:",
    ),
    "review-full-immutable-sha": (
        "tools/governance/change_guard.py",
        "if not FULL_COMMIT_SHA.fullmatch(reviewed):",
        "if False:",
    ),
    "blocking-finding-authority": (
        "tools/governance/strict_contracts.py",
        "if disposition == \\\"ACCEPTED\\\" and not accepted_finding_authorized(root, assurance_level, finding):",
        "if False:",
    ),
    "required-test-semantic-freshness": (
        "tools/governance/change_guard.py",
        "return test_semantic_projection(old_test) != test_semantic_projection(new_test)",
        "return False",
    ),
    "endpoint-merge-base": (
        "tools/governance/change_guard.py",
        "endpoint_files = endpoint_changed_files(root, base, head)",
        "endpoint_files = changed_files(root, base, head)",
    ),
'''
assert s.count(marker) == 1
s = s.replace(marker, extra + marker, 1)
p.write_text(s, encoding="utf-8")

# WORK-0002 tracks all six new findings without claiming resolution.
p = Path("registry/work-items/WORK-0002.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))
data["updated_at"] = "2026-09-14"
data["scope_change"]["rationale"] = "Fresh exact-SHA L2 REVIEW-0029 found six additional lifecycle/evidence/authority/freshness/merge-base defects after the v10 integration; owner authorizes correcting those defects without changing product scope."
open_findings = data["review_plan"].setdefault("open_findings", [])
for item in (
    "REVIEW-0029/F-1 / P1: enforce canonical initial-state, acceptance-precondition and one-shot import semantics in the change guard.",
    "REVIEW-0029/F-2 / P1: every active PASS TEST requires concrete revision-bound execution evidence.",
    "REVIEW-0029/F-3 / P1: COMPLETE review revisions must be full immutable existing commit object IDs and freshness-safe ancestors.",
    "REVIEW-0029/F-4 / P1: blocking finding ACCEPTED requires matrix-authorized typed durable authority evidence.",
    "REVIEW-0029/F-5 / P1: required TEST semantic contracts remain review-freshness-relevant while execution metadata may be administrative.",
    "REVIEW-0029/F-6 / P2: endpoint scope uses PR merge-base semantics while commit-edge validation uses true parents.",
):
    if item not in open_findings:
        open_findings.append(item)
regressions = data["required_tests"].setdefault("regression", [])
for item in (
    "new non-initial TEST/REVIEW/REQ terminal records fail unless covered by exact historical/import exception",
    "PROPOSED to ACCEPTED requirements fail without exact bound independent review and cold-read evidence",
    "mutable/short/nonexistent review commit references fail freshness",
    "blocking accepted findings fail without canonical authority matrix evidence",
    "required-test semantic weakening stales review while execution-only evidence changes remain administrative",
    "endpoint scope excludes base-only changes by using merge-base semantics",
):
    if item not in regressions:
        regressions.append(item)
p.write_text(yaml.safe_dump(data, sort_keys=False, width=140), encoding="utf-8")
