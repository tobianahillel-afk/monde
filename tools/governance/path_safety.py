from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

PATH_KEYS = ("read_before", "affected_docs", "affected_schemas")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


@dataclass(frozen=True)
class PathFinding:
    path: str
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule} {self.path}: {self.message}"


def relative_display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def iter_strings_for_key(value: Any, key: str) -> Iterable[str]:
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key and isinstance(current_value, list):
                for item in current_value:
                    if isinstance(item, str):
                        yield item
            yield from iter_strings_for_key(current_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings_for_key(item, key)


def validate_yaml_paths(root: Path) -> list[PathFinding]:
    findings: list[PathFinding] = []
    registry = root / "registry"
    if not registry.exists():
        return findings
    for path in sorted(registry.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue  # parse/read diagnostics belong to validate_repo.py
        for key in PATH_KEYS:
            for raw in iter_strings_for_key(data, key):
                declared = Path(raw)
                candidate = declared if declared.is_absolute() else root / declared
                if not contained(root, candidate):
                    findings.append(PathFinding(
                        relative_display(root, path),
                        "PATH_SCOPE",
                        f"{key} path escapes repository root: {raw}",
                    ))
    return findings


def validate_markdown_paths(root: Path) -> list[PathFinding]:
    findings: list[PathFinding] = []
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue  # read diagnostics belong to validate_repo.py
        for target in MARKDOWN_LINK.findall(text):
            clean = target.split("#", 1)[0].strip()
            if not clean or clean.startswith(EXTERNAL_PREFIXES):
                continue
            declared = Path(clean)
            candidate = declared if declared.is_absolute() else path.parent / declared
            if not contained(root, candidate):
                findings.append(PathFinding(
                    relative_display(root, path),
                    "MARKDOWN_SCOPE",
                    f"relative link escapes repository root: {target}",
                ))
    return findings


def validate(root: Path) -> list[PathFinding]:
    resolved = root.resolve()
    return validate_yaml_paths(resolved) + validate_markdown_paths(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MONDE repository path containment")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    args = parser.parse_args(argv)
    findings = validate(Path(args.root))
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    print(f"MONDE path-safety validation: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
