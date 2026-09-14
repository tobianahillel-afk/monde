from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import tools.governance.change_guard as cg

ADOPTION_PATH = "tools/governance/review_closure.py"
APPROVING_OUTCOMES = {"APPROVE", "APPROVE_WITH_FOLLOWUP"}
NEGATIVE_OUTCOMES = {"CHANGES_REQUIRED", "BLOCKED"}
ASSURANCE_FLOORS = {"A0": 0, "A1": 0, "A2": 1, "A3": 2, "A4": 3}


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def review_source_provenance(review: dict[str, Any]) -> bool:
    external = review.get("external_import")
    if isinstance(external, dict):
        if nonempty(external.get("source_review_id")) and nonempty(external.get("source_submitted_at")):
            return True
    verification = review.get("verification_result") or {}
    if not isinstance(verification, dict):
        return False
    source = verification.get("source") or {}
    executor = verification.get("executor") or {}
    return bool(
        isinstance(source, dict)
        and isinstance(executor, dict)
        and nonempty(source.get("source_id"))
        and nonempty(source.get("submitted_at"))
        and nonempty(executor.get("context_id"))
    )


def substantive_review(review: dict[str, Any], minimum_rank: int = 2) -> bool:
    reviewer = review.get("reviewer") or {}
    checks = review.get("checks") or {}
    roles = review.get("roles") or []
    return bool(
        review.get("status") == "COMPLETE"
        and review.get("outcome") in APPROVING_OUTCOMES
        and isinstance(reviewer, dict)
        and cg.review_independence_rank(reviewer.get("independence_level")) >= minimum_rank
        and nonempty(reviewer.get("actor"))
        and nonempty(reviewer.get("context_id"))
        and nonempty(review.get("completed_at"))
        and isinstance(roles, list)
        and any(nonempty(role) for role in roles)
        and isinstance(checks, dict)
        and bool(checks)
        and review_source_provenance(review)
    )


def requirement_review_floor(root: Path, sha: str, requirement: dict[str, Any]) -> tuple[int, str | None]:
    origin = requirement.get("origin") or {}
    work_id = origin.get("introduced_by_work") if isinstance(origin, dict) else None
    if not isinstance(work_id, str) or not work_id.startswith("WORK-"):
        return 3, None
    work = cg.show_yaml(root, sha, f"registry/work-items/{work_id}.yaml") or {}
    assurance = str(((work.get("assurance") or {}).get("level") or ""))
    declared = cg.review_independence_rank(((work.get("review_plan") or {}).get("independence_level")))
    floor = max(ASSURANCE_FLOORS.get(assurance, 3), declared if declared >= 0 else 0)
    return floor, work_id


def cold_read_has_provenance(test: dict[str, Any], minimum_rank: int) -> bool:
    cold = test.get("acceptance_cold_read") or {}
    source = cold.get("source") or {}
    executor = cold.get("executor") or {}
    return bool(
        isinstance(cold, dict)
        and isinstance(source, dict)
        and isinstance(executor, dict)
        and nonempty(source.get("source_id"))
        and nonempty(source.get("submitted_at"))
        and nonempty(executor.get("context_id"))
        and cg.review_independence_rank(executor.get("independence_level")) >= minimum_rank
        and executor.get("fresh_context") is True
        and executor.get("authoring_context_separated") is True
    )


def validate_requirement_acceptance(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        for path in cg.changed_files(root, before, after):
            if not path.startswith("registry/requirements/") or not path.endswith(".yaml"):
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if not previous or not current or previous.get("status") != "PROPOSED" or current.get("status") != "ACCEPTED":
                continue
            floor, work_id = requirement_review_floor(root, after, current)
            verification = current.get("verification") or {}
            reviews = []
            for review_id in verification.get("acceptance_evidence", []) or []:
                if isinstance(review_id, str) and review_id.startswith("REVIEW-"):
                    review = cg.show_yaml(root, after, f"registry/reviews/{review_id}.yaml") or {}
                    if substantive_review(review, floor):
                        reviews.append(review_id)
            if not reviews:
                out.append(Finding(path, "REQ_REVIEW_ASSURANCE", f"requirement acceptance lacks substantive review evidence at owning-work floor L{floor}; owner={work_id!r}"))

            cold_floor = max(2, floor)
            cold_reads = []
            for test_id in verification.get("acceptance_cold_read_test_ids", []) or []:
                if isinstance(test_id, str) and test_id.startswith("TEST-"):
                    test = cg.show_yaml(root, after, f"registry/tests/{test_id}.yaml") or {}
                    if cold_read_has_provenance(test, cold_floor):
                        cold_reads.append(test_id)
            if not cold_reads:
                out.append(Finding(path, "REQ_COLD_READ_PROVENANCE", f"requirement acceptance lacks durable source/executor cold-read provenance at L{cold_floor}+"))
    return out


def historical_exception_match(spec: dict[str, Any], record: dict[str, Any], materialize_sha: str) -> bool:
    for exc in spec.get("historical_import_exceptions", []) or []:
        if not isinstance(exc, dict):
            continue
        if (
            exc.get("record_id") == record.get("id")
            and exc.get("imported_status") == record.get("status")
            and exc.get("import_commit") == materialize_sha
            and exc.get("historical_only") is True
            and exc.get("future_reuse_forbidden") is True
            and nonempty(exc.get("review_origin"))
        ):
            return True
    return False


def validate_historical_import_authorization(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        if not cg.file_exists_at(root, before, ADOPTION_PATH):
            continue
        for path in cg.changed_files(root, before, after):
            kind = cg.registry_kind(path)
            if not kind or kind == "progress":
                continue
            previous = cg.show_yaml(root, before, path)
            current = cg.show_yaml(root, after, path)
            if previous is not None or not current:
                continue
            spec_after = cg.canonical_machine_spec(root, after, kind)
            if current.get("status") == spec_after.get("initial"):
                continue
            external = current.get("external_import")
            if isinstance(external, dict):
                continue
            spec_before = cg.canonical_machine_spec(root, before, kind)
            if not historical_exception_match(spec_before, current, after):
                out.append(Finding(path, "HISTORICAL_IMPORT_PREAUTH", f"non-initial {kind} record must use a pre-existing, reviewed, non-reusable exception bound to {after[:12]}"))
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
                    for key, value in state.items():
                        if isinstance(value, str):
                            prefix = "work" if key == "status" else "progress:work"
                            suffix = f":{key}" if key != "status" else ""
                            out[f"{prefix}:{work_id}{suffix}"] = value
    for key, value in (data.get("quality_dimensions") or {}).items():
        if isinstance(value, str):
            out[f"progress:quality:{key}"] = value
    return out


def descendant_works(matrix: dict[str, Any], key: str) -> set[str]:
    if key.startswith("progress:work:"):
        return {key.split(":", 3)[2]}
    if key.startswith("work:"):
        return {key.split(":", 1)[1]}
    target: dict[str, Any] | None = None
    if key.startswith("progress:phase:"):
        target = (matrix.get("phases") or {}).get(key.split(":", 2)[2])
    elif key.startswith("progress:lot:"):
        phase_id, lot_id = key.split(":", 2)[2].split("/", 1)
        target = (((matrix.get("phases") or {}).get(phase_id) or {}).get("lots") or {}).get(lot_id)
    elif key.startswith("progress:sublot:"):
        phase_id, lot_id, sub_id = key.split(":", 2)[2].split("/", 2)
        target = ((((((matrix.get("phases") or {}).get(phase_id) or {}).get("lots") or {}).get(lot_id) or {}).get("sublots") or {}).get(sub_id))
    if not isinstance(target, dict):
        return set()
    works: set[str] = set()
    stack = [target]
    while stack:
        node = stack.pop()
        for work_id in (node.get("work_items") or {}):
            if isinstance(work_id, str):
                works.add(work_id)
        for child_key in ("lots", "sublots"):
            for child in (node.get(child_key) or {}).values():
                if isinstance(child, dict):
                    stack.append(child)
    return works


def reopening_evidence_valid(root: Path, before: str, after: str, key: str, matrix: dict[str, Any]) -> bool:
    target_works = descendant_works(matrix, key)
    for path in cg.changed_files(root, before, after):
        if path.startswith("registry/reviews/") and path.endswith(".yaml"):
            review = cg.show_yaml(root, after, path) or {}
            scope = review.get("scope") or {}
            progress_keys = set(scope.get("progress_keys") or []) if isinstance(scope, dict) else set()
            scoped_works = set(scope.get("work_items") or []) if isinstance(scope, dict) else set()
            if review.get("status") == "COMPLETE" and review.get("outcome") in NEGATIVE_OUTCOMES:
                if key in progress_keys or (target_works and bool(target_works & scoped_works)):
                    return True
        if path.startswith("registry/work-items/") and path.endswith(".yaml"):
            current = cg.show_yaml(root, after, path) or {}
            work_id = current.get("id")
            scope_change = current.get("scope_change") or {}
            if (
                isinstance(work_id, str)
                and work_id in target_works
                and isinstance(scope_change, dict)
                and scope_change.get("approved") is True
                and nonempty(scope_change.get("rationale"))
                and bool(scope_change.get("evidence"))
            ):
                return True
    return False


def validate_progress_reopening(root: Path, edges: list[tuple[str, str]]) -> list[Finding]:
    out: list[Finding] = []
    for before, after in edges:
        if "registry/progress/matrix.yaml" not in cg.changed_files(root, before, after):
            continue
        before_matrix = cg.show_yaml(root, before, "registry/progress/matrix.yaml") or {}
        after_matrix = cg.show_yaml(root, after, "registry/progress/matrix.yaml") or {}
        old = flatten_progress(before_matrix)
        new = flatten_progress(after_matrix)
        for key in sorted(set(old) | set(new)):
            if old.get(key) == "DONE" and new.get(key) == "IN_REVIEW" and not reopening_evidence_valid(root, before, after, key, after_matrix):
                out.append(Finding("registry/progress/matrix.yaml", "PROGRESS_REOPENING_EVIDENCE", f"{key} reopened without evidence scoped to the affected progress/work surface at {after[:12]}"))
    return out


def validate_done_review_substance(root: Path) -> list[Finding]:
    out: list[Finding] = []
    for path in sorted((root / "registry/work-items").glob("WORK-*.yaml")):
        work = cg.load_mapping(path)
        if work.get("status") != "DONE":
            continue
        target = cg.review_independence_rank(((work.get("review_plan") or {}).get("independence_level")))
        floor = max(ASSURANCE_FLOORS.get(str(((work.get("assurance") or {}).get("level") or "")), 3), target if target >= 0 else 0)
        if floor < 2:
            continue
        for review_id in ((work.get("review_plan") or {}).get("completed_reviews") or []):
            review = cg.load_mapping(root / f"registry/reviews/{review_id}.yaml")
            if review.get("status") == "COMPLETE" and cg.review_independence_rank((review.get("reviewer") or {}).get("independence_level")) >= floor and not substantive_review(review, floor):
                out.append(Finding(f"registry/reviews/{review_id}.yaml", "REVIEW_SUBSTANTIVE_L2", f"L{floor}+ completion evidence requires durable reviewer/context identity, completion time, checks, roles and source provenance"))
    return out


def run(root: Path, base: str, head: str) -> list[Finding]:
    root = root.resolve()
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    findings: list[Finding] = []
    findings.extend(validate_done_review_substance(root))
    findings.extend(validate_requirement_acceptance(root, edges))
    findings.extend(validate_historical_import_authorization(root, edges))
    findings.extend(validate_progress_reopening(root, edges))
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
        print(f"ERROR REVIEW_CLOSURE {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE review-closure hardening: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
