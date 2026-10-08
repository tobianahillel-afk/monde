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

from tools.governance.proof_contracts import pass_test_execution_revision_valid

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
BLOCKING_SEVERITIES = {"R0_CRITICAL", "R1_BLOCKER", "R1_CRITICAL", "R2_MAJOR"}
DONE_TASK_RUN_STATES = {"DONE", "NOT_APPLICABLE"}
CHECKOUT_REF = "${{ inputs.head_sha }}"


@dataclass(frozen=True)
class Finding:
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


def git_ok(root: Path, *args: str) -> bool:
    return subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    ).returncode == 0


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def show_yaml(root: Path, sha: str, path: str) -> dict[str, Any] | None:
    try:
        raw = git(root, "show", f"{sha}:{path}")
        data = yaml.safe_load(raw)
    except (RuntimeError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def commit_parents(root: Path, sha: str) -> list[str]:
    return git(root, "show", "-s", "--format=%P", sha).split()


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return bool(FULL_SHA.fullmatch(ancestor) and FULL_SHA.fullmatch(descendant) and git_ok(root, "merge-base", "--is-ancestor", ancestor, descendant))


def changed_files(root: Path, before: str, after: str) -> list[str]:
    return [line for line in git(root, "diff", "--name-only", f"{before}..{after}").splitlines() if line]


def comparison_parent(root: Path, base: str, sha: str) -> str:
    parents = commit_parents(root, sha)
    if not parents:
        raise RuntimeError(f"commit {sha} has no parent")
    for parent in parents:
        if parent == base or is_ancestor(root, base, parent):
            return parent
    return parents[0]


def pr_edges(root: Path, base: str, head: str) -> list[tuple[str, str]]:
    merge_base = git(root, "merge-base", base, head).strip()
    commits = [line for line in git(root, "rev-list", "--reverse", "--topo-order", f"{merge_base}..{head}").splitlines() if line]
    return [(comparison_parent(root, merge_base, sha), sha) for sha in commits]


def first_status_commit(root: Path, path: str, status: str, head: str) -> str | None:
    commits = [line for line in git(root, "rev-list", "--reverse", "--topo-order", head, "--", path).splitlines() if line]
    for sha in commits:
        current = show_yaml(root, sha, path)
        if not current or current.get("status") != status:
            continue
        parents = commit_parents(root, sha)
        if not parents or all((show_yaml(root, parent, path) or {}).get("status") != status for parent in parents):
            return sha
    return None


def review_semantic_projection(review: dict[str, Any] | None) -> dict[str, Any]:
    if not review:
        return {}
    findings: list[dict[str, Any]] = []
    for finding in review.get("findings", []) or []:
        if isinstance(finding, dict):
            findings.append({
                key: finding.get(key)
                for key in ("id", "severity", "category", "disposition", "acceptance", "resolved_by")
                if key in finding
            })
    reviewer = review.get("reviewer") or {}
    return {
        "status": review.get("status"),
        "outcome": review.get("outcome"),
        "artifact": review.get("artifact"),
        "reviewer": {
            key: reviewer.get(key)
            for key in ("actor", "context_id", "independence_level")
            if key in reviewer
        } if isinstance(reviewer, dict) else reviewer,
        "roles": review.get("roles"),
        "scope": review.get("scope"),
        "findings": findings,
    }


def validate_completed_review_immutability(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in changed_files(root, before, after):
            if not path.startswith("registry/reviews/") or not path.endswith(".yaml"):
                continue
            previous = show_yaml(root, before, path)
            current = show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "COMPLETE":
                continue
            if review_semantic_projection(previous) != review_semantic_projection(current):
                out.append(Finding(path, "COMPLETE_REVIEW_IMMUTABLE", f"approval-bearing COMPLETE review semantics changed at {after[:12]}"))
    return out


def _values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def authority_evidence_valid(
    root: Path,
    work_id: str,
    acceptance: dict[str, Any],
    policy: dict[str, Any],
) -> bool:
    actor = str(acceptance.get("accepted_by") or "")
    role = str(acceptance.get("authority_role") or "")
    evidence_type = str(acceptance.get("authority_evidence_type") or "")
    ref = str(acceptance.get("authority_evidence_ref") or "")
    governed = policy.get("governed_repository") or {}
    if evidence_type == "GITHUB_REPOSITORY_OWNER_PERMISSION":
        proof_id = governed.get("permission_proof")
        proof = load_mapping(root / f"registry/tests/{proof_id}.yaml") if isinstance(proof_id, str) else {}
        return bool(
            ref == governed.get("metadata_url")
            and actor == governed.get("owner_login")
            and proof.get("id") == proof_id
            and proof.get("status") == "PASS"
        )
    if not ref.startswith("registry/"):
        return False
    record = load_mapping(root / ref)
    if not record:
        return False
    if evidence_type == "WORK_ITEM_OWNER_BINDING":
        return bool(ref == f"registry/work-items/{work_id}.yaml" and record.get("owner") == actor and role == "WORK_OWNER")
    if evidence_type not in {"GOVERNANCE_DELEGATION", "GOVERNANCE_SECURITY_DELEGATION", "EXPLICIT_REPOSITORY_OWNER_DECISION"}:
        return False
    actor_values = _values(record.get("actor")) | _values(record.get("delegate")) | _values(record.get("accepted_by")) | _values(record.get("owner"))
    if actor not in actor_values:
        return False
    role_values = _values(record.get("role")) | _values(record.get("authority_role")) | _values(record.get("roles")) | _values(record.get("authority_roles"))
    if role not in role_values:
        return False
    scope = record.get("scope") or {}
    if not isinstance(scope, dict):
        return False
    work_scope = _values(scope.get("work_items"))
    repo_scope = _values(scope.get("repositories")) | _values(scope.get("repository")) | _values(scope.get("full_name"))
    return work_id in work_scope or str(governed.get("full_name") or "") in repo_scope


def accepted_finding_authorized(root: Path, work_id: str, assurance: str, finding: dict[str, Any]) -> bool:
    policy = load_mapping(root / "registry/acceptance-authority.yaml")
    acceptance = finding.get("acceptance") or {}
    severity = str(finding.get("severity") or "")
    matrix = ((policy.get("finding_acceptance") or {}).get("matrix") or {}).get(assurance) or {}
    allowed_roles = matrix.get(severity) or []
    role = acceptance.get("authority_role")
    evidence_type = acceptance.get("authority_evidence_type")
    role_spec = (((policy.get("vocabulary") or {}).get("authority_roles") or {}).get(role) or {})
    required = (
        "accepted_by", "authority_role", "authority_evidence_type", "authority_evidence_ref",
        "authority_matrix_version", "authority_rule_id", "rationale", "accepted_at", "review_condition",
    )
    return bool(
        isinstance(acceptance, dict)
        and all(acceptance.get(key) not in (None, "") for key in required)
        and role in allowed_roles
        and evidence_type in (role_spec.get("allowed_evidence_types") or [])
        and acceptance.get("authority_matrix_version") == policy.get("version")
        and acceptance.get("authority_rule_id") == f"FINDING:{assurance}:{severity}"
        and authority_evidence_valid(root, work_id, acceptance, policy)
    )


def _review_authorization_matches(auth: dict[str, Any], review: dict[str, Any], consumed: Any) -> bool:
    ext = review.get("external_import") or {}
    artifact = review.get("artifact") or {}
    reviewer = review.get("reviewer") or {}
    return bool(
        auth.get("record_id") == review.get("id")
        and auth.get("imported_status") == review.get("status")
        and auth.get("artifact_commit_sha") == artifact.get("commit_sha")
        and auth.get("source_review_id") == ext.get("source_review_id")
        and auth.get("source_submitted_at") == ext.get("source_submitted_at")
        and auth.get("reviewer_context_id") == reviewer.get("context_id")
        and auth.get("expected_outcome") == review.get("outcome")
        and auth.get("one_shot") is True
        and auth.get("consumed_by_commit") == consumed
    )


def review_import_finalized(root: Path, review: dict[str, Any], head: str, path: str) -> bool:
    ext = review.get("external_import")
    if ext is None:
        return True
    if not isinstance(ext, dict) or ext.get("mode") != "PREAUTHORIZED_EXTERNAL_COMPLETION":
        return False
    import_commit = str(ext.get("import_commit") or "")
    auth_commit = str(ext.get("authorization_commit") or "")
    if not FULL_SHA.fullmatch(import_commit) or not FULL_SHA.fullmatch(auth_commit):
        return False
    if not git_ok(root, "cat-file", "-e", f"{import_commit}^{{commit}}") or not git_ok(root, "cat-file", "-e", f"{auth_commit}^{{commit}}"):
        return False
    actual_import = first_status_commit(root, path, str(review.get("status") or ""), head)
    if actual_import != import_commit:
        return False
    if auth_commit == import_commit or not is_ancestor(root, auth_commit, import_commit):
        return False
    auth_machine = show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    head_machine = show_yaml(root, head, "registry/status-machines.yaml") or {}
    auths_before = ((((auth_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    auths_after = ((((head_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    return any(isinstance(auth, dict) and _review_authorization_matches(auth, review, None) for auth in auths_before) and any(
        isinstance(auth, dict) and _review_authorization_matches(auth, review, import_commit) for auth in auths_after
    )


def _test_authorization_matches(auth: dict[str, Any], test: dict[str, Any], consumed: Any) -> bool:
    cold = test.get("acceptance_cold_read") or {}
    source = cold.get("source") or {}
    executor = cold.get("executor") or {}
    execution = test.get("execution") or {}
    return bool(
        auth.get("record_id") == test.get("id")
        and auth.get("imported_status") == test.get("status")
        and auth.get("execution_commit_sha") == execution.get("commit_sha")
        and auth.get("source_id") == source.get("source_id")
        and auth.get("source_submitted_at") == source.get("submitted_at")
        and auth.get("executor_context_id") == executor.get("context_id")
        and auth.get("expected_result") == execution.get("result")
        and auth.get("one_shot") is True
        and auth.get("consumed_by_commit") == consumed
    )


def test_import_finalized(root: Path, test: dict[str, Any], head: str, path: str) -> bool:
    ext = test.get("external_import")
    if ext is None:
        return True
    if not isinstance(ext, dict):
        return False
    source = str(ext.get("authorization_source") or "")
    match = re.fullmatch(r"registry/status-machines\.yaml@([0-9a-f]{40})#.+", source)
    import_commit = str(ext.get("import_commit") or "")
    if match is None or not FULL_SHA.fullmatch(import_commit):
        return False
    auth_commit = match.group(1)
    if not git_ok(root, "cat-file", "-e", f"{import_commit}^{{commit}}") or not git_ok(root, "cat-file", "-e", f"{auth_commit}^{{commit}}"):
        return False
    actual_import = first_status_commit(root, path, str(test.get("status") or ""), head)
    if actual_import != import_commit:
        return False
    if auth_commit == import_commit or not is_ancestor(root, auth_commit, import_commit):
        return False
    before_machine = show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    after_machine = show_yaml(root, head, "registry/status-machines.yaml") or {}
    before_auths = ((((before_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    after_auths = ((((after_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    return any(isinstance(auth, dict) and _test_authorization_matches(auth, test, None) for auth in before_auths) and any(
        isinstance(auth, dict) and _test_authorization_matches(auth, test, import_commit) for auth in after_auths
    )


def validate_requirement_acceptance_proof(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in changed_files(root, before, after):
            if not path.startswith("registry/requirements/") or not path.endswith(".yaml"):
                continue
            previous = show_yaml(root, before, path)
            current = show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "PROPOSED" or current.get("status") != "ACCEPTED":
                continue
            verification = current.get("verification") or {}
            for review_id in verification.get("acceptance_evidence", []) or []:
                review_path = f"registry/reviews/{review_id}.yaml"
                review = show_yaml(root, after, review_path) or {}
                if not review_import_finalized(root, review, after, review_path):
                    out.append(Finding(path, "REQ_REVIEW_IMPORT_FINALIZATION", f"acceptance review {review_id} is not bound to its actual materialization/consumption commit"))
            for test_id in verification.get("acceptance_cold_read_test_ids", []) or []:
                test_path = f"registry/tests/{test_id}.yaml"
                test = show_yaml(root, after, test_path) or {}
                if not pass_test_execution_revision_valid(root, test, after):
                    out.append(Finding(path, "REQ_COLD_READ_REVISION", f"cold-read test {test_id} does not bind a real reachable execution revision"))
                if not test_import_finalized(root, test, after, test_path):
                    out.append(Finding(path, "REQ_COLD_READ_IMPORT", f"cold-read test {test_id} external result import is not finalized"))
    return out


def flatten_progress(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for phase_id, phase in (data.get("phases") or {}).items():
        if not isinstance(phase, dict):
            continue
        if isinstance(phase.get("status"), str):
            out[f"progress:phase:{phase_id}"] = phase["status"]
        for lot_id, lot in (phase.get("lots") or {}).items():
            if not isinstance(lot, dict):
                continue
            if isinstance(lot.get("status"), str):
                out[f"progress:lot:{phase_id}/{lot_id}"] = lot["status"]
            for sub_id, sub in (lot.get("sublots") or {}).items():
                if not isinstance(sub, dict):
                    continue
                if isinstance(sub.get("status"), str):
                    out[f"progress:sublot:{phase_id}/{lot_id}/{sub_id}"] = sub["status"]
                for work_id, state in (sub.get("work_items") or {}).items():
                    if not isinstance(state, dict):
                        continue
                    if isinstance(state.get("status"), str):
                        out[f"work:{work_id}"] = state["status"]
                    for key, value in state.items():
                        if key != "status" and isinstance(value, str):
                            out[f"progress:work:{work_id}:{key}"] = value
    for key, value in (data.get("quality_dimensions") or {}).items():
        if isinstance(value, str):
            out[f"progress:quality:{key}"] = value
    return out


def reopening_triggered(root: Path, before: str, after: str, key: str) -> bool:
    target_work = None
    if key.startswith("progress:work:"):
        target_work = key.split(":", 3)[2]
    for path in changed_files(root, before, after):
        if path.startswith("registry/work-items/") and path.endswith(".yaml"):
            previous = show_yaml(root, before, path) or {}
            current = show_yaml(root, after, path) or {}
            if target_work and current.get("id") != target_work:
                continue
            old_findings = ((previous.get("review_plan") or {}).get("open_findings") or [])
            new_findings = ((current.get("review_plan") or {}).get("open_findings") or [])
            if isinstance(new_findings, list) and new_findings and new_findings != old_findings:
                return True
            old_scope = previous.get("scope_change") or {}
            new_scope = current.get("scope_change") or {}
            if isinstance(new_scope, dict) and new_scope.get("approved") is True and new_scope.get("rationale") and new_scope != old_scope:
                return True
        if path.startswith("registry/reviews/") and path.endswith(".yaml"):
            review = show_yaml(root, after, path) or {}
            scope = review.get("scope") or {}
            if review.get("status") == "COMPLETE" and review.get("outcome") in {"CHANGES_REQUIRED", "BLOCKED"}:
                if target_work is None or target_work in (scope.get("work_items") or []):
                    return True
    return False


def validate_progress_lifecycle(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before_sha, after_sha in edges:
        if "registry/progress/matrix.yaml" not in changed_files(root, before_sha, after_sha):
            continue
        before_data = show_yaml(root, before_sha, "registry/progress/matrix.yaml") or {}
        after_data = show_yaml(root, after_sha, "registry/progress/matrix.yaml") or {}
        machine = show_yaml(root, after_sha, "registry/status-machines.yaml") or {}
        progress_spec = machine.get("progress") or {}
        work_spec = ((machine.get("registry_machines") or {}).get("work_items") or {})
        progress_transitions = {str(k): set(v or []) for k, v in (progress_spec.get("transitions") or {}).items()}
        work_transitions = {str(k): set(v or []) for k, v in (work_spec.get("transitions") or {}).items()}
        before = flatten_progress(before_data)
        after = flatten_progress(after_data)
        for key in sorted(set(before) | set(after)):
            old = before.get(key)
            new = after.get(key)
            if old == new:
                continue
            transitions = work_transitions if key.startswith("work:") else progress_transitions
            initial = str(work_spec.get("initial") if key.startswith("work:") else progress_spec.get("initial") or "")
            effective_old = old if old is not None else initial
            if new is None:
                out.append(Finding("registry/progress/matrix.yaml", "PROGRESS_DELETE", f"progress instance {key} disappeared at {after_sha[:12]}"))
                continue
            allowed = transitions.get(str(effective_old), set())
            if new not in allowed:
                out.append(Finding("registry/progress/matrix.yaml", "PROGRESS_TRANSITION", f"invalid {key} transition {effective_old} -> {new} at {after_sha[:12]}"))
                continue
            if effective_old == "DONE" and new == "IN_REVIEW" and not reopening_triggered(root, before_sha, after_sha, key):
                out.append(Finding("registry/progress/matrix.yaml", "PROGRESS_REOPENING", f"{key} reopened DONE -> IN_REVIEW without structured review/evidence trigger at {after_sha[:12]}"))
    return out


def validate_squash_flags(root: Path) -> list[Finding]:
    out: list[Finding] = []
    provenance = load_mapping(root / "registry/integration-provenance.yaml")
    for index, entry in enumerate(provenance.get("squash_integrations", []) or []):
        if not isinstance(entry, dict):
            out.append(Finding("registry/integration-provenance.yaml", "SQUASH_PROVENANCE_SHAPE", f"squash integration #{index} must be a mapping"))
            continue
        if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:
            out.append(Finding("registry/integration-provenance.yaml", "SQUASH_PROVENANCE_REUSE", f"squash integration #{index} must be historical_only=true and future_reuse_forbidden=true"))
    return out


def validate_done_tasks_runs_and_authority(root: Path, head: str) -> list[Finding]:
    out: list[Finding] = []
    for path in sorted((root / "registry/work-items").glob("WORK-*.yaml")):
        work = load_mapping(path)
        if work.get("status") != "DONE":
            continue
        plan = work.get("implementation_plan") or {}
        for collection in ("tasks", "planned_runs"):
            for item in plan.get(collection, []) or []:
                if not isinstance(item, dict) or item.get("status") not in DONE_TASK_RUN_STATES:
                    out.append(Finding(str(path.relative_to(root)), "DONE_TASK_RUN", f"DONE work requires every {collection} entry to be DONE/NOT_APPLICABLE; got {item!r}"))
        assurance = str(((work.get("assurance") or {}).get("level") or ""))
        work_id = str(work.get("id") or "")
        for review_id in ((work.get("review_plan") or {}).get("completed_reviews") or []):
            review_path = f"registry/reviews/{review_id}.yaml"
            review = load_mapping(root / review_path)
            if review.get("status") == "COMPLETE" and not review_import_finalized(root, review, head, review_path):
                out.append(Finding(review_path, "REVIEW_IMPORT_MATERIALIZATION", f"review {review_id} import binding is not the real first COMPLETE materialization and consumed authorization"))
            for finding in review.get("findings", []) or []:
                if not isinstance(finding, dict) or finding.get("severity") not in BLOCKING_SEVERITIES or finding.get("disposition") != "ACCEPTED":
                    continue
                if not accepted_finding_authorized(root, work_id, assurance, finding):
                    out.append(Finding(review_path, "FINDING_ACCEPTANCE_AUTHORITY", f"accepted blocking finding {finding.get('id')} does not establish actor, role and governed scope"))
    return out


def validate_checkout_ref(root: Path) -> list[Finding]:
    workflow = load_mapping(root / ".github/workflows/_governance-core.yml")
    steps = ((((workflow.get("jobs") or {}).get("validate") or {}).get("steps") or []))
    checkout = next((step for step in steps if isinstance(step, dict) and str(step.get("uses") or "").startswith("actions/checkout@")), None)
    if not isinstance(checkout, dict) or (checkout.get("with") or {}).get("ref") != CHECKOUT_REF:
        return [Finding(".github/workflows/_governance-core.yml", "EXACT_HEAD_CHECKOUT", "governance core must checkout inputs.head_sha explicitly, not the synthetic PR merge ref")]
    return []


def run(root: Path, base: str, head: str) -> list[Finding]:
    root = root.resolve()
    edges = pr_edges(root, base, head)
    findings: list[Finding] = []
    findings.extend(validate_checkout_ref(root))
    findings.extend(validate_completed_review_immutability(root, edges))
    findings.extend(validate_requirement_acceptance_proof(root, edges))
    findings.extend(validate_progress_lifecycle(root, edges))
    findings.extend(validate_squash_flags(root))
    findings.extend(validate_done_tasks_runs_and_authority(root, head))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    try:
        findings = run(Path(args.root), args.base, args.head)
    except RuntimeError as exc:
        print(f"ERROR L2_HARDENING {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE L2 hardening: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
