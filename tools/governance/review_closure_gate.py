from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc

RULE_ID = "PROGRESS_REOPENING_EVIDENCE_V1"
PROVENANCE_PATH = "registry/integration-provenance.yaml"
GUARD_PATH = "tools/governance/review_closure.py"
ACTIVATION_PATH = ".github/workflows/_governance-core.yml"


def adoption_sha(root: Path, head: str) -> str | None:
    provenance = rc.load_mapping(root / PROVENANCE_PATH)
    matches = [
        entry
        for entry in (provenance.get("enforcement_adoptions", []) or [])
        if isinstance(entry, dict) and entry.get("rule_id") == RULE_ID
    ]
    if len(matches) != 1:
        return None
    entry = matches[0]
    adoption = str(entry.get("adoption_commit_sha") or "")
    if not cg.FULL_COMMIT_SHA.fullmatch(adoption):
        return None
    if entry.get("guard_path") != GUARD_PATH or entry.get("activation_path") != ACTIVATION_PATH:
        return None
    if entry.get("historical_only") is not True or entry.get("future_reuse_forbidden") is not True:
        return None
    if not cg.commit_exists(root, adoption):
        return None
    if not cg.file_exists_at(root, adoption, GUARD_PATH) or not cg.file_exists_at(root, adoption, ACTIVATION_PATH):
        return None
    if not cg.is_ancestor(root, adoption, head):
        return None
    parents = cg.commit_parents(root, adoption)
    if len(parents) != 1:
        return None
    changed = set(cg.changed_files(root, parents[0], adoption))
    if ACTIVATION_PATH not in changed or PROVENANCE_PATH in changed:
        return None
    return adoption


def run(root: Path, base: str, head: str) -> list[rc.Finding]:
    root = root.resolve()
    _, edges = cg.pr_commit_edges(root, base, head, require_guard=False)
    findings: list[rc.Finding] = []
    findings.extend(rc.validate_done_review_substance(root))
    findings.extend(rc.validate_requirement_acceptance(root, edges))
    findings.extend(rc.validate_historical_import_authorization(root, edges))

    adoption = adoption_sha(root, head)
    if adoption is None:
        findings.append(
            rc.Finding(
                PROVENANCE_PATH,
                "ENFORCEMENT_ADOPTION",
                f"{RULE_ID} requires one exact, immutable, non-reusable activation boundary",
            )
        )
    else:
        progress_edges = [(before, after) for before, after in edges if cg.is_ancestor(root, adoption, before)]
        findings.extend(rc.validate_progress_reopening(root, progress_edges))
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
        print(f"ERROR REVIEW_CLOSURE_GATE {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE review-closure gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
