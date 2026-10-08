from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import governance_l2_hardening as h

TEST_ID = re.compile(r"\bTEST-\d+\b")


def tree_sha(root: Path, sha: str) -> str | None:
    if not h.git_ok(root, "cat-file", "-e", f"{sha}^{{commit}}"):
        return None
    value = h.git(root, "rev-parse", f"{sha}^{{tree}}").strip()
    return value if h.FULL_SHA.fullmatch(value) else None


def test_squash_materialization_valid(root: Path, test: dict[str, Any], head: str, path: str) -> bool:
    ext = test.get("external_import") or {}
    import_commit = str(ext.get("import_commit") or "")
    test_id = str(test.get("id") or "")
    if not h.FULL_SHA.fullmatch(import_commit):
        return False
    provenance = h.load_mapping(root / "registry/integration-provenance.yaml")
    for entry in provenance.get("squash_integrations", []) or []:
        if not isinstance(entry, dict) or test_id not in (entry.get("eligible_test_ids") or []):
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
        if h.first_status_commit(root, path, str(test.get("status") or ""), source_head) != import_commit:
            continue
        return True
    return False


def test_import_finalized(root: Path, test: dict[str, Any], head: str, path: str) -> bool:
    if h.test_import_finalized(root, test, head, path):
        return True
    if not test_squash_materialization_valid(root, test, head, path):
        return False
    ext = test.get("external_import") or {}
    source = str(ext.get("authorization_source") or "")
    match = re.fullmatch(r"registry/status-machines\.yaml@([0-9a-f]{40})#.+", source)
    import_commit = str(ext.get("import_commit") or "")
    if match is None:
        return False
    auth_commit = match.group(1)
    if (
        not h.git_ok(root, "cat-file", "-e", f"{auth_commit}^{{commit}}")
        or not h.is_ancestor(root, auth_commit, import_commit)
        or auth_commit == import_commit
    ):
        return False
    before_machine = h.show_yaml(root, auth_commit, "registry/status-machines.yaml") or {}
    after_machine = h.show_yaml(root, head, "registry/status-machines.yaml") or {}
    before_auths = ((((before_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    after_auths = ((((after_machine.get("registry_machines") or {}).get("tests") or {}).get("external_execution_import_authorizations") or []))
    return any(isinstance(auth, dict) and h._test_authorization_matches(auth, test, None) for auth in before_auths) and any(
        isinstance(auth, dict) and h._test_authorization_matches(auth, test, import_commit) for auth in after_auths
    )


def iter_test_ids(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield from TEST_ID.findall(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_test_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_test_ids(item)


def validate_done_test_imports(root: Path, head: str) -> list[h.Finding]:
    findings: list[h.Finding] = []
    for work_path in sorted((root / "registry/work-items").glob("WORK-*.yaml")):
        work = h.load_mapping(work_path)
        if work.get("status") != "DONE":
            continue
        for test_id in sorted(set(iter_test_ids(work.get("required_tests") or {}))):
            path = f"registry/tests/{test_id}.yaml"
            test = h.load_mapping(root / path)
            if test.get("external_import") is not None and not test_import_finalized(root, test, head, path):
                findings.append(h.Finding(str(work_path.relative_to(root)), "DONE_TEST_IMPORT_MATERIALIZATION", f"required imported test {test_id} is not bound to its real result-import/authorization-consumption history"))
    return findings


def run(root: Path, base: str, head: str) -> list[h.Finding]:
    del base
    return validate_done_test_imports(root.resolve(), head)
