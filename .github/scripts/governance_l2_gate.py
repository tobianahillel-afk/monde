from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import governance_l2_hardening as h

RULE_ID = "PROGRESS_LIFECYCLE_EDGE_ENFORCEMENT_V1"
BASE_REVIEW_IMPORT_FINALIZED = h.review_import_finalized


def tree_sha(root: Path, sha: str) -> str | None:
    if not h.git_ok(root, "cat-file", "-e", f"{sha}^{{commit}}"):
        return None
    value = h.git(root, "rev-parse", f"{sha}^{{tree}}").strip()
    return value if h.FULL_SHA.fullmatch(value) else None


def progress_adoption_sha(root: Path, head: str) -> str | None:
    provenance = h.load_mapping(root / "registry/integration-provenance.yaml")
    for entry in provenance.get("enforcement_adoptions", []) or []:
        if not isinstance(entry, dict) or entry.get("rule_id") != RULE_ID:
            continue
        adoption = str(entry.get("adoption_commit_sha") or "")
        guard_path = str(entry.get("guard_path") or "")
        if (
            not h.FULL_SHA.fullmatch(adoption)
            or guard_path != ".github/scripts/governance_l2_hardening.py"
            or entry.get("historical_only") is not True
            or entry.get("future_reuse_forbidden") is not True
            or not h.git_ok(root, "cat-file", "-e", f"{adoption}^{{commit}}")
            or not h.git_ok(root, "cat-file", "-e", f"{adoption}:{guard_path}")
            or not h.is_ancestor(root, adoption, head)
        ):
            return None
        parents = h.commit_parents(root, adoption)
        if len(parents) != 1 or "registry/progress/matrix.yaml" in h.changed_files(root, parents[0], adoption):
            return None
        return adoption
    return None


def review_squash_materialization_valid(root: Path, review: dict[str, Any], head: str, path: str) -> bool:
    ext = review.get("external_import") or {}
    import_commit = str(ext.get("import_commit") or "")
    review_id = str(review.get("id") or "")
    if not h.FULL_SHA.fullmatch(import_commit):
        return False
    provenance = h.load_mapping(root / "registry/integration-provenance.yaml")
    for entry in provenance.get("squash_integrations", []) or []:
        if not isinstance(entry, dict) or review_id not in (entry.get("eligible_review_ids") or []):
            continue
        source_head = str(entry.get("source_head_sha") or "")
        integrated = str(entry.get("integrated_commit_sha") or "")
        expected_tree = str(entry.get("expected_tree_sha") or "")
        if (
            entry.get("historical_only") is not True
            or entry.get("future_reuse_forbidden") is not True
            or not all(h.FULL_SHA.fullmatch(value) for value in (source_head, integrated, expected_tree))
            or not h.is_ancestor(root, import_commit, source_head)
            or not h.is_ancestor(root, integrated, head)
            or tree_sha(root, source_head) != expected_tree
            or tree_sha(root, integrated) != expected_tree
        ):
            continue
        if h.first_status_commit(root, path, str(review.get("status") or ""), source_head) != import_commit:
            continue
        return True
    return False


def review_import_finalized(root: Path, review: dict[str, Any], head: str, path: str) -> bool:
    if BASE_REVIEW_IMPORT_FINALIZED(root, review, head, path):
        return True
    if not review_squash_materialization_valid(root, review, head, path):
        return False
    ext = review.get("external_import") or {}
    if not isinstance(ext, dict) or ext.get("mode") != "PREAUTHORIZED_EXTERNAL_COMPLETION":
        return False
    import_commit = str(ext.get("import_commit") or "")
    auth_commit = str(ext.get("authorization_commit") or "")
    if (
        not h.FULL_SHA.fullmatch(auth_commit)
        or not h.git_ok(root, "cat-file", "-e", f"{auth_commit}^{{commit}}")
        or not h.is_ancestor(root, auth_commit, import_commit)
        or auth_commit == import_commit
    ):
        return False
    auth_machine = h.show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    head_machine = h.show_yaml(root, head, "registry/status-machines.yaml") or {}
    auths_before = ((((auth_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    auths_after = ((((head_machine.get("registry_machines") or {}).get("reviews") or {}).get("external_import_authorizations") or []))
    return any(isinstance(auth, dict) and h._review_authorization_matches(auth, review, None) for auth in auths_before) and any(
        isinstance(auth, dict) and h._review_authorization_matches(auth, review, import_commit) for auth in auths_after
    )


def run(root: Path, base: str, head: str) -> list[h.Finding]:
    root = root.resolve()
    edges = h.pr_edges(root, base, head)
    findings: list[h.Finding] = []
    findings.extend(h.validate_checkout_ref(root))
    findings.extend(h.validate_completed_review_immutability(root, edges))

    adoption = progress_adoption_sha(root, head)
    if adoption is None:
        findings.append(h.Finding("registry/integration-provenance.yaml", "ENFORCEMENT_ADOPTION", f"{RULE_ID} adoption provenance is missing or invalid"))
        progress_edges: list[tuple[str, str]] = []
    else:
        progress_edges = [(before, after) for before, after in edges if h.is_ancestor(root, adoption, before)]

    original = h.review_import_finalized
    h.review_import_finalized = review_import_finalized
    try:
        findings.extend(h.validate_requirement_acceptance_proof(root, edges))
        findings.extend(h.validate_progress_lifecycle(root, progress_edges))
        findings.extend(h.validate_squash_flags(root))
        findings.extend(h.validate_done_tasks_runs_and_authority(root, head))
    finally:
        h.review_import_finalized = original
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
        print(f"ERROR L2_HARDENING {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([asdict(item) for item in findings], indent=2), encoding="utf-8")
    print(f"MONDE L2 hardening gate: {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
