from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml

GLOBAL_STATUSES = {
    "NOT_STARTED", "PROPOSED", "PLANNED", "READY", "IN_PROGRESS", "PARTIAL",
    "BLOCKED", "IN_REVIEW", "DONE", "DEPRECATED", "CANCELLED", "NOT_APPLICABLE",
}
STATUS_BY_KIND = {
    "work-items": GLOBAL_STATUSES,
    "capabilities": GLOBAL_STATUSES,
    "requirements": GLOBAL_STATUSES | {"ACCEPTED", "SUPERSEDED"},
    "assumptions": {"OPEN", "VALIDATED", "REFUTED", "EXPIRED", "SUPERSEDED", "CLOSED"},
    "risks": {"OPEN", "ACCEPTED", "MITIGATED", "MATERIALIZED", "CLOSED"},
    "reviews": {"OPEN", "IN_PROGRESS", "COMPLETE", "CLOSED"},
    "tests": {"NOT_STARTED", "PLANNED", "READY", "PASS", "FAIL", "BLOCKED", "DEPRECATED"},
    "experiments": {"NOT_STARTED", "PLANNED", "READY", "IN_PROGRESS", "PASS", "FAIL", "BLOCKED", "COMPLETE", "DEPRECATED"},
}
PREFIX_BY_KIND = {
    "work-items": "WORK-", "capabilities": "CAP-", "requirements": "REQ-",
    "assumptions": "ASM-", "risks": "RISK-", "reviews": "REVIEW-",
    "tests": "TEST-", "experiments": "EXP-",
}
ID_PATTERN = re.compile(r"\b(WORK|CAP|REQ|ASM|RISK|REVIEW|TEST|EXP)-\d+\b")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    path: str
    rule: str
    message: str
    severity: str = "ERROR"

    def render(self) -> str:
        return f"{self.severity} {self.rule} {self.path}: {self.message}"


@dataclass
class Record:
    kind: str
    path: Path
    data: dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.data.get("id", ""))


class Validator:
    def __init__(self, root: Path, today: date | None = None) -> None:
        self.root = root.resolve()
        self.today = today or date.today()
        self.issues: list[Issue] = []
        self.records: list[Record] = []
        self.by_id: dict[str, Record] = {}

    def add(self, path: Path | str, rule: str, message: str, severity: str = "ERROR") -> None:
        p = str(path)
        if isinstance(path, Path):
            try:
                p = str(path.resolve().relative_to(self.root))
            except ValueError:
                p = str(path)
        self.issues.append(Issue(p, rule, message, severity))

    def load_yaml(self, path: Path) -> Any | None:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        except (OSError, yaml.YAMLError) as exc:
            self.add(path, "YAML_PARSE", str(exc))
            return None

    def discover_records(self) -> None:
        base = self.root / "registry"
        for kind, prefix in PREFIX_BY_KIND.items():
            directory = base / kind
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.yaml")):
                if path.name.startswith("_"):
                    continue
                data = self.load_yaml(path)
                if data is None:
                    continue
                if not isinstance(data, dict):
                    self.add(path, "RECORD_SHAPE", "registry record must be a YAML mapping")
                    continue
                record = Record(kind, path, data)
                self.records.append(record)
                if not record.id:
                    self.add(path, "ID_REQUIRED", "registry record is missing id")
                elif not record.id.startswith(prefix):
                    self.add(path, "ID_PREFIX", f"id {record.id!r} must start with {prefix}")
                elif record.id in self.by_id:
                    self.add(path, "ID_UNIQUE", f"duplicate id {record.id}; first seen at {self.by_id[record.id].path}")
                else:
                    self.by_id[record.id] = record

    def validate_statuses(self) -> None:
        for record in self.records:
            status = record.data.get("status")
            allowed = STATUS_BY_KIND[record.kind]
            if status not in allowed:
                self.add(record.path, "STATUS", f"invalid status {status!r} for {record.kind}; allowed={sorted(allowed)}")

    def iter_strings(self, value: Any) -> Iterable[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from self.iter_strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from self.iter_strings(item)

    def validate_references(self) -> None:
        for record in self.records:
            for text in self.iter_strings(record.data):
                for match in ID_PATTERN.finditer(text):
                    ref = match.group(0)
                    if ref != record.id and ref not in self.by_id:
                        self.add(record.path, "REFERENCE", f"unknown registry reference {ref}")

    def validate_paths(self) -> None:
        keys = ("read_before", "affected_docs", "affected_schemas")
        for record in self.records:
            for key in keys:
                values = record.data.get(key, [])
                if values is None:
                    continue
                if not isinstance(values, list):
                    self.add(record.path, "PATH_LIST", f"{key} must be a list")
                    continue
                for value in values:
                    if not isinstance(value, str):
                        self.add(record.path, "PATH_TYPE", f"{key} contains non-string path {value!r}")
                    elif not (self.root / value).exists():
                        self.add(record.path, "PATH_EXISTS", f"{key} path does not exist: {value}")

    def validate_work_graph(self) -> None:
        works = {rid: rec for rid, rec in self.by_id.items() if rec.kind == "work-items"}
        edges: dict[str, list[str]] = {}
        for wid, rec in works.items():
            deps = rec.data.get("depends_on", []) or []
            edges[wid] = []
            if not isinstance(deps, list):
                self.add(rec.path, "WORK_DEPS", "depends_on must be a list")
                continue
            for dep in deps:
                if dep not in works:
                    self.add(rec.path, "WORK_DEP_EXISTS", f"unknown work dependency {dep}")
                else:
                    edges[wid].append(dep)
            self.validate_work_tasks(rec)
            if rec.data.get("status") == "DONE":
                self.validate_done_work(rec)
        self.detect_cycles(edges, works)

    def validate_work_tasks(self, rec: Record) -> None:
        plan = rec.data.get("implementation_plan", {}) or {}
        tasks = plan.get("tasks", []) or []
        runs = plan.get("planned_runs", []) or []
        task_ids = {t.get("id") for t in tasks if isinstance(t, dict) and t.get("id")}
        for task in tasks:
            if not isinstance(task, dict):
                self.add(rec.path, "TASK_SHAPE", "task must be a mapping")
                continue
            for dep in task.get("depends_on", []) or []:
                if dep not in task_ids:
                    self.add(rec.path, "TASK_DEP", f"task {task.get('id')} depends on unknown task {dep}")
        for run in runs:
            if not isinstance(run, dict):
                self.add(rec.path, "RUN_SHAPE", "planned run must be a mapping")
                continue
            for task_id in run.get("tasks", []) or []:
                if task_id not in task_ids:
                    self.add(rec.path, "RUN_TASK", f"run {run.get('id')} references unknown task {task_id}")

    def validate_done_work(self, rec: Record) -> None:
        criteria = rec.data.get("acceptance_criteria", []) or []
        if not criteria:
            self.add(rec.path, "DONE_AC", "DONE work item must have acceptance criteria")
        for criterion in criteria:
            if not isinstance(criterion, dict) or criterion.get("status") != "DONE":
                self.add(rec.path, "DONE_AC", f"DONE work item has incomplete acceptance criterion {criterion!r}")
        completion = rec.data.get("completion", {}) or {}
        required = (
            "definition_of_ready_checked", "definition_of_done_checked", "traceability_checked",
            "review_complete", "docs_updated", "registries_updated", "project_state_updated",
        )
        for key in required:
            if completion.get(key) is not True:
                self.add(rec.path, "DONE_COMPLETION", f"DONE work item requires completion.{key}=true")
        review_plan = rec.data.get("review_plan", {}) or {}
        if review_plan.get("required_hats") and not review_plan.get("completed_reviews"):
            self.add(rec.path, "DONE_REVIEW", "DONE work item requires completed review evidence")

    def detect_cycles(self, edges: dict[str, list[str]], works: dict[str, Record]) -> None:
        state: dict[str, int] = {}

        def visit(node: str, stack: list[str]) -> None:
            marker = state.get(node, 0)
            if marker == 1:
                cycle = " -> ".join(stack + [node])
                self.add(works[node].path, "WORK_CYCLE", f"dependency cycle detected: {cycle}")
                return
            if marker == 2:
                return
            state[node] = 1
            for dep in edges.get(node, []):
                visit(dep, stack + [node])
            state[node] = 2

        for node in edges:
            visit(node, [])

    def validate_due_dates(self) -> None:
        for record in self.records:
            if record.kind == "assumptions" and record.data.get("status") == "OPEN":
                target = (record.data.get("validation") or {}).get("target_date")
                self.check_due(record, target, "ASSUMPTION_DUE")
            if record.kind == "risks" and record.data.get("status") == "OPEN":
                self.check_due(record, record.data.get("review_by"), "RISK_DUE")

    def check_due(self, record: Record, raw: Any, rule: str) -> None:
        if raw in (None, ""):
            return
        try:
            due = date.fromisoformat(str(raw))
        except ValueError:
            self.add(record.path, rule, f"invalid ISO date {raw!r}")
            return
        if due < self.today:
            self.add(record.path, rule, f"review/validation date {due.isoformat()} is overdue")

    def validate_markdown(self) -> None:
        for path in sorted(self.root.rglob("*.md")):
            if ".git" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                self.add(path, "MARKDOWN_READ", str(exc))
                continue
            canonical = "Canonical: Yes" in text and "Status: Accepted" in text
            if canonical and PLACEHOLDER.search(text):
                self.add(path, "CANONICAL_PLACEHOLDER", "Accepted canonical document contains TODO/TBD/FIXME")
            for target in MARKDOWN_LINK.findall(text):
                clean = target.split("#", 1)[0].strip()
                if not clean or clean.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                candidate = (path.parent / clean).resolve()
                if not candidate.exists():
                    self.add(path, "MARKDOWN_LINK", f"broken relative link: {target}")

    def validate_progress(self) -> None:
        path = self.root / "registry/progress/matrix.yaml"
        if not path.exists():
            self.add(path, "PROGRESS_REQUIRED", "progress matrix is missing")
            return
        data = self.load_yaml(path)
        if not isinstance(data, dict):
            return
        vocab = set(data.get("status_vocabulary", []) or [])
        if vocab != GLOBAL_STATUSES:
            self.add(path, "STATUS_VOCAB", f"progress status_vocabulary must equal canonical set; got {sorted(vocab)}")
        found: dict[str, str] = {}
        for phase in (data.get("phases") or {}).values():
            for lot in (phase.get("lots") or {}).values():
                for sublot in (lot.get("sublots") or {}).values():
                    for wid, state in (sublot.get("work_items") or {}).items():
                        found[wid] = state.get("status") if isinstance(state, dict) else None
        for wid, status in found.items():
            record = self.by_id.get(wid)
            if record is None:
                self.add(path, "PROGRESS_WORK", f"progress matrix references unknown work item {wid}")
            elif status != record.data.get("status"):
                self.add(path, "PROGRESS_STATUS", f"{wid} matrix status {status!r} != work item status {record.data.get('status')!r}")

    def validate_project_state(self) -> None:
        path = self.root / "PROJECT_STATE.md"
        if not path.exists():
            self.add(path, "PROJECT_STATE_REQUIRED", "PROJECT_STATE.md is missing")
            return
        text = path.read_text(encoding="utf-8")
        active_section = self.extract_section(text, "Active work")
        active_ids = set(re.findall(r"\bWORK-\d+\b", active_section))
        if not active_ids:
            self.add(path, "ACTIVE_WORK", "Active work section must reference at least one WORK id")
        for wid in active_ids:
            record = self.by_id.get(wid)
            if record is None:
                self.add(path, "ACTIVE_WORK", f"unknown active work item {wid}")
            elif record.data.get("status") in {"DONE", "DEPRECATED", "CANCELLED"}:
                self.add(path, "ACTIVE_WORK", f"active work item {wid} has terminal status {record.data.get('status')}")

    @staticmethod
    def extract_section(text: str, heading: str) -> str:
        pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE | re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            return ""
        start = match.end()
        nxt = re.search(r"^##\s+", text[start:], re.MULTILINE)
        return text[start:start + nxt.start()] if nxt else text[start:]

    def run(self) -> list[Issue]:
        self.discover_records()
        self.validate_statuses()
        self.validate_references()
        self.validate_paths()
        self.validate_work_graph()
        self.validate_due_dates()
        self.validate_markdown()
        self.validate_progress()
        self.validate_project_state()
        return self.issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate MONDE repository governance invariants")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument("--today", help="override current date (YYYY-MM-DD) for deterministic checks")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else None
    except ValueError:
        print("ERROR CLI --today must be ISO YYYY-MM-DD", file=sys.stderr)
        return 2
    root = Path(args.root)
    validator = Validator(root, today=today)
    issues = validator.run()
    for issue in issues:
        print(issue.render(), file=sys.stderr if issue.severity == "ERROR" else sys.stdout)
    errors = sum(issue.severity == "ERROR" for issue in issues)
    warnings = len(issues) - errors
    print(f"MONDE governance validation: {errors} error(s), {warnings} warning(s), {len(validator.records)} record(s)")
    return 1 if errors else 0


if __name__ == "__main__":  # pragma: no cover - exercised through main() in tests
    raise SystemExit(main())
