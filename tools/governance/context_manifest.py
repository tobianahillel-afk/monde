from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import yaml

REGISTRY_ID = re.compile(r"\b(?:WORK|CAP|REQ|ASM|RISK|REVIEW|TEST|EXP|DEP)-\d+\b")
ACTIVE_WORK_STATUSES = {"READY", "IN_PROGRESS", "PARTIAL", "BLOCKED", "IN_REVIEW"}


def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "git failed")
    return p.stdout


def changed(root: Path, base: str, head: str) -> list[str]:
    return [x for x in git(root, "diff", "--name-only", f"{base}..{head}").splitlines() if x]


def load(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def record_refs(data: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for text in iter_strings(data):
        refs.update(REGISTRY_ID.findall(text))
    rid = data.get("id")
    if isinstance(rid, str):
        refs.discard(rid)
    return refs


def record_index(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    out: dict[str, tuple[Path, dict[str, Any]]] = {}
    registry = root / "registry"
    if not registry.exists():
        return out
    for path in sorted(registry.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = load(path)
        rid = data.get("id")
        if isinstance(rid, str):
            out[rid] = (path, data)
    return out


def active_work(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted((root / "registry/work-items").glob("WORK-*.yaml")):
        if load(p).get("status") in ACTIVE_WORK_STATUSES:
            out.append(p)
    return out


def declared_paths(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("read_before", "affected_docs", "affected_schemas", "affected_paths"):
        values = data.get(key, []) or []
        if isinstance(values, list):
            out.extend(x for x in values if isinstance(x, str))
    plan = data.get("implementation_plan") or {}
    if isinstance(plan, dict):
        for task in plan.get("tasks", []) or []:
            if not isinstance(task, dict):
                continue
            files = task.get("expected_files", []) or []
            if isinstance(files, list):
                out.extend(x for x in files if isinstance(x, str))
    return out


def path_matches(path: str, declarations: Iterable[str]) -> bool:
    for raw in declarations:
        if raw.endswith("/") and path.startswith(raw):
            return True
        if path == raw:
            return True
    return False


def dependency_closure(records: dict[str, tuple[Path, dict[str, Any]]], seeds: set[str]) -> set[str]:
    forward = {rid: {ref for ref in record_refs(data) if ref in records} for rid, (_, data) in records.items()}
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, targets in forward.items():
        for target in targets:
            reverse[target].add(source)

    selected = {rid for rid in seeds if rid in records}
    queue = deque(sorted(selected))
    while queue:
        rid = queue.popleft()
        neighbors = forward.get(rid, set()) | reverse.get(rid, set())
        for neighbor in sorted(neighbors):
            if neighbor in selected:
                continue
            selected.add(neighbor)
            queue.append(neighbor)
    return selected


def build(root: Path, base: str, head: str) -> dict[str, Any]:
    root = root.resolve()
    files = changed(root, base, head)
    works = active_work(root)
    records = record_index(root)

    must = ["README.md", "AGENTS.md", "docs/00_START_HERE.md", "PROJECT_STATE.md"]
    should: list[str] = []
    ondemand: list[str] = []
    levels: list[Any] = []
    seeds: set[str] = set()
    active_ids: set[str] = set()

    for p in works:
        d = load(p)
        rid = d.get("id")
        if isinstance(rid, str):
            seeds.add(rid)
            active_ids.add(rid)
        must.append(str(p.relative_to(root)))
        must.extend(d.get("read_before", []) or [])
        should.extend(d.get("affected_docs", []) or [])
        ondemand.extend(d.get("affected_schemas", []) or [])
        levels.append((d.get("assurance") or {}).get("level"))

    for rid, (path, data) in records.items():
        rel = str(path.relative_to(root))
        if rel in files:
            seeds.add(rid)
        if rid.startswith("WORK-") and any(path_matches(fp, declared_paths(data)) for fp in files):
            seeds.add(rid)

    selected = dependency_closure(records, seeds)
    impacted_work = sorted(rid for rid in selected if rid.startswith("WORK-") and rid not in active_ids)

    for rid in sorted(selected):
        path, data = records[rid]
        rel = str(path.relative_to(root))
        if rel not in must:
            should.append(rel)
        if rid.startswith("WORK-"):
            should.extend(data.get("read_before", []) or [])
            should.extend(data.get("affected_docs", []) or [])
            ondemand.extend(data.get("affected_schemas", []) or [])
        if rid.startswith("TEST-"):
            location = data.get("location") or {}
            if isinstance(location, dict):
                test_path = location.get("test_path")
                if isinstance(test_path, str):
                    should.append(test_path)

    for fp in files:
        if fp.endswith((".py", ".yml", ".yaml", ".json")):
            should.append(fp)

    def uniq(values: Iterable[Any]) -> list[str]:
        return list(dict.fromkeys(x for x in values if isinstance(x, str)))

    must = uniq(must)
    should = [x for x in uniq(should) if x not in must]
    ondemand = [x for x in uniq(ondemand) if x not in must and x not in should]
    est = sum((root / x).stat().st_size for x in must if (root / x).exists()) // 4

    return {
        "base_sha": base,
        "head_sha": head,
        "active_work": [p.stem for p in works],
        "impacted_work": impacted_work,
        "dependency_records": sorted(selected),
        "assurance_levels": levels,
        "changed_files": files,
        "context": {
            "must_read": must,
            "should_read": should,
            "on_demand": ondemand,
            "estimated_must_read_tokens": est,
            "budget_tier": "T0" if est <= 5000 else "T1" if est <= 20000 else "T2",
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("root", nargs="?", default=".")
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    try:
        data = build(Path(a.root).resolve(), a.base, a.head)
    except RuntimeError as exc:
        print(f"ERROR CONTEXT {exc}")
        return 2
    Path(a.out).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"MONDE context manifest: {len(data['context']['must_read'])} MUST_READ files")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())