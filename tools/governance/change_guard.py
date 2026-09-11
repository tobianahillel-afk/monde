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

TRANSITIONS = {
    "work-items": {
        "NOT_STARTED": {"PROPOSED", "PLANNED"},
        "PROPOSED": {"PLANNED", "CANCELLED"},
        "PLANNED": {"READY", "IN_PROGRESS", "BLOCKED", "CANCELLED"},
        "READY": {"IN_PROGRESS", "BLOCKED"},
        "IN_PROGRESS": {"PARTIAL", "BLOCKED", "IN_REVIEW", "DONE"},
        "PARTIAL": {"IN_PROGRESS", "BLOCKED", "IN_REVIEW"},
        "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
        "IN_REVIEW": {"IN_PROGRESS", "DONE", "BLOCKED"},
        "DONE": {"DEPRECATED"},
        "DEPRECATED": set(),
        "CANCELLED": set(),
        "NOT_APPLICABLE": set(),
    },
    "reviews": {
        "OPEN": {"IN_PROGRESS", "CLOSED"},
        "IN_PROGRESS": {"COMPLETE", "CLOSED"},
        "COMPLETE": {"CLOSED"},
        "CLOSED": set(),
    },
    "tests": {
        "NOT_STARTED": {"PLANNED", "READY"},
        "PLANNED": {"READY", "BLOCKED"},
        "READY": {"PASS", "FAIL", "BLOCKED"},
        "PASS": {"FAIL", "DEPRECATED"},
        "FAIL": {"READY", "BLOCKED", "DEPRECATED"},
        "BLOCKED": {"READY", "DEPRECATED"},
        "DEPRECATED": set(),
    },
}
META_PATH_PREFIXES = (".github/", "tools/governance/", "schemas/registry/", "scripts/governance_")
ADMIN_PATH_PREFIXES = ("registry/reviews/", "registry/tests/", "registry/progress/", "PROJECT_STATE.md")
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


def paths_across_sequence(root: Path, sequence: list[str]) -> list[str]:
    paths: set[str] = set()
    for before, after in zip(sequence, sequence[1:]):
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
    endpoint_files = changed_files(root, base, head)
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

    all_commits = [base] + [x for x in git(root, "rev-list", "--reverse", f"{base}..{head}").splitlines() if x]
    start = 0
    if not base_has_guard:
        start = next((i for i, sha in enumerate(all_commits) if file_exists_at(root, sha, GUARD_PATH)), len(all_commits) - 1)
    sequence = all_commits[start:]
    sequence_files = paths_across_sequence(root, sequence) if len(sequence) >= 2 else endpoint_files

    for path in sequence_files:
        kind = registry_kind(path)
        allowed = TRANSITIONS.get(kind or "")
        if not allowed or len(sequence) < 2:
            continue
        previous = show_yaml(root, sequence[0], path)
        for sha in sequence[1:]:
            current = show_yaml(root, sha, path)
            if previous and current is None:
                out.append(ChangeFinding(path, "RECORD_DELETE", f"published registry record deleted at {sha[:12]}"))
                previous = None
                continue
            if previous and current:
                if previous.get("id") != current.get("id"):
                    out.append(ChangeFinding(path, "ID_IMMUTABLE", f"registry id changed at {sha[:12]}"))
                before, after = previous.get("status"), current.get("status")
                if before != after and after not in allowed.get(str(before), set()):
                    out.append(ChangeFinding(path, "STATE_TRANSITION", f"invalid {kind} transition {before} -> {after} at {sha[:12]}"))
                if kind == "work-items" and before in ACTIVE_WORK_STATUSES and semantic_projection(previous) != semantic_projection(current):
                    scope_change = current.get("scope_change") or {}
                    if scope_change.get("approved") is not True or not scope_change.get("rationale"):
                        out.append(ChangeFinding(path, "SCOPE_DRIFT", f"semantic scope/AC/review/contracts changed at {sha[:12]} without approved scope_change rationale"))
            previous = current

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
    for path in work_paths:
        work = show_yaml(root, head, path) or {}
        plan = work.get("review_plan") or {}
        for rid in plan.get("completed_reviews", []) or []:
            review_path = f"registry/reviews/{rid}.yaml"
            review = show_yaml(root, head, review_path)
            if not review or review.get("status") not in {"COMPLETE", "CLOSED"}:
                continue
            reviewed = str((review.get("artifact") or {}).get("commit_sha") or "")
            if not reviewed or reviewed == head:
                continue
            try:
                later = changed_files(root, reviewed, head)
            except RuntimeError:
                out.append(ChangeFinding(review_path, "REVIEW_FRESHNESS", "review commit is not available in history"))
                continue
            substantive = [
                file_path
                for file_path in later
                if change_relevant_to_work(root, path, work, reviewed, head, file_path)
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
