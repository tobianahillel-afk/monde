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
from tools.governance.proof_contracts import pass_test_execution_revision_valid, requirement_normative_digest

PROTECTED_POLICIES = (
    "registry/status-machines.yaml",
    "registry/acceptance-authority.yaml",
    "registry/content-identity.yaml",
)
T7_PATH = "tools/governance/t7_closure.py"
APPROVING_OUTCOMES = {"APPROVE", "APPROVE_WITH_FOLLOWUP"}
REQUIRED_COLD_OUTCOMES = {
    "understood_without_author_reasoning",
    "atomic_and_testable",
    "dependencies_and_conflicts_checked",
    "omissions_and_failure_modes_checked",
    "evidence_plan_sufficient",
}
ADOPTION_RULES = {
    "PROGRESS_LIFECYCLE_EDGE_ENFORCEMENT_V1": (
        ".github/scripts/governance_l2_hardening.py",
        "def validate_progress_lifecycle",
    ),
    "PROGRESS_REOPENING_EVIDENCE_V1": (
        ".github/workflows/_governance-core.yml",
        "tools.governance.review_closure",
    ),
}


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


def t7_adoption_sha(root: Path, head: str) -> str | None:
    return first_commit_matching(root, head, T7_PATH, lambda text: "def validate_policy_trust_anchors" in text)


def active_predecessor_work_covers(root: Path, sha: str, path: str) -> bool:
    work_paths = [
        item
        for item in cg.git(root, "ls-tree", "-r", "--name-only", sha, "registry/work-items").splitlines()
        if item.endswith(".yaml") and not Path(item).name.startswith("_")
    ]
    for work_path in work_paths:
        work = cg.show_yaml(root, sha, work_path) or {}
        if work.get("status") not in cg.ACTIVE_WORK_STATUSES:
            continue
        if ((work.get("assurance") or {}).get("level")) not in {"A3", "A4"}:
            continue
        if cg.path_is_declared(path, work.get("affected_paths", []) or []):
            return True
    return False


def validate_policy_trust_anchors(root: Path, base: str, head: str) -> list[Finding]:
    adoption = t7_adoption_sha(root, head)
    if adoption is None:
        return [Finding(T7_PATH, "POLICY_TRUST_ANCHOR_ADOPTION", "T7 trust-anchor enforcement has no immutable Git introduction commit")]
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        changed = set(cg.changed_files(root, before, after)) & set(PROTECTED_POLICIES)
        if not changed:
            continue
        if after == adoption:
            for path in sorted(changed):
                out.append(Finding(path, "POLICY_SELF_AUTHORIZATION", "T7 adoption commit may not also modify a protected canonical policy"))
            continue
        if not cg.is_ancestor(root, adoption, before):
            continue
        for path in sorted(changed):
            if not active_predecessor_work_covers(root, before, path):
                out.append(Finding(path, "POLICY_PREDECESSOR_AUTHORITY", f"protected policy amendment at {after[:12]} lacks an active predecessor A3/A4 work scope covering the policy"))
    return out


def validate_adoption_boundaries(root: Path, head: str) -> list[Finding]:
    provenance = cg.show_yaml(root, head, "registry/integration-provenance.yaml") or {}
    entries = provenance.get("enforcement_adoptions", []) or []
    out: list[Finding] = []
    for rule_id, (path, needle) in ADOPTION_RULES.items():
        actual = first_commit_matching(root, head, path, lambda text, marker=needle: marker in text)
        matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("rule_id") == rule_id]
        if actual is None or len(matches) != 1:
            out.append(Finding("registry/integration-provenance.yaml", "ADOPTION_HISTORY_BINDING", f"{rule_id} must have one marker matching a derivable immutable Git introduction"))
            continue
        entry = matches[0]
        if (
            entry.get("adoption_commit_sha") != actual
            or entry.get("historical_only") is not True
            or entry.get("future_reuse_forbidden") is not True
        ):
            out.append(Finding("registry/integration-provenance.yaml", "ADOPTION_HISTORY_BINDING", f"{rule_id} marker must equal immutable Git-derived adoption {actual}"))
    return out


def policy_blob(root: Path, sha: str) -> str | None:
    return cg.blob_sha_at(root, sha, "registry/content-identity.yaml")


def review_qualifies(
    root: Path,
    acceptance_sha: str,
    requirement: dict[str, Any],
    digest: str,
    floor: int,
    review: dict[str, Any],
) -> bool:
    rid = str(requirement.get("id") or "")
    scope = review.get("scope") or {}
    revision = (scope.get("requirement_revisions") or {}).get(rid) or {}
    reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or ""))
    return bool(
        rc.substantive_review(review, floor)
        and review.get("outcome") in APPROVING_OUTCOMES
        and rid in (scope.get("requirements") or [])
        and revision.get("digest") == digest
        and revision.get("status_at_review") == "PROPOSED"
        and cg.review_requirement_revision_valid(root, acceptance_sha, rid, digest, review)
        and policy_blob(root, reviewed_sha) is not None
        and policy_blob(root, reviewed_sha) == policy_blob(root, acceptance_sha)
    )


def cold_read_qualifies(
    root: Path,
    acceptance_sha: str,
    requirement: dict[str, Any],
    digest: str,
    floor: int,
    test: dict[str, Any],
) -> bool:
    rid = str(requirement.get("id") or "")
    cold = test.get("acceptance_cold_read") or {}
    binding = (cold.get("requirements") or {}).get(rid) or {}
    outcomes = cold.get("required_outcomes") or {}
    execution_sha = str(((test.get("execution") or {}).get("commit_sha") or ""))
    execution_policy = cg.show_yaml(root, execution_sha, "registry/content-identity.yaml") or {}
    execution_requirement = cg.show_yaml(root, execution_sha, f"registry/requirements/{rid}.yaml") or {}
    return bool(
        test.get("status") == "PASS"
        and ((test.get("execution") or {}).get("result")) == "PASS"
        and rid in ((test.get("protects") or {}).get("requirements") or [])
        and cold.get("qualifies") is True
        and binding.get("content_digest") == digest
        and binding.get("status_at_read") == "PROPOSED"
        and rc.cold_read_has_provenance(test, max(2, floor))
        and cold.get("all_required_outcomes_pass") is True
        and REQUIRED_COLD_OUTCOMES.issubset(outcomes)
        and all(outcomes.get(key) == "PASS" for key in REQUIRED_COLD_OUTCOMES)
        and pass_test_execution_revision_valid(root, test, acceptance_sha)
        and execution_requirement.get("status") == "PROPOSED"
        and requirement_normative_digest(root, execution_requirement, execution_policy) == digest
        and policy_blob(root, execution_sha) is not None
        and policy_blob(root, execution_sha) == policy_blob(root, acceptance_sha)
    )


def validate_requirement_co_satisfaction(root: Path, base: str, head: str) -> list[Finding]:
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            if not path.startswith("registry/requirements/") or not path.endswith(".yaml"):
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "PROPOSED" or current.get("status") != "ACCEPTED":
                continue
            ident = current.get("content_identity") or {}
            digest = str(ident.get("digest") or "")
            floor, _ = rc.requirement_review_floor(root, after, current)
            verification = current.get("verification") or {}
            reviews = [
                cg.show_yaml(root, after, f"registry/reviews/{rid}.yaml") or {}
                for rid in verification.get("acceptance_evidence", []) or []
                if isinstance(rid, str) and rid.startswith("REVIEW-")
            ]
            tests = [
                cg.show_yaml(root, after, f"registry/tests/{tid}.yaml") or {}
                for tid in verification.get("acceptance_cold_read_test_ids", []) or []
                if isinstance(tid, str) and tid.startswith("TEST-")
            ]
            if not any(review_qualifies(root, after, current, digest, floor, review) for review in reviews):
                out.append(Finding(path, "REQ_REVIEW_CO_SATISFACTION", f"one review must co-satisfy semantic binding, exact policy revision, provenance and L{floor}+ independence"))
            if not any(cold_read_qualifies(root, after, current, digest, floor, test) for test in tests):
                out.append(Finding(path, "REQ_COLD_READ_CO_SATISFACTION", f"one cold-read TEST must co-satisfy revision, policy, outcomes, provenance, reachability and L{max(2, floor)}+ independence"))
    return out


def actual_git_repository(root: Path) -> str | None:
    try:
        remote = cg.git(root, "config", "--get", "remote.origin.url").strip()
    except RuntimeError:
        return None
    match = re.search(r"github\.com(?::|/)([^/]+/[^/]+?)(?:\.git)?$", remote)
    return match.group(1) if match else None


def validate_repository_owner_anchor(root: Path, head: str) -> list[Finding]:
    actual = actual_git_repository(root)
    policy = cg.show_yaml(root, head, "registry/acceptance-authority.yaml") or {}
    governed = policy.get("governed_repository") or {}
    if not actual:
        return [Finding("registry/acceptance-authority.yaml", "REPOSITORY_OWNER_EXTERNAL_ANCHOR", "Git remote must identify the actual GitHub repository")]
    owner = actual.split("/", 1)[0]
    proof_id = governed.get("permission_proof")
    proof = cg.show_yaml(root, head, f"registry/tests/{proof_id}.yaml") if isinstance(proof_id, str) else None
    proof = proof or {}
    real_dependencies = ((proof.get("environment") or {}).get("real_dependencies") or [])
    if not isinstance(real_dependencies, list):
        real_dependencies = []
    valid = bool(
        governed.get("full_name") == actual
        and governed.get("owner_login") == owner
        and governed.get("metadata_url") == f"https://api.github.com/repos/{actual}"
        and isinstance(proof_id, str)
        and proof.get("id") == proof_id
        and proof.get("status") == "PASS"
        and ((proof.get("execution") or {}).get("result")) == "PASS"
        and pass_test_execution_revision_valid(root, proof, head)
        and any(actual in str(item) for item in real_dependencies)
        and any("collaborator permission" in str(item).lower() for item in real_dependencies)
    )
    return [] if valid else [Finding("registry/acceptance-authority.yaml", "REPOSITORY_OWNER_EXTERNAL_ANCHOR", "repository-owner authority must match the actual Git remote and a reachable PASS real-GitHub permission proof")]


def run(root: Path, base: str, head: str) -> list[Finding]:
    root = root.resolve()
    findings: list[Finding] = []
    findings.extend(validate_policy_trust_anchors(root, base, head))
    findings.extend(validate_adoption_boundaries(root, head))
    findings.extend(validate_requirement_co_satisfaction(root, base, head))
    findings.extend(validate_repository_owner_anchor(root, head))
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
        print(f"ERROR T7_CLOSURE {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE T7 closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
