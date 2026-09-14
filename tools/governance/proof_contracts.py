from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

import rfc8785
import yaml

FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


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


def git_commit_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if not git_commit_exists(root, ancestor) or not git_commit_exists(root, descendant):
        return False
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return proc.returncode == 0


def current_head(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and FULL_COMMIT_SHA.fullmatch(value) else None


def pass_test_execution_revision_valid(root: Path, test: dict[str, Any], head: str | None = None) -> bool:
    execution = test.get("execution") or {}
    sha = str(execution.get("commit_sha") or "")
    if not git_commit_exists(root, sha):
        return False
    target = head or current_head(root)
    return bool(target and git_commit_is_ancestor(root, sha, target))


def _copy_nested_path(source: dict[str, Any], target: dict[str, Any], dotted_path: str) -> bool:
    parts = dotted_path.split(".")
    current: Any = source
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    destination = target
    for part in parts[:-1]:
        child = destination.get(part)
        if child is None:
            child = {}
            destination[part] = child
        if not isinstance(child, dict):
            return False
        destination = child
    destination[parts[-1]] = current
    return True


def requirement_normative_digest(
    root: Path,
    requirement: dict[str, Any],
    identity_policy: dict[str, Any] | None = None,
) -> str | None:
    policy = identity_policy or load_mapping(root / "registry/content-identity.yaml")
    scheme = ((policy.get("schemes") or {}).get("REQUIREMENT_NORMATIVE_V1") or {})
    if scheme.get("algorithm") != "SHA256":
        return None
    canonicalization = scheme.get("canonicalization") or {}
    if canonicalization.get("standard") != "RFC_8785_JSON_CANONICALIZATION_SCHEME":
        return None
    included = scheme.get("included_fields") or []
    if not isinstance(included, list) or not included:
        return None
    projection: dict[str, Any] = {}
    for raw_path in included:
        if not isinstance(raw_path, str) or not raw_path or not _copy_nested_path(requirement, projection, raw_path):
            return None
    try:
        payload = rfc8785.dumps(projection)
    except (rfc8785.CanonicalizationError, TypeError, ValueError):
        return None
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def repository_owner_evidence_valid(
    acceptance: dict[str, Any],
    policy: dict[str, Any],
) -> bool:
    governed = policy.get("governed_repository") or {}
    return bool(
        acceptance.get("authority_evidence_type") == "GITHUB_REPOSITORY_OWNER_PERMISSION"
        and acceptance.get("authority_evidence_ref") == governed.get("metadata_url")
        and acceptance.get("accepted_by") == governed.get("owner_login")
        and isinstance(governed.get("full_name"), str)
        and bool(governed.get("full_name"))
        and isinstance(governed.get("permission_proof"), str)
        and bool(governed.get("permission_proof"))
    )


def review_external_import_finalized(
    review: dict[str, Any],
    machine: dict[str, Any],
) -> bool:
    ext = review.get("external_import")
    if ext is None:
        return True
    if not isinstance(ext, dict):
        return False
    if ext.get("mode") != "PREAUTHORIZED_EXTERNAL_COMPLETION":
        return False
    import_commit = str(ext.get("import_commit") or "")
    auth_commit = str(ext.get("authorization_commit") or "")
    if not FULL_COMMIT_SHA.fullmatch(import_commit) or not FULL_COMMIT_SHA.fullmatch(auth_commit):
        return False
    reviews_spec = ((machine.get("registry_machines") or {}).get("reviews") or {})
    authorizations = reviews_spec.get("external_import_authorizations") or []
    artifact = review.get("artifact") or {}
    reviewer = review.get("reviewer") or {}
    for auth in authorizations:
        if not isinstance(auth, dict):
            continue
        if (
            auth.get("record_id") == review.get("id")
            and auth.get("imported_status") == review.get("status")
            and auth.get("artifact_commit_sha") == artifact.get("commit_sha")
            and auth.get("source_review_id") == ext.get("source_review_id")
            and auth.get("reviewer_context_id") == reviewer.get("context_id")
            and auth.get("expected_outcome") == review.get("outcome")
            and auth.get("one_shot") is True
            and auth.get("consumed_by_commit") == import_commit
        ):
            return True
    return False


def resolve_risk_authority_rule(
    root: Path,
    risk: dict[str, Any],
    policy: dict[str, Any],
    record_loader: Callable[[str], dict[str, Any] | None],
) -> tuple[str, list[str]] | None:
    scope = risk.get("scope") or {}
    work_items = scope.get("work_items") or []
    if not isinstance(work_items, list) or len(work_items) != 1 or not isinstance(work_items[0], str):
        return None
    work = record_loader(f"registry/work-items/{work_items[0]}.yaml")
    if not isinstance(work, dict):
        return None
    assurance = str(((work.get("assurance") or {}).get("level") or ""))
    category = str(risk.get("category") or "")
    impact = str(((risk.get("assessment") or {}).get("impact") or ""))
    vocab = policy.get("vocabulary") or {}
    if assurance not in (vocab.get("assurance_levels") or []):
        return None
    if category not in (vocab.get("risk_categories") or []):
        return None
    if impact not in (vocab.get("risk_impacts") or []):
        return None
    risk_policy = policy.get("risk_acceptance") or {}
    override = ((((risk_policy.get("category_overrides") or {}).get(category) or {}).get(assurance) or {}).get(impact))
    if override is not None:
        return f"RISK_CATEGORY:{category}:{assurance}:{impact}", list(override or [])
    default = (((risk_policy.get("default_matrix") or {}).get(assurance) or {}).get(impact))
    if default is None:
        return None
    return f"RISK_DEFAULT:{assurance}:{impact}", list(default or [])
