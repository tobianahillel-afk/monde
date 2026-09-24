from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .proof_contracts import (
    requirement_normative_digest,
    repository_owner_evidence_valid,
    resolve_risk_authority_rule,
)

META_PATH_PREFIXES = (
    ".github/",
    "tools/governance/",
    "schemas/registry/",
    "scripts/governance_",
    "registry/integration-provenance.yaml",
)
ADMIN_PATH_PREFIXES = ("registry/reviews/", "registry/progress/", "PROJECT_STATE.md")
FULL_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
SEMANTIC_WORK_KEYS = {
    "purpose", "scope", "acceptance_criteria", "requirements", "assumptions", "risks",
    "assurance", "depends_on", "reuses", "contracts", "impact_analysis", "required_tests",
    "scientific_validation", "risk", "rollback", "affected_paths",
}
REVIEW_PLAN_ADMIN_KEYS = {"completed_reviews", "open_findings"}
GUARD_PATH = "tools/governance/change_guard.py"
ACTIVE_WORK_STATUSES = {"READY", "IN_PROGRESS", "PARTIAL", "BLOCKED", "IN_REVIEW"}
REGISTRY_ID = re.compile(r"\b(?:WORK|CAP|REQ|ASM|RISK|REVIEW|TEST|EXP|DEP)-\d+\b")
SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{50,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class ChangeFinding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False, errors="replace"
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout


def changed_files(root: Path, base: str, head: str) -> list[str]:
    return [x for x in git(root, "diff", "--name-only", f"{base}..{head}").splitlines() if x]


def endpoint_changed_files(root: Path, base: str, head: str) -> list[str]:
    merge_base = git(root, "merge-base", base, head).strip()
    if not merge_base:
        raise RuntimeError("no merge base for endpoint comparison")
    return changed_files(root, merge_base, head)


def show_yaml(root: Path, sha: str, path: str) -> dict[str, Any] | None:
    try:
        text = git(root, "show", f"{sha}:{path}")
    except RuntimeError:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def file_exists_at(root: Path, sha: str, path: str) -> bool:
    try:
        git(root, "cat-file", "-e", f"{sha}:{path}")
        return True
    except RuntimeError:
        return False


def commit_exists(root: Path, sha: str) -> bool:
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


def blob_sha_at(root: Path, sha: str, path: str) -> str | None:
    try:
        value = git(root, "rev-parse", f"{sha}:{path}").strip()
    except RuntimeError:
        return None
    return value if FULL_COMMIT_SHA.fullmatch(value) else None


def historical_malformed_yaml_allowed(
    root: Path,
    path: str,
    malformed_sha: str,
    head: str,
    repaired_sha: str | None = None,
) -> bool:
    provenance = show_yaml(root, head, "registry/integration-provenance.yaml") or {}
    for entry in provenance.get("historical_malformed_yaml", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("path") != path:
            continue
        origin = str(entry.get("malformed_commit_sha") or "")
        repair = str(entry.get("repaired_commit_sha") or "")
        malformed_blob = str(entry.get("malformed_blob_sha") or "")
        repaired_blob = str(entry.get("repaired_blob_sha") or "")
        if repaired_sha is not None and repair != repaired_sha:
            continue
        if not all(FULL_COMMIT_SHA.fullmatch(value) for value in (origin, malformed_sha, repair, malformed_blob, repaired_blob)):
            continue
        if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:
            continue
        if blob_sha_at(root, origin, path) != malformed_blob or blob_sha_at(root, malformed_sha, path) != malformed_blob:
            continue
        if blob_sha_at(root, repair, path) != repaired_blob:
            continue
        if not is_ancestor(root, origin, malformed_sha) or not is_ancestor(root, malformed_sha, repair) or not is_ancestor(root, repair, head):
            continue
        return True
    return False


def registry_kind(path: str) -> str | None:
    parts = Path(path).parts
    if len(parts) >= 3 and parts[0] == "registry" and path.endswith(".yaml") and not Path(path).name.startswith("_"):
        return parts[1]
    return None


def acceptance_contract(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    out = []
    for item in value:
        if isinstance(item, dict):
            out.append({k: item.get(k) for k in ("id", "description") if k in item})
        else:
            out.append(item)
    return out


def review_plan_contract(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {k: value[k] for k in sorted(value) if k not in REVIEW_PLAN_ADMIN_KEYS}


def semantic_projection(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    out = {k: data.get(k) for k in sorted(SEMANTIC_WORK_KEYS) if k in data}
    if "acceptance_criteria" in out:
        out["acceptance_criteria"] = acceptance_contract(out["acceptance_criteria"])
    if "review_plan" in data:
        out["review_plan"] = review_plan_contract(data.get("review_plan"))
    return out


def test_semantic_projection(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    keys = ("name", "type", "protects", "cases", "location", "environment", "execution_definition", "execution_evidence_policy")
    out = {key: data.get(key) for key in keys if key in data}
    execution = data.get("execution")
    if isinstance(execution, dict) and "command_or_workflow" in execution:
        out["execution"] = {"command_or_workflow": execution.get("command_or_workflow")}
    return out


def canonical_machine_spec(root: Path, sha: str, kind: str) -> dict[str, Any]:
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


def _values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


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
    if kind == "tests":
        rid, status = current.get("id"), current.get("status")
        policy = canonical_machine_spec(root, policy_sha, kind)
        return any(
            isinstance(exc, dict)
            and exc.get("record_id") == rid
            and exc.get("imported_status") == status
            and exc.get("import_commit") == materialize_sha
            for exc in policy.get("historical_import_exceptions", []) or []
        )
    return historical_import_allowed(root, parent_sha, materialize_sha, policy_sha, kind, current)


def review_requirement_revision_valid(root: Path, acceptance_sha: str, requirement_id: str, digest: str, review: dict[str, Any]) -> bool:
    reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or ""))
    if not commit_exists(root, reviewed_sha) or not is_ancestor(root, reviewed_sha, acceptance_sha):
        return False
    reviewed_requirement = show_yaml(root, reviewed_sha, f"registry/requirements/{requirement_id}.yaml") or {}
    if reviewed_requirement.get("status") != "PROPOSED":
        return False
    identity_policy = show_yaml(root, reviewed_sha, "registry/content-identity.yaml") or {}
    return requirement_normative_digest(root, reviewed_requirement, identity_policy) == digest


def test_external_execution_transition_allowed(
    root: Path,
    parent_sha: str,
    transition_sha: str,
    previous: dict[str, Any],
    current: dict[str, Any],
) -> bool:
    ext = current.get("external_import")
    if not isinstance(ext, dict) or ext.get("import_commit") is not None:
        return False
    auth_source = str(ext.get("authorization_source") or "")
    match = re.fullmatch(r"registry/status-machines\.yaml@([0-9a-f]{40})#registry_machines\.tests\.external_execution_import_authorizations\.[A-Za-z0-9_-]+", auth_source)
    if match is None:
        return False
    auth_commit = match.group(1)
    if not commit_exists(root, auth_commit) or not is_ancestor(root, auth_commit, parent_sha):
        return False
    spec = canonical_machine_spec(root, auth_commit, "tests")
    cold = current.get("acceptance_cold_read") or {}
    source = cold.get("source") or {}
    executor = cold.get("executor") or {}
    execution = current.get("execution") or {}
    for auth in spec.get("external_execution_import_authorizations", []) or []:
        if not isinstance(auth, dict):
            continue
        if (
            auth.get("record_id") == current.get("id")
            and previous.get("id") == current.get("id")
            and auth.get("from_status") == previous.get("status")
            and auth.get("imported_status") == current.get("status")
            and auth.get("execution_commit_sha") == execution.get("commit_sha")
            and auth.get("source_id") == source.get("source_id")
            and auth.get("source_submitted_at") == source.get("submitted_at")
            and auth.get("executor_context_id") == executor.get("context_id")
            and auth.get("expected_result") == execution.get("result")
            and auth.get("one_shot") is True
            and auth.get("consumed_by_commit") is None
        ):
            return True
    return False


def requirement_acceptance_satisfied(root: Path, sha: str, requirement: dict[str, Any]) -> bool:
    rid = requirement.get("id")
    ident = requirement.get("content_identity") or {}
    digest = ident.get("digest")
    if ident.get("scheme") != "REQUIREMENT_NORMATIVE_V1" or not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        return False
    identity_policy = show_yaml(root, sha, "registry/content-identity.yaml") or {}
    if requirement_normative_digest(root, requirement, identity_policy) != digest:
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
            and review_requirement_revision_valid(root, sha, str(rid), digest, review)
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


def risk_acceptance_satisfied(root: Path, sha: str, risk: dict[str, Any]) -> bool:
    spec = canonical_machine_spec(root, sha, "risks")
    preconditions = spec.get("acceptance_preconditions") or {}
    resolution = risk.get("resolution") or {}
    required_fields = preconditions.get("required_fields") or []
    if not isinstance(resolution, dict) or resolution.get("accepted") is not True:
        return False
    for dotted in required_fields:
        if not isinstance(dotted, str) or not dotted.startswith("resolution."):
            return False
        key = dotted.split(".", 1)[1]
        if resolution.get(key) in (None, ""):
            return False

    policy = show_yaml(root, sha, "registry/acceptance-authority.yaml") or {}
    resolved = resolve_risk_authority_rule(
        root,
        risk,
        policy,
        lambda path: show_yaml(root, sha, path),
    )
    if resolved is None:
        return False
    rule_id, allowed_roles = resolved
    role = resolution.get("authority_role")
    evidence_type = resolution.get("authority_evidence_type")
    role_spec = (((policy.get("vocabulary") or {}).get("authority_roles") or {}).get(role) or {})
    if role not in allowed_roles or evidence_type not in (role_spec.get("allowed_evidence_types") or []):
        return False
    if resolution.get("authority_matrix_version") != policy.get("version") or resolution.get("authority_rule_id") != rule_id:
        return False

    evidence = {
        "accepted_by": resolution.get("accepted_by"),
        "authority_evidence_type": evidence_type,
        "authority_evidence_ref": resolution.get("authority_evidence_ref"),
    }
    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":
        return repository_owner_evidence_valid(evidence, policy)

    ref = str(resolution.get("authority_evidence_ref") or "")
    scope = risk.get("scope") or {}
    work_items = scope.get("work_items") or []
    if evidence_type == "WORK_ITEM_OWNER_BINDING":
        if len(work_items) != 1 or ref != f"registry/work-items/{work_items[0]}.yaml":
            return False
        work = show_yaml(root, sha, ref) or {}
        return work.get("owner") == resolution.get("accepted_by")

    if evidence_type in {"GOVERNANCE_DELEGATION", "GOVERNANCE_SECURITY_DELEGATION", "EXPLICIT_REPOSITORY_OWNER_DECISION"}:
        if len(work_items) != 1 or not ref.startswith("registry/"):
            return False
        authority_record = show_yaml(root, sha, ref) or {}
        actor = str(resolution.get("accepted_by") or "")
        actor_values = _values(authority_record.get("actor")) | _values(authority_record.get("delegate")) | _values(authority_record.get("accepted_by")) | _values(authority_record.get("owner"))
        role_values = _values(authority_record.get("role")) | _values(authority_record.get("authority_role")) | _values(authority_record.get("roles")) | _values(authority_record.get("authority_roles"))
        authority_scope = authority_record.get("scope") or {}
        if not isinstance(authority_scope, dict):
            return False
        work_scope = _values(authority_scope.get("work_items"))
        repo_scope = _values(authority_scope.get("repositories")) | _values(authority_scope.get("repository")) | _values(authority_scope.get("full_name"))
        governed = policy.get("governed_repository") or {}
        return bool(
            actor in actor_values
            and str(role or "") in role_values
            and (str(work_items[0]) in work_scope or str(governed.get("full_name") or "") in repo_scope)
        )
    return False


def commit_parents(root: Path, sha: str) -> list[str]:
    return git(root, "show", "-s", "--format=%P", sha).split()


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root, text=True, capture_output=True, check=False,
    )
    return proc.returncode == 0


def is_first_parent_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if not FULL_COMMIT_SHA.fullmatch(str(ancestor or "")) or not FULL_COMMIT_SHA.fullmatch(str(descendant or "")):
        return False
    return ancestor in {
        sha
        for sha in git(root, "rev-list", "--first-parent", descendant).splitlines()
        if sha
    }


def comparison_parent(root: Path, base: str, sha: str) -> str:
    parents = commit_parents(root, sha)
    if base in parents:
        return base
    inherited_base_side = [parent for parent in parents if is_ancestor(root, parent, base)]
    if inherited_base_side:
        return inherited_base_side[0]
    base_descendants = [parent for parent in parents if is_ancestor(root, base, parent)]
    return base_descendants[0] if base_descendants else parents[0]


def inherited_merge_record_allowed(
    root: Path,
    base: str,
    previous_sha: str,
    sha: str,
    path: str,
    current: dict[str, Any],
    exclusive_commits: set[str],
) -> bool:
    parents = commit_parents(root, sha)
    if len(parents) < 2:
        return False
    current_blob = blob_sha_at(root, sha, path)
    record_id = current.get("id")
    if current_blob is None or not isinstance(record_id, str):
        return False
    for parent in parents:
        if parent == previous_sha or blob_sha_at(root, parent, path) != current_blob:
            continue
        # comparison_parent() already selects a parent inherited by the
        # current base when one exists, so any remaining matching parent is source
        # history. Only reuse it when that source commit is part of this exact
        # base..head traversal and already carries the guard; otherwise fail closed.
        if parent in exclusive_commits and file_exists_at(root, parent, GUARD_PATH):
            return True
    return False


def pr_commit_edges(root: Path, base: str, head: str, require_guard: bool) -> tuple[list[str], list[tuple[str, str]]]:
    commits = [x for x in git(root, "rev-list", "--reverse", "--topo-order", f"{base}..{head}").splitlines() if x]
    edges: list[tuple[str, str]] = []
    for sha in commits:
        if require_guard and not file_exists_at(root, sha, GUARD_PATH):
            continue
        edges.append((comparison_parent(root, base, sha), sha))
    return commits, edges


def paths_across_edges(root: Path, edges: list[tuple[str, str]]) -> list[str]:
    paths: set[str] = set()
    for before, after in edges:
        paths.update(changed_files(root, before, after))
    return sorted(paths)


def path_is_declared(path: str, declared: list[Any]) -> bool:
    for raw in declared:
        if not isinstance(raw, str):
            continue
        if raw.endswith("/") and path.startswith(raw):
            return True
        if path == raw:
            return True
    return False


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def work_scope_paths(work: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("read_before", "affected_docs", "affected_schemas", "affected_paths"):
        values = work.get(key, []) or []
        if isinstance(values, list):
            paths.extend(x for x in values if isinstance(x, str))
    plan = work.get("implementation_plan") or {}
    if isinstance(plan, dict):
        for task in plan.get("tasks", []) or []:
            if not isinstance(task, dict):
                continue
            expected = task.get("expected_files", []) or []
            if isinstance(expected, list):
                paths.extend(x for x in expected if isinstance(x, str))
    return paths


def work_referenced_ids(work: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for text in iter_strings(semantic_projection(work)):
        refs.update(REGISTRY_ID.findall(text))
    wid = work.get("id")
    if isinstance(wid, str):
        refs.discard(wid)
    return refs


def registry_id_for_change(root: Path, reviewed: str, head: str, path: str) -> str | None:
    current = show_yaml(root, head, path) or show_yaml(root, reviewed, path)
    if not current:
        return None
    rid = current.get("id")
    return rid if isinstance(rid, str) else None


def change_relevant_to_work(
    root: Path,
    work_path: str,
    work: dict[str, Any],
    reviewed: str,
    head: str,
    file_path: str,
) -> bool:
    if file_path.startswith(ADMIN_PATH_PREFIXES):
        return False
    if file_path.startswith("registry/tests/"):
        changed_id = registry_id_for_change(root, reviewed, head, file_path)
        if changed_id not in work_referenced_ids(work):
            return False
        old_test = show_yaml(root, reviewed, file_path)
        new_test = show_yaml(root, head, file_path)
        return test_semantic_projection(old_test) != test_semantic_projection(new_test)
    if file_path == work_path:
        old_work = show_yaml(root, reviewed, work_path)
        new_work = show_yaml(root, head, work_path)
        return semantic_projection(old_work) != semantic_projection(new_work)

    declarations = work_scope_paths(work)
    if path_is_declared(file_path, declarations):
        return True

    refs = work_referenced_ids(work)
    changed_id = registry_id_for_change(root, reviewed, head, file_path)
    if changed_id is not None and changed_id in refs:
        return True

    # Legacy records may not yet declare scope paths/references. Preserve fail-closed
    # behavior for those records instead of silently treating all later changes as irrelevant.
    return not declarations and not refs


def commit_added_lines(root: Path, sha: str) -> str:
    patch = git(root, "show", "--format=", "--no-ext-diff", "--unified=0", sha)
    return "\n".join(
        line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )


def validate(root: Path, base: str, head: str) -> list[ChangeFinding]:
    out: list[ChangeFinding] = []
    endpoint_files = endpoint_changed_files(root, base, head)
    base_has_guard = file_exists_at(root, base, GUARD_PATH)

    for path in endpoint_files:
        kind = registry_kind(path)
        if not kind:
            continue
        old = show_yaml(root, base, path)
        new = show_yaml(root, head, path)
        if old and not new:
            out.append(ChangeFinding(path, "RECORD_DELETE", "published registry records must be superseded/deprecated, not deleted"))
            continue
        if not old or not new:
            continue
        if old.get("id") != new.get("id"):
            out.append(ChangeFinding(path, "ID_IMMUTABLE", "registry id changed across base→head"))
        before = old.get("status")
        if kind == "work-items" and before in ACTIVE_WORK_STATUSES:
            if semantic_projection(old) != semantic_projection(new):
                scope_change = new.get("scope_change") or {}
                if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                    out.append(ChangeFinding(path, "SCOPE_DRIFT", "semantic scope/AC/review/contracts changed after READY without approved scope_change rationale"))

    exclusive_commits, edges = pr_commit_edges(root, base, head, require_guard=not base_has_guard)
    exclusive_commit_set = set(exclusive_commits)
    all_commits = [base] + exclusive_commits
    sequence_files = paths_across_edges(root, edges) if edges else endpoint_files

    for previous_sha, sha in edges:
        for path in changed_files(root, previous_sha, sha):
            kind = registry_kind(path)
            if not kind or kind == "progress":
                continue
            previous = show_yaml(root, previous_sha, path)
            current = show_yaml(root, sha, path)
            if current and inherited_merge_record_allowed(
                root, base, previous_sha, sha, path, current, exclusive_commit_set
            ):
                continue
            if previous and current is None:
                if file_exists_at(root, sha, path) and historical_malformed_yaml_allowed(root, path, sha, head):
                    continue
                out.append(ChangeFinding(path, "RECORD_DELETE", f"published registry record deleted at {sha[:12]}"))
                continue
            if previous is None and current:
                if file_exists_at(root, previous_sha, path) and historical_malformed_yaml_allowed(root, path, previous_sha, head, repaired_sha=sha):
                    continue
                if not record_introduction_allowed(root, previous_sha, sha, head, kind, current):
                    out.append(ChangeFinding(path, "STATE_INITIAL", f"new {kind} record {current.get('id')} materialized as {current.get('status')!r} without canonical initial state or exact import exception at {sha[:12]}"))
                continue
            if previous and current:
                if previous.get("id") != current.get("id"):
                    out.append(ChangeFinding(path, "ID_IMMUTABLE", f"registry id changed at {sha[:12]}"))
                before, after = previous.get("status"), current.get("status")
                allowed = canonical_transitions(root, sha, kind)
                external_test_import = bool(
                    kind == "tests"
                    and before != after
                    and test_external_execution_transition_allowed(root, previous_sha, sha, previous, current)
                )
                if before != after and after not in allowed.get(str(before), set()) and not external_test_import:
                    out.append(ChangeFinding(path, "STATE_TRANSITION", f"invalid {kind} transition {before} -> {after} at {sha[:12]}"))
                if kind == "requirements" and before == "PROPOSED" and after == "ACCEPTED" and not requirement_acceptance_satisfied(root, sha, current):
                    out.append(ChangeFinding(path, "ACCEPTANCE_PRECONDITION", f"requirement {current.get('id')} accepted without qualifying content-bound review and cold-read evidence at {sha[:12]}"))
                if kind == "risks" and before != "ACCEPTED" and after == "ACCEPTED" and not risk_acceptance_satisfied(root, sha, current):
                    out.append(ChangeFinding(path, "RISK_ACCEPTANCE_PRECONDITION", f"risk {current.get('id')} accepted without canonical authority/precondition evidence at {sha[:12]}"))
                if kind == "work-items" and before in ACTIVE_WORK_STATUSES and semantic_projection(previous) != semantic_projection(current):
                    scope_change = current.get("scope_change") or {}
                    if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                        out.append(ChangeFinding(path, "SCOPE_DRIFT", f"semantic scope/AC/review/contracts changed at {sha[:12]} without approved scope_change rationale"))

    meta_paths = [path for path in sequence_files if path.startswith(META_PATH_PREFIXES)]
    if meta_paths:
        work_paths = [
            path for path in sequence_files
            if path.startswith("registry/work-items/") and path.endswith(".yaml") and not Path(path).name.startswith("_")
        ]
        qualifying: list[dict[str, Any]] = []
        for path in work_paths:
            work = show_yaml(root, head, path)
            if not work:
                continue
            if work.get("status") not in ACTIVE_WORK_STATUSES:
                continue
            if (work.get("assurance") or {}).get("level") not in {"A3", "A4"}:
                continue
            qualifying.append(work)
        for meta_path in meta_paths:
            if not any(path_is_declared(meta_path, work.get("affected_paths", []) or []) for work in qualifying):
                out.append(ChangeFinding(meta_path, "META_GOVERNANCE", "meta-governance change requires an active changed A3/A4 work item whose affected_paths covers this path"))

    for sha in all_commits[1:]:
        added = commit_added_lines(root, sha)
        for pattern in SECRET_PATTERNS:
            if pattern.search(added):
                out.append(ChangeFinding(sha[:12], "SECRET_HISTORY", "high-confidence secret/private-key pattern introduced in PR commit history"))
                break

    work_paths = [
        x for x in git(root, "ls-tree", "-r", "--name-only", head, "registry/work-items").splitlines()
        if x.endswith(".yaml") and not Path(x).name.startswith("_")
    ]
    endpoint_set = set(endpoint_files)
    for path in work_paths:
        work = show_yaml(root, head, path) or {}
        if work.get("status") in {"DONE", "DEPRECATED", "CANCELLED"} and path not in endpoint_set:
            continue
        plan = work.get("review_plan") or {}
        for rid in plan.get("completed_reviews", []) or []:
            review_path = f"registry/reviews/{rid}.yaml"
            review = show_yaml(root, head, review_path)
            if not review or review.get("status") not in {"COMPLETE", "CLOSED"}:
                continue
            reviewed = str((review.get("artifact") or {}).get("commit_sha") or "")
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
            # A completed review inherited through a non-first-parent merge
            # remains valid evidence for that integrated predecessor, but it is
            # not a review of the current branch delta. Only reviews on the
            # current head's first-parent lineage are freshness authorities for
            # subsequent first-parent work.
            if not is_first_parent_ancestor(root, reviewed, head):
                continue
            later = changed_files(root, reviewed, head)
            substantive = [
                file_path
                for file_path in later
                if file_path in endpoint_set
                and change_relevant_to_work(root, path, work, reviewed, head, file_path)
            ]
            if substantive:
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", f"review {rid} predates substantive changes: {', '.join(substantive[:8])}"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    try:
        findings = validate(Path(args.root).resolve(), args.base, args.head)
    except RuntimeError as exc:
        print(f"ERROR CHANGE_GUARD {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(x) for x in findings], indent=2), encoding="utf-8")
    print(f"MONDE change guard: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
