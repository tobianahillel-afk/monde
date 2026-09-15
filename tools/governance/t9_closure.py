from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc
import tools.governance.t7_closure as t7
import tools.governance.t8_closure as t8
from tools.governance.proof_contracts import FULL_COMMIT_SHA

POLICY_PATH = "registry/content-identity.yaml"
T9_PATH = "tools/governance/t9_closure.py"
PROTECTED_POLICIES = t7.PROTECTED_POLICIES


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def text_at(root: Path, sha: str, path: str) -> str | None:
    try:
        return cg.git(root, "show", f"{sha}:{path}")
    except RuntimeError:
        return None


def first_commit_matching(root: Path, head: str, path: str, predicate: Callable[[str], bool]) -> str | None:
    commits = [
        value
        for value in cg.git(root, "rev-list", "--reverse", "--topo-order", head, "--", path).splitlines()
        if value
    ]
    for sha in commits:
        current = text_at(root, sha, path)
        if current is None or not predicate(current):
            continue
        parents = cg.commit_parents(root, sha)
        if not parents or all(not predicate(text_at(root, parent, path) or "") for parent in parents):
            return sha
    return None


def t9_adoption_sha(root: Path, head: str) -> str | None:
    return first_commit_matching(root, head, T9_PATH, lambda text: "def validate_base_preexisting_policy_authority" in text)


def policy_stable_full_history(root: Path, evidence_sha: str, acceptance_sha: str) -> bool:
    if not cg.commit_exists(root, evidence_sha) or not cg.commit_exists(root, acceptance_sha):
        return False
    if not cg.is_ancestor(root, evidence_sha, acceptance_sha):
        return False
    evidence_blob = t7.policy_blob(root, evidence_sha)
    acceptance_blob = t7.policy_blob(root, acceptance_sha)
    if evidence_blob is None or evidence_blob != acceptance_blob:
        return False
    touched = [
        line
        for line in cg.git(
            root,
            "rev-list",
            "--full-history",
            "--topo-order",
            f"{evidence_sha}..{acceptance_sha}",
            "--",
            POLICY_PATH,
        ).splitlines()
        if line
    ]
    return not touched


def _first_status_commit(root: Path, path: str, status: str, head: str) -> str | None:
    commits = [
        line
        for line in cg.git(root, "rev-list", "--reverse", "--topo-order", head, "--", path).splitlines()
        if line
    ]
    for sha in commits:
        current = cg.show_yaml(root, sha, path)
        if not current or current.get("status") != status:
            continue
        parents = cg.commit_parents(root, sha)
        if not parents or all((cg.show_yaml(root, parent, path) or {}).get("status") != status for parent in parents):
            return sha
    return None


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
    if not FULL_COMMIT_SHA.fullmatch(import_commit) or not FULL_COMMIT_SHA.fullmatch(auth_commit):
        return False
    if not cg.commit_exists(root, import_commit) or not cg.commit_exists(root, auth_commit):
        return False
    if _first_status_commit(root, path, str(review.get("status") or ""), head) != import_commit:
        return False
    if auth_commit == import_commit or not cg.is_ancestor(root, auth_commit, import_commit):
        return False
    before_machine = cg.show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    after_machine = cg.show_yaml(root, head, "registry/status-machines.yaml") or {}
    before_auths = ((((before_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    after_auths = ((((after_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    return any(isinstance(auth, dict) and _review_authorization_matches(auth, review, None) for auth in before_auths) and any(
        isinstance(auth, dict) and _review_authorization_matches(auth, review, import_commit) for auth in after_auths
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
    if match is None or not FULL_COMMIT_SHA.fullmatch(import_commit):
        return False
    auth_commit = match.group(1)
    if not cg.commit_exists(root, import_commit) or not cg.commit_exists(root, auth_commit):
        return False
    if _first_status_commit(root, path, str(test.get("status") or ""), head) != import_commit:
        return False
    if auth_commit == import_commit or not cg.is_ancestor(root, auth_commit, import_commit):
        return False
    before_machine = cg.show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    after_machine = cg.show_yaml(root, head, "registry/status-machines.yaml") or {}
    before_auths = ((((before_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    after_auths = ((((after_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    return any(isinstance(auth, dict) and _test_authorization_matches(auth, test, None) for auth in before_auths) and any(
        isinstance(auth, dict) and _test_authorization_matches(auth, test, import_commit) for auth in after_auths
    )


def review_qualifies(root: Path, acceptance_sha: str, requirement: dict[str, Any], digest: str, floor: int, review: dict[str, Any]) -> bool:
    reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or ""))
    review_id = str(review.get("id") or "")
    path = f"registry/reviews/{review_id}.yaml"
    return bool(
        t7.review_qualifies(root, acceptance_sha, requirement, digest, floor, review)
        and policy_stable_full_history(root, reviewed_sha, acceptance_sha)
        and review_import_finalized(root, review, acceptance_sha, path)
    )


def cold_read_qualifies(root: Path, acceptance_sha: str, requirement: dict[str, Any], digest: str, floor: int, test: dict[str, Any]) -> bool:
    execution_sha = str(((test.get("execution") or {}).get("commit_sha") or ""))
    test_id = str(test.get("id") or "")
    path = f"registry/tests/{test_id}.yaml"
    return bool(
        t7.cold_read_qualifies(root, acceptance_sha, requirement, digest, floor, test)
        and policy_stable_full_history(root, execution_sha, acceptance_sha)
        and test_import_finalized(root, test, acceptance_sha, path)
    )


def requirement_acceptance_invariant(root: Path, sha: str, requirement: dict[str, Any]) -> bool:
    if not cg.requirement_acceptance_satisfied(root, sha, requirement):
        return False
    digest = str(((requirement.get("content_identity") or {}).get("digest") or ""))
    floor, _ = rc.requirement_review_floor(root, sha, requirement)
    verification = requirement.get("verification") or {}
    reviews = [
        cg.show_yaml(root, sha, f"registry/reviews/{review_id}.yaml") or {}
        for review_id in verification.get("acceptance_evidence", []) or []
        if isinstance(review_id, str) and review_id.startswith("REVIEW-")
    ]
    tests = [
        cg.show_yaml(root, sha, f"registry/tests/{test_id}.yaml") or {}
        for test_id in verification.get("acceptance_cold_read_test_ids", []) or []
        if isinstance(test_id, str) and test_id.startswith("TEST-")
    ]
    return bool(
        any(review_qualifies(root, sha, requirement, digest, floor, review) for review in reviews)
        and any(cold_read_qualifies(root, sha, requirement, digest, floor, test) for test in tests)
    )


def validate_requirement_acceptance(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            if not path.startswith("registry/requirements/") or not path.endswith(".yaml"):
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or current.get("status") != "ACCEPTED":
                continue
            if not requirement_acceptance_invariant(root, after, current):
                out.append(Finding(path, "REQ_ACCEPTANCE_T9", f"ACCEPTED requirement lacks full-history, finalized review/cold-read evidence at {after[:12]}"))
    return out


def validate_import_commit_immutability(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            if not path.startswith("registry/reviews/") or not path.endswith(".yaml"):
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "COMPLETE":
                continue
            old_ext = previous.get("external_import")
            new_ext = current.get("external_import")
            if not isinstance(old_ext, dict) or not isinstance(new_ext, dict):
                continue
            old_value = old_ext.get("import_commit")
            new_value = new_ext.get("import_commit")
            if old_value == new_value:
                continue
            if old_value in (None, "") and isinstance(new_value, str) and review_import_finalized(root, current, after, path):
                continue
            out.append(Finding(path, "REVIEW_IMPORT_COMMIT_IMMUTABLE", f"external review import_commit changed outside its one allowed null-to-materialization finalization at {after[:12]}"))
    return out


def base_preexisting_work_covers(root: Path, base: str, path: str) -> bool:
    work_paths = [
        item
        for item in cg.git(root, "ls-tree", "-r", "--name-only", base, "registry/work-items").splitlines()
        if item.endswith(".yaml") and not Path(item).name.startswith("_")
    ]
    for work_path in work_paths:
        work = cg.show_yaml(root, base, work_path) or {}
        if work.get("status") not in cg.ACTIVE_WORK_STATUSES:
            continue
        if ((work.get("assurance") or {}).get("level")) not in {"A3", "A4"}:
            continue
        if ((work.get("scope_change") or {}).get("approved")) is not True:
            continue
        if cg.path_is_declared(path, work.get("affected_paths", []) or []):
            return True
    return False


def validate_base_preexisting_policy_authority(root: Path, base: str, head: str) -> list[Finding]:
    adoption = t9_adoption_sha(root, head)
    if adoption is None:
        return [Finding(T9_PATH, "T9_ADOPTION", "T9 enforcement has no immutable Git introduction commit")]
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        changed = set(cg.changed_files(root, before, after)) & set(PROTECTED_POLICIES)
        if not changed:
            continue
        if after == adoption:
            for path in sorted(changed):
                out.append(Finding(path, "POLICY_T9_SELF_AUTHORIZATION", "T9 adoption commit may not amend a protected policy"))
            continue
        if not cg.is_ancestor(root, adoption, before):
            continue
        for path in sorted(changed):
            if not base_preexisting_work_covers(root, base, path):
                out.append(Finding(path, "POLICY_BASE_AUTHORITY", f"protected policy amendment at {after[:12]} is not covered by base-preexisting independently approved active A3/A4 scope"))
    return out


def _new_review_trigger(root: Path, before: str, after: str, work_id: str, path: str) -> bool:
    previous = cg.show_yaml(root, before, path) or {}
    current = cg.show_yaml(root, after, path) or {}
    scope = current.get("scope") or {}
    current_qualifies = bool(
        current.get("status") == "COMPLETE"
        and current.get("outcome") in {"CHANGES_REQUIRED", "BLOCKED"}
        and work_id in (scope.get("work_items") or [])
    )
    old_scope = previous.get("scope") or {}
    previous_qualifies = bool(
        previous.get("status") == "COMPLETE"
        and previous.get("outcome") in {"CHANGES_REQUIRED", "BLOCKED"}
        and work_id in (old_scope.get("work_items") or [])
    )
    return current_qualifies and not previous_qualifies


def new_reopening_trigger(root: Path, before: str, after: str, work_id: str) -> bool:
    changed = set(cg.changed_files(root, before, after))
    work_path = f"registry/work-items/{work_id}.yaml"
    if work_path in changed:
        previous = cg.show_yaml(root, before, work_path) or {}
        current = cg.show_yaml(root, after, work_path) or {}
        old_findings = ((previous.get("review_plan") or {}).get("open_findings") or [])
        new_findings = ((current.get("review_plan") or {}).get("open_findings") or [])
        if isinstance(old_findings, list) and isinstance(new_findings, list):
            old_ids = {value for value in old_findings if isinstance(value, str)}
            new_ids = {value for value in new_findings if isinstance(value, str)}
            if new_ids - old_ids:
                return True
        old_scope = previous.get("scope_change") or {}
        new_scope = current.get("scope_change") or {}
        if (
            isinstance(old_scope, dict)
            and isinstance(new_scope, dict)
            and old_scope.get("approved") is not True
            and new_scope.get("approved") is True
            and bool(new_scope.get("rationale"))
        ):
            return True
    for path in changed:
        if path.startswith("registry/reviews/") and path.endswith(".yaml") and _new_review_trigger(root, before, after, work_id, path):
            return True
    return False


def validate_new_reopening_triggers(root: Path, base: str, head: str) -> list[Finding]:
    adoption = t9_adoption_sha(root, head)
    if adoption is None:
        return [Finding(T9_PATH, "T9_ADOPTION", "T9 enforcement has no immutable Git introduction commit")]
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        if not cg.is_ancestor(root, adoption, before):
            continue
        if "registry/progress/matrix.yaml" not in cg.changed_files(root, before, after):
            continue
        previous = t8.matrix_work_statuses(cg.show_yaml(root, before, "registry/progress/matrix.yaml") or {})
        current = t8.matrix_work_statuses(cg.show_yaml(root, after, "registry/progress/matrix.yaml") or {})
        for work_id in sorted(set(previous) | set(current)):
            if previous.get(work_id) != "DONE" or current.get(work_id) != "IN_REVIEW":
                continue
            if not new_reopening_trigger(root, before, after, work_id):
                out.append(Finding("registry/progress/matrix.yaml", "WORK_REOPENING_NEW_TRIGGER", f"WORK {work_id} reopened DONE -> IN_REVIEW without a newly added finding/evidence identity or newly approved scope-change event at {after[:12]}"))
    return out


def run(root: Path, base: str, head: str) -> list[Finding]:
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    out: list[Finding] = []
    out.extend(validate_requirement_acceptance(root, edges))
    out.extend(validate_import_commit_immutability(root, edges))
    out.extend(validate_base_preexisting_policy_authority(root, base, head))
    out.extend(validate_new_reopening_triggers(root, base, head))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    findings = run(Path(args.root).resolve(), args.base, args.head)
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE T9 closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
