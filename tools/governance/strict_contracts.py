from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import yaml

from .validate_repo import GLOBAL_STATUSES, Issue, PINNED_ACTION, PINNED_DOCKER, independence_rank

ACTIVE_DEPENDENCY_CONSUMERS = {"READY", "IN_PROGRESS", "PARTIAL", "IN_REVIEW", "DONE"}
USABLE_DEPENDENCY_STATES = {"IN_REVIEW", "DONE"}
TEST_ID = re.compile(r"\bTEST-\d+\b")
DONE_PROGRESS_ALLOWED = {"DONE", "NOT_APPLICABLE"}
ASSURANCE_MIN_REVIEW_RANK = {"A3": 2, "A4": 3}
WORK_PROGRESS_DIMENSIONS = (
    "docs",
    "specification_governance",
    "implementation",
    "tests",
    "scientific_validation",
    "security_review",
    "real_system_validation",
    "review",
    "dependencies",
    "traceability",
    "handover",
)
REVIEW_SEVERITY_RANK = {
    "R1_CRITICAL": 1,
    "R2_MAJOR": 2,
    "R3_MODERATE": 3,
    "R4_MINOR": 4,
    # Bounded compatibility with bootstrap-era spellings.
    "R0_CRITICAL": 1,
    "R1_BLOCKER": 1,
    "R4_LOW": 4,
}
BLOCKING_REVIEW_RANK = 2


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def load_records(root: Path, kind: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    directory = root / "registry" / kind
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = load_mapping(path)
        rid = data.get("id")
        if isinstance(rid, str):
            out[rid] = data
    return out


def iter_test_ids(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield from TEST_ID.findall(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_test_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_test_ids(item)


def review_targets(review: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    scope = review.get("scope") or {}
    if isinstance(scope, dict):
        for item in scope.get("work_items", []) or []:
            if isinstance(item, str):
                targets.add(item)
    artifact = review.get("artifact") or {}
    if isinstance(artifact, dict) and artifact.get("type") == "WORK_ITEM":
        item = artifact.get("id_or_path")
        if isinstance(item, str):
            targets.add(item)
    return targets


def validate_review_findings(path: str, review_id: str, review: dict[str, Any]) -> list[Issue]:
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


def validate_work_lifecycle(root: Path) -> list[Issue]:
    works = load_records(root, "work-items")
    reviews = load_records(root, "reviews")
    tests = load_records(root, "tests")
    issues: list[Issue] = []

    for wid, work in works.items():
        status = work.get("status")
        deps = work.get("depends_on", []) or []
        if status in ACTIVE_DEPENDENCY_CONSUMERS and isinstance(deps, list):
            allowed = {"DONE"} if status == "DONE" else USABLE_DEPENDENCY_STATES
            for dep in deps:
                target = works.get(dep)
                if target is not None and target.get("status") not in allowed:
                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "WORK_DEP_STATE", f"dependency {dep} has unusable status {target.get('status')!r} for {status}"))

        assurance_level = str(((work.get("assurance") or {}).get("level") or ""))
        declared_rank = independence_rank((work.get("review_plan") or {}).get("independence_level"))
        if assurance_level in ASSURANCE_MIN_REVIEW_RANK and declared_rank < ASSURANCE_MIN_REVIEW_RANK[assurance_level]:
            minimum = "L2" if assurance_level == "A3" else "L3"
            issues.append(Issue(f"registry/work-items/{wid}.yaml", "REVIEW_ASSURANCE_INDEPENDENCE", f"{assurance_level} requires review independence at least {minimum}"))

        if status != "DONE":
            continue

        completion = work.get("completion")
        if isinstance(completion, dict) and completion.get("specification_gates_checked") is not True:
            issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_COMPLETION", "DONE work item requires completion.specification_gates_checked=true"))

        completed = ((work.get("review_plan") or {}).get("completed_reviews", []) or [])
        for rid in completed:
            review = reviews.get(rid)
            if review is not None:
                reviewed_sha = str(((review.get("artifact") or {}).get("commit_sha") or "")).strip()
                if review.get("status") == "COMPLETE" and not reviewed_sha:
                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SHA", f"review {rid} is COMPLETE but has no artifact.commit_sha"))
                if wid not in review_targets(review):
                    issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_REVIEW_SCOPE", f"review {rid} is not structurally bound to {wid}"))
                issues.extend(validate_review_findings(f"registry/work-items/{wid}.yaml", rid, review))

        for tid in sorted(set(iter_test_ids(work.get("required_tests") or {}))):
            test = tests.get(tid)
            if test is None or test.get("status") != "PASS":
                actual = None if test is None else test.get("status")
                issues.append(Issue(f"registry/work-items/{wid}.yaml", "DONE_TEST_EVIDENCE", f"required test {tid} must exist with status PASS, got {actual!r}"))

    return issues


def validate_progress_uniqueness(root: Path) -> list[Issue]:
    path = root / "registry/progress/matrix.yaml"
    data = load_mapping(path)
    works = load_records(root, "work-items")
    seen: dict[str, str] = {}
    issues: list[Issue] = []
    expected_dimensions = set(WORK_PROGRESS_DIMENSIONS)
    for phase_name, phase in (data.get("phases") or {}).items():
        for lot_name, lot in ((phase or {}).get("lots") or {}).items():
            for sub_name, sub in ((lot or {}).get("sublots") or {}).items():
                location = f"{phase_name}/{lot_name}/{sub_name}"
                for wid, state in ((sub or {}).get("work_items") or {}).items():
                    previous = seen.get(wid)
                    if previous is not None:
                        issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_DUPLICATE", f"{wid} appears in both {previous} and {location}"))
                    else:
                        seen[wid] = location
                    if not isinstance(state, dict):
                        issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_SHAPE", f"{wid} progress entry must be a mapping"))
                        continue
                    dimensions = {key for key in state if key != "status"}
                    for key in sorted(dimensions - expected_dimensions):
                        issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_DIMENSION_KEY", f"{wid} has unknown progress dimension {key!r}"))
                    for key in sorted(dimensions & expected_dimensions):
                        value = state.get(key)
                        if value not in GLOBAL_STATUSES:
                            issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_DIMENSION_STATUS", f"{wid}.{key} has noncanonical status {value!r}"))
                        if state.get("status") == "DONE" and value == "NOT_APPLICABLE":
                            justifications = (works.get(wid) or {}).get("progress_justifications") or {}
                            reason = justifications.get(key) if isinstance(justifications, dict) else None
                            if not isinstance(reason, str) or not reason.strip():
                                issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_NA_JUSTIFICATION", f"{wid}.{key}=NOT_APPLICABLE requires a non-empty work-item progress_justifications.{key}"))
                    if state.get("status") == "DONE":
                        missing = expected_dimensions - dimensions
                        if missing:
                            issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_DONE_DIMENSION", f"{wid} DONE entry is missing dimensions {sorted(missing)}"))
                        for key in sorted(dimensions & expected_dimensions):
                            value = state.get(key)
                            if value in GLOBAL_STATUSES and value not in DONE_PROGRESS_ALLOWED:
                                issues.append(Issue("registry/progress/matrix.yaml", "PROGRESS_DONE_DIMENSION", f"{wid}.{key}={value} is incomplete for DONE"))
    return issues


def executable_manifests(root: Path) -> list[Path]:
    manifests: set[Path] = set()
    workflow_dir = root / ".github/workflows"
    if workflow_dir.exists():
        manifests.update(workflow_dir.glob("*.yml"))
        manifests.update(workflow_dir.glob("*.yaml"))
    for name in ("action.yml", "action.yaml"):
        manifests.update(root.rglob(name))
    return sorted(manifests)


def validate_action_surfaces(root: Path) -> list[Issue]:
    issues: list[Issue] = []

    def inspect(path: Path, value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "uses" and isinstance(item, str):
                    if item.startswith("./"):
                        target = (root / item[2:]).resolve()
                        if not target.exists():
                            issues.append(Issue(str(path.relative_to(root)), "ACTION_LOCAL", f"local action/workflow does not exist: {item}"))
                        elif target.is_dir() and not ((target / "action.yml").exists() or (target / "action.yaml").exists()):
                            issues.append(Issue(str(path.relative_to(root)), "ACTION_LOCAL", f"local action directory has no action.yml/action.yaml: {item}"))
                    elif item.startswith("docker://"):
                        if not PINNED_DOCKER.fullmatch(item):
                            issues.append(Issue(str(path.relative_to(root)), "ACTION_PIN", f"docker action must use sha256 digest: {item}"))
                    elif not PINNED_ACTION.fullmatch(item):
                        issues.append(Issue(str(path.relative_to(root)), "ACTION_PIN", f"action must use full commit SHA: {item}"))
                inspect(path, item)
        elif isinstance(value, list):
            for item in value:
                inspect(path, item)

    for path in executable_manifests(root):
        data = load_mapping(path)
        inspect(path, data)
    return issues


def run(root: Path) -> list[Issue]:
    root = root.resolve()
    return validate_work_lifecycle(root) + validate_progress_uniqueness(root) + validate_action_surfaces(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    issues = run(Path(args.root))
    for issue in issues:
        print(issue.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in issues], indent=2), encoding="utf-8")
    print(f"MONDE strict governance: {len(issues)} error(s)")
    return 1 if issues else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())