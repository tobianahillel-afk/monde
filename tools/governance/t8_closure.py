from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc
import tools.governance.t7_closure as t7

POLICY_PATH = "registry/content-identity.yaml"
REQUIRED_COLD_OUTCOMES = t7.REQUIRED_COLD_OUTCOMES


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def policy_stable_between(root: Path, evidence_sha: str, acceptance_sha: str) -> bool:
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
        for line in cg.git(root, "rev-list", f"{evidence_sha}..{acceptance_sha}", "--", POLICY_PATH).splitlines()
        if line
    ]
    return not touched


def review_qualifies_continuously(
    root: Path,
    acceptance_sha: str,
    requirement: dict[str, Any],
    digest: str,
    floor: int,
    review: dict[str, Any],
) -> bool:
    reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or ""))
    return bool(
        t7.review_qualifies(root, acceptance_sha, requirement, digest, floor, review)
        and policy_stable_between(root, reviewed_sha, acceptance_sha)
    )


def cold_read_qualifies_continuously(
    root: Path,
    acceptance_sha: str,
    requirement: dict[str, Any],
    digest: str,
    floor: int,
    test: dict[str, Any],
) -> bool:
    execution_sha = str(((test.get("execution") or {}).get("commit_sha") or ""))
    return bool(
        t7.cold_read_qualifies(root, acceptance_sha, requirement, digest, floor, test)
        and policy_stable_between(root, execution_sha, acceptance_sha)
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
        any(review_qualifies_continuously(root, sha, requirement, digest, floor, review) for review in reviews)
        and any(cold_read_qualifies_continuously(root, sha, requirement, digest, floor, test) for test in tests)
    )


def validate_continuing_acceptance(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            kind = cg.registry_kind(path)
            if kind not in {"requirements", "risks"}:
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "ACCEPTED" or current.get("status") != "ACCEPTED":
                continue
            if kind == "requirements" and not requirement_acceptance_invariant(root, after, current):
                out.append(Finding(path, "REQ_ACCEPTED_INVARIANT", f"changed ACCEPTED requirement no longer satisfies canonical acceptance evidence at {after[:12]}"))
            if kind == "risks" and not cg.risk_acceptance_satisfied(root, after, current):
                out.append(Finding(path, "RISK_ACCEPTED_INVARIANT", f"changed ACCEPTED risk no longer satisfies canonical authority/precondition evidence at {after[:12]}"))
    return out


def completion_review_projection(review: dict[str, Any] | None) -> dict[str, Any]:
    if not review:
        return {}
    external = review.get("external_import")
    external_projection: Any = external
    if isinstance(external, dict):
        external_projection = {key: value for key, value in external.items() if key != "import_commit"}
    return {
        "status": review.get("status"),
        "outcome": review.get("outcome"),
        "artifact": review.get("artifact"),
        "reviewer": review.get("reviewer"),
        "roles": review.get("roles"),
        "scope": review.get("scope"),
        "findings": review.get("findings"),
        "checks": review.get("checks"),
        "completed_at": review.get("completed_at"),
        "verification_result": review.get("verification_result"),
        "external_import": external_projection,
    }


def validate_complete_review_immutability(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            if not path.startswith("registry/reviews/") or not path.endswith(".yaml"):
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "COMPLETE":
                continue
            if completion_review_projection(previous) != completion_review_projection(current):
                out.append(Finding(path, "COMPLETE_REVIEW_COMPLETION_IMMUTABLE", f"completion-bearing COMPLETE review evidence changed at {after[:12]}"))
    return out


def matrix_work_statuses(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for phase in (data.get("phases") or {}).values():
        if not isinstance(phase, dict):
            continue
        for lot in (phase.get("lots") or {}).values():
            if not isinstance(lot, dict):
                continue
            for sublot in (lot.get("sublots") or {}).values():
                if not isinstance(sublot, dict):
                    continue
                for work_id, state in (sublot.get("work_items") or {}).items():
                    if isinstance(state, dict) and isinstance(state.get("status"), str):
                        out[str(work_id)] = state["status"]
    return out


def target_work_reopening_triggered(root: Path, before: str, after: str, work_id: str) -> bool:
    work_path = f"registry/work-items/{work_id}.yaml"
    changed = set(cg.changed_files(root, before, after))
    if work_path in changed:
        previous = cg.show_yaml(root, before, work_path) or {}
        current = cg.show_yaml(root, after, work_path) or {}
        old_findings = ((previous.get("review_plan") or {}).get("open_findings") or [])
        new_findings = ((current.get("review_plan") or {}).get("open_findings") or [])
        if isinstance(new_findings, list) and new_findings and new_findings != old_findings:
            return True
        old_scope = previous.get("scope_change") or {}
        new_scope = current.get("scope_change") or {}
        if isinstance(new_scope, dict) and new_scope.get("approved") is True and new_scope.get("rationale") and new_scope != old_scope:
            return True
    for path in changed:
        if not path.startswith("registry/reviews/") or not path.endswith(".yaml"):
            continue
        review = cg.show_yaml(root, after, path) or {}
        scope = review.get("scope") or {}
        if (
            review.get("status") == "COMPLETE"
            and review.get("outcome") in {"CHANGES_REQUIRED", "BLOCKED"}
            and work_id in (scope.get("work_items") or [])
        ):
            return True
    return False


def validate_work_reopenings(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        if "registry/progress/matrix.yaml" not in cg.changed_files(root, before, after):
            continue
        previous = matrix_work_statuses(cg.show_yaml(root, before, "registry/progress/matrix.yaml") or {})
        current = matrix_work_statuses(cg.show_yaml(root, after, "registry/progress/matrix.yaml") or {})
        for work_id in sorted(set(previous) | set(current)):
            if previous.get(work_id) != "DONE" or current.get(work_id) != "IN_REVIEW":
                continue
            if not target_work_reopening_triggered(root, before, after, work_id):
                out.append(Finding("registry/progress/matrix.yaml", "WORK_REOPENING_SCOPE", f"WORK {work_id} reopened DONE -> IN_REVIEW without a trigger scoped to that exact WORK at {after[:12]}"))
    return out


def run(root: Path, base: str, head: str) -> list[Finding]:
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    out: list[Finding] = []
    out.extend(validate_continuing_acceptance(root, edges))
    out.extend(validate_complete_review_immutability(root, edges))
    out.extend(validate_work_reopenings(root, edges))
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
    print(f"MONDE T8 closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
