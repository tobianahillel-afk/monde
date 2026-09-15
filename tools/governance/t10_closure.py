from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import tools.governance.change_guard as cg
import tools.governance.t9_closure as t9

T10_PATH = "tools/governance/t10_closure.py"
INTEGRATION_PROVENANCE_PATH = "registry/integration-provenance.yaml"
WORKFLOW_PATH = ".github/workflows/governance.yml"
CORE_WORKFLOW_PATH = ".github/workflows/_governance-core.yml"
REQUIREMENT_POLICY_PATHS = {
    "registry/content-identity.yaml",
    "registry/status-machines.yaml",
    "registry/integration-provenance.yaml",
}
RISK_POLICY_PATHS = {
    "registry/acceptance-authority.yaml",
    "registry/status-machines.yaml",
}
REGISTRY_REF = re.compile(r"^(WORK|REVIEW|TEST)-[A-Za-z0-9_-]+")


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


def first_commit_matching(root: Path, head: str, path: str, needle: str) -> str | None:
    commits = [
        value
        for value in cg.git(root, "rev-list", "--reverse", "--topo-order", head, "--", path).splitlines()
        if value
    ]
    for sha in commits:
        current = text_at(root, sha, path) or ""
        if needle not in current:
            continue
        parents = cg.commit_parents(root, sha)
        if not parents or all(needle not in (text_at(root, parent, path) or "") for parent in parents):
            return sha
    return None


def t10_adoption_sha(root: Path, head: str) -> str | None:
    return first_commit_matching(root, head, T10_PATH, "def validate_integration_provenance_trust_anchor")


def edge_is_enforced(root: Path, adoption: str, before: str, after: str) -> bool:
    return after == adoption or cg.is_ancestor(root, adoption, before)


def validate_integration_provenance_trust_anchor(root: Path, base: str, head: str) -> list[Finding]:
    adoption = t10_adoption_sha(root, head)
    if adoption is None:
        return [Finding(T10_PATH, "T10_ADOPTION", "T10 enforcement has no immutable Git introduction commit")]
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        if INTEGRATION_PROVENANCE_PATH not in cg.changed_files(root, before, after):
            continue
        if after == adoption:
            out.append(
                Finding(
                    INTEGRATION_PROVENANCE_PATH,
                    "INTEGRATION_PROVENANCE_SELF_AUTHORIZATION",
                    "T10 adoption commit may not amend the integration-provenance exception policy",
                )
            )
            continue
        if not cg.is_ancestor(root, adoption, before):
            continue
        if not t9.base_preexisting_work_covers(root, base, INTEGRATION_PROVENANCE_PATH):
            out.append(
                Finding(
                    INTEGRATION_PROVENANCE_PATH,
                    "INTEGRATION_PROVENANCE_BASE_AUTHORITY",
                    f"integration-provenance amendment at {after[:12]} lacks base-preexisting independently approved active A3/A4 scope",
                )
            )
    return out


def registry_records(root: Path, sha: str, kind: str) -> Iterator[tuple[str, dict[str, Any]]]:
    prefix = f"registry/{kind}"
    paths = [
        value
        for value in cg.git(root, "ls-tree", "-r", "--name-only", sha, prefix).splitlines()
        if value.endswith(".yaml") and not Path(value).name.startswith("_")
    ]
    for path in paths:
        record = cg.show_yaml(root, sha, path)
        if isinstance(record, dict):
            yield path, record


def registry_reference_path(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = REGISTRY_REF.match(value)
    if match is None:
        return value if value.startswith("registry/") else None
    identifier = match.group(0)
    family = match.group(1)
    directory = {"WORK": "work-items", "REVIEW": "reviews", "TEST": "tests"}[family]
    return f"registry/{directory}/{identifier}.yaml"


def requirement_dependency_paths(path: str, requirement: dict[str, Any]) -> set[str]:
    deps = set(REQUIREMENT_POLICY_PATHS)
    deps.add(path)
    verification = requirement.get("verification") or {}
    for value in verification.get("acceptance_evidence", []) or []:
        ref = registry_reference_path(value)
        if ref:
            deps.add(ref)
    for value in verification.get("acceptance_cold_read_test_ids", []) or []:
        ref = registry_reference_path(value)
        if ref:
            deps.add(ref)
    origin = requirement.get("origin") or {}
    ref = registry_reference_path(origin.get("introduced_by_work"))
    if ref:
        deps.add(ref)
    return deps


def risk_dependency_paths(path: str, risk: dict[str, Any]) -> set[str]:
    deps = set(RISK_POLICY_PATHS)
    deps.add(path)
    resolution = risk.get("resolution") or {}
    ref = registry_reference_path(resolution.get("authority_evidence_ref"))
    if ref:
        deps.add(ref)
    scope = risk.get("scope") or {}
    for value in scope.get("work_items", []) or []:
        ref = registry_reference_path(value)
        if ref:
            deps.add(ref)
    return deps


def validate_acceptance_dependencies(root: Path, base: str, head: str) -> list[Finding]:
    adoption = t10_adoption_sha(root, head)
    if adoption is None:
        return [Finding(T10_PATH, "T10_ADOPTION", "T10 enforcement has no immutable Git introduction commit")]
    out: list[Finding] = []
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    for before, after in edges:
        if not edge_is_enforced(root, adoption, before, after):
            continue
        changed = set(cg.changed_files(root, before, after))
        for path, record in registry_records(root, after, "requirements"):
            if record.get("status") != "ACCEPTED" or not changed.intersection(requirement_dependency_paths(path, record)):
                continue
            if not t9.requirement_acceptance_invariant(root, after, record):
                out.append(
                    Finding(
                        path,
                        "REQ_ACCEPTED_DEPENDENCY_INVARIANT",
                        f"ACCEPTED requirement lost qualifying review/cold-read evidence after a dependency change at {after[:12]}",
                    )
                )
        for path, record in registry_records(root, after, "risks"):
            if record.get("status") != "ACCEPTED" or not changed.intersection(risk_dependency_paths(path, record)):
                continue
            if not cg.risk_acceptance_satisfied(root, after, record):
                out.append(
                    Finding(
                        path,
                        "RISK_ACCEPTED_DEPENDENCY_INVARIANT",
                        f"ACCEPTED risk lost qualifying authority evidence after a dependency change at {after[:12]}",
                    )
                )
    return out


def validate_workflow_review_triggers(root: Path) -> list[Finding]:
    try:
        workflow = (root / WORKFLOW_PATH).read_text(encoding="utf-8")
        core = (root / CORE_WORKFLOW_PATH).read_text(encoding="utf-8")
    except OSError as exc:
        return [Finding(WORKFLOW_PATH, "LIVE_GATE_REVIEW_TRIGGER", f"cannot read governance workflow: {exc}")]
    required = {
        "pull_request_review": "  pull_request_review:\n    types: [submitted, edited, dismissed]\n",
        "pull_request_review_comment": "  pull_request_review_comment:\n    types: [created, edited, deleted]\n",
    }
    out: list[Finding] = []
    for event, snippet in required.items():
        if snippet not in workflow:
            out.append(
                Finding(
                    WORKFLOW_PATH,
                    "LIVE_GATE_REVIEW_TRIGGER",
                    f"{event} must rerun the live merge gate when review state changes",
                )
            )
    if "startsWith(github.event_name, 'pull_request')" not in workflow:
        out.append(
            Finding(
                WORKFLOW_PATH,
                "LIVE_GATE_PR_FAMILY",
                "review-event runs must execute the same pull-request live-gate path",
            )
        )
    if "python -m tools.governance.t10_closure" not in core:
        out.append(
            Finding(
                CORE_WORKFLOW_PATH,
                "T10_GATE_WIRING",
                "the reusable governance core must execute the T10 closure gate",
            )
        )
    return out


def run(root: Path, base: str, head: str) -> list[Finding]:
    root = root.resolve()
    out: list[Finding] = []
    out.extend(validate_integration_provenance_trust_anchor(root, base, head))
    out.extend(validate_acceptance_dependencies(root, base, head))
    out.extend(validate_workflow_review_triggers(root))
    return out


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
        print(f"ERROR T10_CLOSURE {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE T10 closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
