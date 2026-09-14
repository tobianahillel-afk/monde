from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    assert count == 1, (path, count, old[:120])
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_once(path: str, anchor: str, block: str, before: bool = True) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(anchor)
    assert count == 1, (path, count, anchor[:120])
    replacement = block + anchor if before else anchor + block
    p.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")


replace_once(
    "tools/governance/change_guard.py",
    "import argparse\nimport json\nimport re\n",
    "import argparse\nimport hashlib\nimport json\nimport math\nimport re\n",
)

anchor = '''def historical_import_allowed(root: Path, parent_sha: str, materialize_sha: str, policy_sha: str, kind: str, current: dict[str, Any]) -> bool:\n'''
block = r'''
JCS_SAFE_INTEGER = 9007199254740991
ASSURANCE_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4}


def governed_repository_slug(root: Path) -> tuple[str, str] | None:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        return None
    value = proc.stdout.strip()
    prefixes = ("https://github.com/", "http://github.com/", "ssh://git@github.com/")
    for prefix in prefixes:
        if value.startswith(prefix):
            tail = value[len(prefix):].strip("/").removesuffix(".git")
            parts = tail.split("/")
            return (parts[0], parts[1]) if len(parts) == 2 and all(parts) else None
    if value.startswith("git@github.com:"):
        tail = value[len("git@github.com:"):].strip("/").removesuffix(".git")
        parts = tail.split("/")
        return (parts[0], parts[1]) if len(parts) == 2 and all(parts) else None
    return None


def _jcs_string(value: str) -> str:
    try:
        value.encode("utf-16-be")
    except UnicodeEncodeError as exc:
        raise ValueError("invalid Unicode surrogate in JCS string") from exc
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _ecmascript_number(value: int | float) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a JCS number")
    if isinstance(value, int):
        if abs(value) > JCS_SAFE_INTEGER:
            raise ValueError("integer exceeds exact IEEE-754 safe range")
        return str(value)
    if not isinstance(value, float) or not math.isfinite(value):
        raise ValueError("JCS numbers must be finite IEEE-754 values")
    if value == 0:
        return "0"
    text = repr(value).lower()
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    if "e" not in text:
        if text.endswith(".0"):
            text = text[:-2]
        return sign + text
    mantissa, exp_text = text.split("e", 1)
    exponent = int(exp_text)
    digits = mantissa.replace(".", "")
    if not digits or not digits.isdigit():
        raise ValueError("unexpected float representation")
    k = len(digits)
    n = 1 + exponent
    if 0 < n <= 21:
        if k <= n:
            rendered = digits + ("0" * (n - k))
        else:
            rendered = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        rendered = "0." + ("0" * (-n)) + digits
    else:
        exponent_out = n - 1
        rendered = digits[0]
        if k > 1:
            rendered += "." + digits[1:]
        rendered += "e" + ("+" if exponent_out >= 0 else "") + str(exponent_out)
    return sign + rendered


def jcs_serialize(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _jcs_string(value)
    if isinstance(value, (int, float)):
        return _ecmascript_number(value)
    if isinstance(value, list):
        return "[" + ",".join(jcs_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        items: list[tuple[bytes, str, Any]] = []
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JCS object keys must be strings")
            try:
                sort_key = key.encode("utf-16-be")
            except UnicodeEncodeError as exc:
                raise ValueError("invalid Unicode surrogate in JCS object key") from exc
            items.append((sort_key, key, item))
        items.sort(key=lambda entry: entry[0])
        return "{" + ",".join(_jcs_string(key) + ":" + jcs_serialize(item) for _, key, item in items) + "}"
    raise ValueError(f"unsupported JCS value type: {type(value).__name__}")


def requirement_normative_projection(requirement: dict[str, Any], scheme: dict[str, Any]) -> dict[str, Any]:
    fields = scheme.get("included_fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("content-identity scheme has no included_fields")
    projected: dict[str, Any] = {}
    for raw_path in fields:
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError("invalid content-identity field path")
        parts = raw_path.split(".")
        source: Any = requirement
        for part in parts:
            if not isinstance(source, dict) or part not in source:
                raise ValueError(f"missing normative path {raw_path}")
            source = source[part]
        target = projected
        for part in parts[:-1]:
            existing = target.get(part)
            if existing is None:
                existing = {}
                target[part] = existing
            if not isinstance(existing, dict):
                raise ValueError(f"projection collision at {raw_path}")
            target = existing
        target[parts[-1]] = source
    return projected


def recompute_requirement_digest(root: Path, sha: str, requirement: dict[str, Any]) -> str | None:
    identity = requirement.get("content_identity") or {}
    if identity.get("scheme") != "REQUIREMENT_NORMATIVE_V1":
        return None
    policy = show_yaml(root, sha, "registry/content-identity.yaml") or {}
    scheme = ((policy.get("schemes") or {}).get("REQUIREMENT_NORMATIVE_V1") or {})
    canonical = scheme.get("canonicalization") or {}
    if (
        scheme.get("algorithm") != "SHA256"
        or scheme.get("encoding") != "UTF-8"
        or canonical.get("standard") != "RFC_8785_JSON_CANONICALIZATION_SCHEME"
        or canonical.get("encoding") != "UTF-8"
    ):
        return None
    try:
        projection = requirement_normative_projection(requirement, scheme)
        payload = jcs_serialize(projection).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        return None
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def requirement_digest_matches(root: Path, sha: str, requirement: dict[str, Any]) -> bool:
    declared = str(((requirement.get("content_identity") or {}).get("digest") or ""))
    recomputed = recompute_requirement_digest(root, sha, requirement)
    return recomputed is not None and declared == recomputed


def authority_evidence_valid_at(
    root: Path,
    sha: str,
    actor: str,
    evidence_type: str,
    ref: str,
) -> bool:
    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":
        slug = governed_repository_slug(root)
        if slug is None or not actor:
            return False
        owner, repo = slug
        expected = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{actor}/permission"
        return ref == expected
    if evidence_type == "WORK_ITEM_OWNER_BINDING":
        return ref.startswith("registry/work-items/") and file_exists_at(root, sha, ref)
    if evidence_type in {
        "GOVERNANCE_DELEGATION",
        "GOVERNANCE_SECURITY_DELEGATION",
        "EXPLICIT_REPOSITORY_OWNER_DECISION",
    }:
        return ref.startswith("registry/") and file_exists_at(root, sha, ref)
    return False


def risk_acceptance_satisfied(root: Path, sha: str, risk: dict[str, Any]) -> bool:
    machine = canonical_machine_spec(root, sha, "risks")
    preconditions = machine.get("acceptance_preconditions") or {}
    required_fields = preconditions.get("required_fields") or []
    resolution = risk.get("resolution") or {}
    if (
        not isinstance(required_fields, list)
        or not required_fields
        or resolution.get("accepted") is not True
        or any(resolution.get(str(field).split(".", 1)[-1]) in (None, "") for field in required_fields)
    ):
        return False

    policy = show_yaml(root, sha, "registry/acceptance-authority.yaml") or {}
    risk_policy = policy.get("risk_acceptance") or {}
    category = str(risk.get("category") or "")
    impact = str(((risk.get("assessment") or {}).get("impact") or ""))
    work_ids = ((risk.get("scope") or {}).get("work_items") or [])
    if not isinstance(work_ids, list) or not work_ids:
        return False

    levels: list[str] = []
    for wid in work_ids:
        if not isinstance(wid, str):
            return False
        work = show_yaml(root, sha, f"registry/work-items/{wid}.yaml") or {}
        level = str(((work.get("assurance") or {}).get("level") or ""))
        if level not in ASSURANCE_RANK:
            return False
        levels.append(level)
    assurance = max(levels, key=lambda level: ASSURANCE_RANK[level])

    overrides = ((risk_policy.get("category_overrides") or {}).get(category) or {})
    override_row = overrides.get(assurance) or {}
    if isinstance(override_row, dict) and impact in override_row:
        allowed_roles = override_row.get(impact) or []
        expected_rule = f"RISK_CATEGORY:{category}:{assurance}:{impact}"
    else:
        allowed_roles = (((risk_policy.get("default_matrix") or {}).get(assurance) or {}).get(impact) or [])
        expected_rule = f"RISK_DEFAULT:{assurance}:{impact}"

    role = str(resolution.get("authority_role") or "")
    evidence_type = str(resolution.get("authority_evidence_type") or "")
    actor = str(resolution.get("accepted_by") or "")
    ref = str(resolution.get("authority_evidence_ref") or "")
    role_spec = (((policy.get("vocabulary") or {}).get("authority_roles") or {}).get(role) or {})
    if (
        role not in allowed_roles
        or evidence_type not in (role_spec.get("allowed_evidence_types") or [])
        or resolution.get("authority_matrix_version") != policy.get("version")
        or resolution.get("authority_rule_id") != expected_rule
    ):
        return False
    return authority_evidence_valid_at(root, sha, actor, evidence_type, ref)


'''
insert_once("tools/governance/change_guard.py", anchor, block, before=True)

replace_once(
    "tools/governance/change_guard.py",
    '''    verification = requirement.get("verification") or {}\n''',
    '''    if not requirement_digest_matches(root, sha, requirement):\n        return False\n    verification = requirement.get("verification") or {}\n''',
)

replace_once(
    "tools/governance/change_guard.py",
    '''                if kind == "requirements" and before == "PROPOSED" and after == "ACCEPTED" and not requirement_acceptance_satisfied(root, sha, current):\n                    out.append(ChangeFinding(path, "ACCEPTANCE_PRECONDITION", f"requirement {current.get('id')} accepted without qualifying exact-revision review and cold-read evidence at {sha[:12]}"))\n''',
    '''                if kind == "requirements" and before == "PROPOSED" and after == "ACCEPTED" and not requirement_acceptance_satisfied(root, sha, current):\n                    out.append(ChangeFinding(path, "ACCEPTANCE_PRECONDITION", f"requirement {current.get('id')} accepted without matching RFC-8785 normative digest plus qualifying exact-revision review and cold-read evidence at {sha[:12]}"))\n                if kind == "risks" and before != "ACCEPTED" and after == "ACCEPTED" and not risk_acceptance_satisfied(root, sha, current):\n                    out.append(ChangeFinding(path, "RISK_ACCEPTANCE_PRECONDITION", f"risk {current.get('id')} accepted without canonical matrix-authorized acceptance evidence at {sha[:12]}"))\n''',
)

replace_once(
    "tools/governance/change_guard.py",
    '''            if not review or review.get("status") not in {"COMPLETE", "CLOSED"}:\n                continue\n''',
    '''            if not review or review.get("status") != "COMPLETE":\n                continue\n''',
)

replace_once(
    "tools/governance/strict_contracts.py",
    "import re\nimport sys\n",
    "import re\nimport subprocess\nimport sys\n",
)

anchor = '''def accepted_finding_authorized(root: Path, assurance_level: str, finding: dict[str, Any]) -> bool:\n'''
block = r'''
def governed_repository_slug(root: Path) -> tuple[str, str] | None:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        return None
    value = proc.stdout.strip()
    prefixes = ("https://github.com/", "http://github.com/", "ssh://git@github.com/")
    for prefix in prefixes:
        if value.startswith(prefix):
            tail = value[len(prefix):].strip("/").removesuffix(".git")
            parts = tail.split("/")
            return (parts[0], parts[1]) if len(parts) == 2 and all(parts) else None
    if value.startswith("git@github.com:"):
        tail = value[len("git@github.com:"):].strip("/").removesuffix(".git")
        parts = tail.split("/")
        return (parts[0], parts[1]) if len(parts) == 2 and all(parts) else None
    return None


def repository_owner_permission_ref_valid(root: Path, actor: str, ref: str) -> bool:
    slug = governed_repository_slug(root)
    if slug is None or not actor:
        return False
    owner, repo = slug
    return ref == f"https://api.github.com/repos/{owner}/{repo}/collaborators/{actor}/permission"


def git_commit_exists(root: Path, sha: str) -> bool:
    if not FULL_COMMIT_SHA.fullmatch(str(sha or "")):
        return False
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def git_commit_reachable(root: Path, sha: str) -> bool:
    if not git_commit_exists(root, sha):
        return False
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, "HEAD"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode == 0:
        return True
    refs = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname)", "--contains", sha, "refs/heads", "refs/remotes"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return refs.returncode == 0 and bool(refs.stdout.strip())


def external_review_import_finalized(root: Path, review_id: str, review: dict[str, Any]) -> bool:
    ext = review.get("external_import")
    if not ext:
        return True
    if not isinstance(ext, dict) or ext.get("mode") != "PREAUTHORIZED_EXTERNAL_COMPLETION":
        return False
    import_sha = str(ext.get("import_commit") or "")
    auth_sha = str(ext.get("authorization_commit") or "")
    if not FULL_COMMIT_SHA.fullmatch(import_sha) or not FULL_COMMIT_SHA.fullmatch(auth_sha):
        return False
    machine = load_mapping(root / "registry/status-machines.yaml")
    reviews = ((machine.get("registry_machines") or {}).get("reviews") or {})
    for auth in reviews.get("external_import_authorizations", []) or []:
        if not isinstance(auth, dict):
            continue
        if (
            auth.get("record_id") == review_id
            and auth.get("imported_status") == review.get("status")
            and auth.get("artifact_commit_sha") == ((review.get("artifact") or {}).get("commit_sha"))
            and auth.get("source_review_id") == ext.get("source_review_id")
            and auth.get("source_submitted_at") == ext.get("source_submitted_at")
            and auth.get("reviewer_context_id") == ((review.get("reviewer") or {}).get("context_id"))
            and auth.get("expected_outcome") == review.get("outcome")
            and auth.get("one_shot") is True
            and auth.get("consumed_by_commit") == import_sha
        ):
            return True
    return False


'''
insert_once("tools/governance/strict_contracts.py", anchor, block, before=True)

replace_once(
    "tools/governance/strict_contracts.py",
    '''    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":\n        match = re.fullmatch(r"https://api\\.github\\.com/repos/([^/]+)/([^/]+)", ref)\n        return bool(match and actor == match.group(1))\n''',
    '''    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":\n        return repository_owner_permission_ref_valid(root, actor, ref)\n''',
)

replace_once(
    "tools/governance/strict_contracts.py",
    '''def pass_test_has_execution(test: dict[str, Any]) -> bool:\n    execution = test.get("execution") or {}\n    return bool(\n        test.get("status") == "PASS"\n        and isinstance(execution, dict)\n        and execution.get("result") == "PASS"\n        and FULL_COMMIT_SHA.fullmatch(str(execution.get("commit_sha") or ""))\n        and isinstance(execution.get("evidence"), list)\n        and bool(execution.get("evidence"))\n        and isinstance(execution.get("command_or_workflow"), str)\n        and bool(execution.get("command_or_workflow").strip())\n    )\n''',
    '''def pass_test_has_execution(root: Path, test: dict[str, Any]) -> bool:\n    execution = test.get("execution") or {}\n    commit_sha = str(execution.get("commit_sha") or "") if isinstance(execution, dict) else ""\n    return bool(\n        test.get("status") == "PASS"\n        and isinstance(execution, dict)\n        and execution.get("result") == "PASS"\n        and FULL_COMMIT_SHA.fullmatch(commit_sha)\n        and git_commit_reachable(root, commit_sha)\n        and isinstance(execution.get("evidence"), list)\n        and bool(execution.get("evidence"))\n        and isinstance(execution.get("command_or_workflow"), str)\n        and bool(execution.get("command_or_workflow").strip())\n    )\n''',
)

replace_once(
    "tools/governance/strict_contracts.py",
    '''            if review is not None:\n                reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or "")).strip()\n                if review.get("status") == "COMPLETE" and not FULL_COMMIT_SHA.fullmatch(reviewed_sha):\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SHA", f"review {rid} is COMPLETE but artifact.commit_sha is not a full immutable 40-hex object id"))\n                if wid not in review_targets(review):\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SCOPE", f"review {rid} is not structurally bound to {wid}"))\n                issues.extend(validate_review_findings(root, f"registry/work-items/{wid}.yaml", rid, review, assurance_level))\n''',
    '''            if review is not None:\n                reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or "")).strip()\n                if review.get("status") != "COMPLETE":\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_STATUS", f"review {rid} must be COMPLETE to provide completion evidence"))\n                if review.get("status") == "COMPLETE" and not FULL_COMMIT_SHA.fullmatch(reviewed_sha):\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SHA", f"review {rid} is COMPLETE but artifact.commit_sha is not a full immutable 40-hex object id"))\n                if not external_review_import_finalized(root, rid, review):\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_IMPORT", f"review {rid} external import is not fully bound and consumed"))\n                if wid not in review_targets(review):\n                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SCOPE", f"review {rid} is not structurally bound to {wid}"))\n                issues.extend(validate_review_findings(root, f"registry/work-items/{wid}.yaml", rid, review, assurance_level))\n''',
)

replace_once(
    "tools/governance/strict_contracts.py",
    '''            if test is None or not pass_test_has_execution(test):\n''',
    '''            if test is None or not pass_test_has_execution(root, test):\n''',
)

replace_once(
    "tools/governance/validate_repo.py",
    '''            if data.get("status") not in {"COMPLETE", "CLOSED"}:\n                self.add(r.path, "DONE_REVIEW", f"review {rid} is not complete")\n            if data.get("outcome") not in REVIEW_OUTCOMES_APPROVING:\n''',
    '''            if data.get("status") != "COMPLETE":\n                self.add(r.path, "DONE_REVIEW", f"review {rid} is not COMPLETE approval evidence")\n                continue\n            if data.get("outcome") not in REVIEW_OUTCOMES_APPROVING:\n''',
)

replace_once(
    "registry/acceptance-authority.yaml",
    '''    - "authority_evidence_ref MUST be a resolvable durable reference establishing the named actor's role/delegation for the acceptance scope."\n''',
    '''    - "authority_evidence_ref MUST be a resolvable durable reference establishing the named actor's role/delegation for the acceptance scope."\n    - "For GITHUB_REPOSITORY_OWNER_PERMISSION, authority_evidence_ref MUST be the exact GitHub collaborator-permission API resource for accepted_by on the governed repository; cross-repository URLs or another actor's permission resource do not qualify."\n''',
)

replace_once(
    "registry/reviews/REVIEW-0001.yaml",
    '''      authority_evidence_ref: "https://api.github.com/repos/tobianahillel-afk/monde"\n''',
    '''      authority_evidence_ref: "https://api.github.com/repos/tobianahillel-afk/monde/collaborators/tobianahillel-afk/permission"\n''',
)

replace_once(
    "tests/governance/test_review0029_branches.py",
    '''    records = {\n''',
    '''    monkeypatch.setattr(cg, "requirement_digest_matches", lambda *args: True)\n    records = {\n''',
)

replace_once(
    "tests/governance/test_review0029_branches.py",
    '''def test_pass_execution_helper() -> None:\n    assert not pass_test_has_execution({"status": "PASS"})\n    assert pass_test_has_execution({"status": "PASS", "execution": {"command_or_workflow": "pytest", "commit_sha": "a" * 40, "result": "PASS", "evidence": ["ci"]}})\n''',
    '''def test_pass_execution_helper(tmp_path: Path) -> None:\n    sha = init_repo(tmp_path)\n    assert not pass_test_has_execution(tmp_path, {"status": "PASS"})\n    assert pass_test_has_execution(tmp_path, {"status": "PASS", "execution": {"command_or_workflow": "pytest", "commit_sha": sha, "result": "PASS", "evidence": ["ci"]}})\n''',
)

replace_once(
    "tests/governance/test_review0029_branches.py",
    '''def test_authority_helper_branches(tmp_path: Path) -> None:\n    policy = {\n''',
    '''def test_authority_helper_branches(tmp_path: Path) -> None:\n    run(tmp_path, "init")\n    run(tmp_path, "remote", "add", "origin", "https://github.com/owner/repo.git")\n    policy = {\n''',
)

replace_once(
    "tests/governance/test_review0029_branches.py",
    '''"authority_evidence_ref": "https://api.github.com/repos/owner/repo",''',
    '''"authority_evidence_ref": "https://api.github.com/repos/owner/repo/collaborators/owner/permission",''',
)

Path("tests/governance/test_review0030_findings.py").write_text(r'''from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import tools.governance.change_guard as cg
from tools.governance.strict_contracts import (
    external_review_import_finalized,
    git_commit_reachable,
    pass_test_has_execution,
    repository_owner_permission_ref_valid,
)
from tools.governance.validate_repo import Record, Validator


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def git(root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if check and proc.returncode:
        raise RuntimeError(proc.stderr)
    return proc.stdout.strip()


def init_git(root: Path, remote: str = "https://github.com/owner/repo.git") -> str:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "test")
    git(root, "remote", "add", "origin", remote)
    (root / "README.md").write_text("base\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", "base")
    return git(root, "rev-parse", "HEAD")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def content_identity_policy() -> dict:
    return {
        "schemes": {
            "REQUIREMENT_NORMATIVE_V1": {
                "algorithm": "SHA256",
                "encoding": "UTF-8",
                "canonicalization": {
                    "standard": "RFC_8785_JSON_CANONICALIZATION_SCHEME",
                    "encoding": "UTF-8",
                },
                "included_fields": ["id", "title", "normative_statement", "scope", "verification.method"],
            }
        }
    }


def test_jcs_serializer_matches_rfc8785_boundary_forms() -> None:
    assert cg.jcs_serialize(1e-6) == "0.000001"
    assert cg.jcs_serialize(1e-7) == "1e-7"
    assert cg.jcs_serialize(1e20) == "100000000000000000000"
    assert cg.jcs_serialize(1e21) == "1e+21"
    assert cg.jcs_serialize(-0.0) == "0"
    assert cg.jcs_serialize({"😀": 1, "\ue000": 2}) == '{"😀":1,"\ue000":2}'
    with pytest.raises(ValueError):
        cg.jcs_serialize(float("inf"))
    with pytest.raises(ValueError):
        cg.jcs_serialize(9007199254740992)
    with pytest.raises(ValueError):
        cg.jcs_serialize("\ud800")


def test_requirement_digest_recomputed_from_normative_projection(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/content-identity.yaml", content_identity_policy())
    req = {
        "id": "REQ-1",
        "title": "Atomic",
        "normative_statement": "must hold",
        "scope": {"in": ["x"], "out": []},
        "verification": {"method": "cold read"},
        "content_identity": {"scheme": "REQUIREMENT_NORMATIVE_V1", "digest": "sha256:" + "0" * 64},
    }
    dump(tmp_path / "registry/requirements/REQ-1.yaml", req)
    first = commit(tmp_path, "requirement")
    computed = cg.recompute_requirement_digest(tmp_path, first, req)
    assert computed is not None
    req["content_identity"]["digest"] = computed
    dump(tmp_path / "registry/requirements/REQ-1.yaml", req)
    bound = commit(tmp_path, "bind digest")
    assert cg.requirement_digest_matches(tmp_path, bound, req)

    req["normative_statement"] = "changed"
    dump(tmp_path / "registry/requirements/REQ-1.yaml", req)
    tampered = commit(tmp_path, "tamper")
    assert not cg.requirement_digest_matches(tmp_path, tampered, req)

    broken = dict(req)
    broken["verification"] = {}
    assert cg.recompute_requirement_digest(tmp_path, tampered, broken) is None


def risk_machine() -> dict:
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


def authority_policy() -> dict:
    return {
        "version": 1,
        "vocabulary": {
            "authority_roles": {
                "REPOSITORY_OWNER": {
                    "allowed_evidence_types": ["GITHUB_REPOSITORY_OWNER_PERMISSION"]
                }
            }
        },
        "risk_acceptance": {
            "default_matrix": {"A3": {"HIGH": ["REPOSITORY_OWNER"]}},
            "category_overrides": {"SECURITY": {"A3": {"HIGH": ["REPOSITORY_OWNER"]}}},
        },
    }


def accepted_risk(ref: str) -> dict:
    return {
        "id": "RISK-1",
        "status": "ACCEPTED",
        "category": "SECURITY",
        "scope": {"work_items": ["WORK-1"]},
        "assessment": {"impact": "HIGH"},
        "resolution": {
            "accepted": True,
            "accepted_by": "owner",
            "authority_role": "REPOSITORY_OWNER",
            "authority_evidence_type": "GITHUB_REPOSITORY_OWNER_PERMISSION",
            "authority_evidence_ref": ref,
            "authority_matrix_version": 1,
            "authority_rule_id": "RISK_CATEGORY:SECURITY:A3:HIGH",
            "acceptance_rationale": "bounded",
            "accepted_at": "2026-09-14",
            "review_condition": "revisit on scope change",
        },
    }


def test_risk_acceptance_requires_exact_matrix_authority_and_governed_repo(tmp_path: Path) -> None:
    init_git(tmp_path)
    dump(tmp_path / "registry/status-machines.yaml", risk_machine())
    dump(tmp_path / "registry/acceptance-authority.yaml", authority_policy())
    dump(tmp_path / "registry/work-items/WORK-1.yaml", {"id": "WORK-1", "assurance": {"level": "A3"}})
    ref = "https://api.github.com/repos/owner/repo/collaborators/owner/permission"
    risk = accepted_risk(ref)
    dump(tmp_path / "registry/risks/RISK-1.yaml", risk)
    sha = commit(tmp_path, "accepted risk")
    assert cg.risk_acceptance_satisfied(tmp_path, sha, risk)

    wrong_repo = accepted_risk("https://api.github.com/repos/owner/other/collaborators/owner/permission")
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, wrong_repo)
    missing = accepted_risk(ref)
    missing["resolution"]["acceptance_rationale"] = ""
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, missing)
    wrong_rule = accepted_risk(ref)
    wrong_rule["resolution"]["authority_rule_id"] = "RISK_DEFAULT:A3:HIGH"
    assert not cg.risk_acceptance_satisfied(tmp_path, sha, wrong_rule)


def test_repository_owner_permission_ref_is_bound_to_governed_repo_and_actor(tmp_path: Path) -> None:
    init_git(tmp_path)
    good = "https://api.github.com/repos/owner/repo/collaborators/alice/permission"
    assert repository_owner_permission_ref_valid(tmp_path, "alice", good)
    assert not repository_owner_permission_ref_valid(
        tmp_path, "alice", "https://api.github.com/repos/owner/other/collaborators/alice/permission"
    )
    assert not repository_owner_permission_ref_valid(tmp_path, "bob", good)


def test_external_review_import_must_be_bound_and_consumed(tmp_path: Path) -> None:
    init_git(tmp_path)
    import_sha = "a" * 40
    auth_sha = "b" * 40
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "artifact": {"commit_sha": "c" * 40},
        "reviewer": {"context_id": "ctx"},
        "outcome": "APPROVE",
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
            "authorization_commit": auth_sha,
            "source_review_id": "SRC",
            "source_submitted_at": "2026-09-14T00:00:00Z",
            "import_commit": import_sha,
        },
    }
    auth = {
        "record_id": "REVIEW-1",
        "imported_status": "COMPLETE",
        "artifact_commit_sha": "c" * 40,
        "source_review_id": "SRC",
        "source_submitted_at": "2026-09-14T00:00:00Z",
        "reviewer_context_id": "ctx",
        "expected_outcome": "APPROVE",
        "one_shot": True,
        "consumed_by_commit": import_sha,
    }
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    assert external_review_import_finalized(tmp_path, "REVIEW-1", review)

    auth["consumed_by_commit"] = None
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    assert not external_review_import_finalized(tmp_path, "REVIEW-1", review)

    no_import = dict(review)
    no_import.pop("external_import")
    assert external_review_import_finalized(tmp_path, "REVIEW-1", no_import)


def test_pass_test_execution_revision_must_exist_and_be_reachable(tmp_path: Path) -> None:
    base = init_git(tmp_path)
    test = {
        "status": "PASS",
        "execution": {
            "command_or_workflow": "pytest",
            "commit_sha": base,
            "result": "PASS",
            "evidence": ["ci"],
        },
    }
    assert pass_test_has_execution(tmp_path, test)
    assert git_commit_reachable(tmp_path, base)

    fake = yaml.safe_load(yaml.safe_dump(test))
    fake["execution"]["commit_sha"] = "f" * 40
    assert not pass_test_has_execution(tmp_path, fake)
    assert not git_commit_reachable(tmp_path, "f" * 40)


def test_closed_review_never_contributes_completion_hats_or_independence(tmp_path: Path) -> None:
    validator = Validator(tmp_path)
    review = Record(
        "reviews",
        tmp_path / "registry/reviews/REVIEW-1.yaml",
        {
            "id": "REVIEW-1",
            "status": "CLOSED",
            "outcome": "APPROVE",
            "roles": ["SECURITY"],
            "reviewer": {"independence_level": "L3"},
            "findings": [],
        },
    )
    validator.by_id["REVIEW-1"] = review
    work = Record(
        "work-items",
        tmp_path / "registry/work-items/WORK-1.yaml",
        {
            "id": "WORK-1",
            "review_plan": {
                "required_hats": ["SECURITY"],
                "independence_level": "L2",
                "completed_reviews": ["REVIEW-1"],
            },
        },
    )
    validator.validate_review_evidence(work)
    messages = [issue.message for issue in validator.issues]
    assert any("not COMPLETE approval evidence" in message for message in messages)
    assert any("miss required hats" in message for message in messages)
    assert any("independence L2" in message for message in messages)
''', encoding="utf-8")

replace_once(
    "scripts/governance_mutation_smoke.py",
    '''        'if data.get("status") not in {"COMPLETE", "CLOSED"}:',\n''',
    '''        'if data.get("status") != "COMPLETE":',\n''',
)
replace_once(
    "scripts/governance_mutation_smoke.py",
    '''        'if test is None or not pass_test_has_execution(test):',\n''',
    '''        'if test is None or not pass_test_has_execution(root, test):',\n''',
)

anchor = '''    "endpoint-merge-base": (\n        "tools/governance/change_guard.py",\n        "endpoint_files = endpoint_changed_files(root, base, head)",\n        "endpoint_files = changed_files(root, base, head)",\n    ),\n'''
block = r'''    "requirement-digest-recompute": (
        "tools/governance/change_guard.py",
        "if not requirement_digest_matches(root, sha, requirement):",
        "if False:",
    ),
    "risk-acceptance-precondition": (
        "tools/governance/change_guard.py",
        'if kind == "risks" and before != "ACCEPTED" and after == "ACCEPTED" and not risk_acceptance_satisfied(root, sha, current):',
        'if False:',
    ),
    "governed-repository-authority": (
        "tools/governance/strict_contracts.py",
        "return repository_owner_permission_ref_valid(root, actor, ref)",
        "return True",
    ),
    "external-review-import-finalized": (
        "tools/governance/strict_contracts.py",
        "if not external_review_import_finalized(root, rid, review):",
        "if False:",
    ),
    "pass-test-real-revision": (
        "tools/governance/strict_contracts.py",
        "and git_commit_reachable(root, commit_sha)",
        "and True",
    ),
'''
insert_once("scripts/governance_mutation_smoke.py", anchor, block, before=False)

replace_once(
    "registry/work-items/WORK-0002.yaml",
    '''  rationale: Fresh exact-SHA L2 REVIEW-0029 found six additional lifecycle/evidence/authority/freshness/merge-base defects after the v10 integration;\n    owner authorizes correcting those defects without changing product scope.\n''',
    '''  rationale: Fresh exact-SHA L2 REVIEW-0029 and REVIEW-0030 found additional lifecycle/evidence/authority/freshness/merge-base defects after the v10 integration; owner authorizes correcting those defects without changing product scope.\n''',
)

anchor = '''  - 'REVIEW-0029/F-6 / P2: endpoint scope uses PR merge-base semantics while commit-edge validation uses true parents.'\n'''
block = r'''  - 'REVIEW-0030/F-1 / P1: risk transitions into ACCEPTED require the complete canonical authority/precondition contract.'
  - 'REVIEW-0030/F-2 / P1: REQUIREMENT_NORMATIVE_V1 digest is recomputed from RFC 8785/JCS canonical bytes before acceptance.'
  - 'REVIEW-0030/F-3 / P1: repository-owner authority proof is bound to the governed MONDE repository and accepted actor.'
  - 'REVIEW-0030/F-4 / P1: preauthorized external reviews are ineligible until import binding and authorization consumption agree.'
  - 'REVIEW-0030/F-5 / P1: PASS TEST execution revisions must name real reachable Git commits.'
  - 'REVIEW-0030/F-6 / P1: CLOSED reviews never satisfy completion or contribute hats/independence.'
'''
insert_once("registry/work-items/WORK-0002.yaml", anchor, block, before=False)

print("REVIEW-0030 corrective patch prepared")
