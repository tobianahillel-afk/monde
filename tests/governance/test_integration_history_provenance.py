from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from tools.governance import change_guard as c


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def write(root: Path, path: str, value: object) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        target.write_text(value, encoding="utf-8")
    else:
        target.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def init_history(root: Path) -> tuple[str, str, str, str, str, str]:
    git(root, "init")
    git(root, "config", "user.email", "history@example.invalid")
    git(root, "config", "user.name", "history")
    write(root, c.GUARD_PATH, "guard\n")
    write(
        root,
        "registry/status-machines.yaml",
        {
            "registry_machines": {
                "work_items": {
                    "initial": "PROPOSED",
                    "transitions": {"IN_REVIEW": ["DONE", "IN_PROGRESS", "PARTIAL", "BLOCKED"]},
                }
            }
        },
    )
    valid = {
        "id": "WORK-1",
        "status": "IN_REVIEW",
        "assurance": {"level": "A3"},
        "affected_paths": ["registry/integration-provenance.yaml"],
        "progress_justifications": {"implementation": "one"},
    }
    write(root, "registry/work-items/WORK-1.yaml", valid)
    base = commit(root, "base")

    malformed_text = """id: WORK-1
status: IN_REVIEW
assurance:
  level: A3
affected_paths:
  - registry/integration-provenance.yaml
progress_justifications:
  implementation: one
progress_justifications:
  implementation: two
"""
    write(root, "registry/work-items/WORK-1.yaml", malformed_text)
    malformed = commit(root, "historical malformed yaml")
    malformed_blob = c.blob_sha_at(root, malformed, "registry/work-items/WORK-1.yaml")
    assert malformed_blob is not None

    write(root, "unrelated.txt", "carry malformed blob forward\n")
    carried = commit(root, "carry malformed blob unchanged")
    assert c.blob_sha_at(root, carried, "registry/work-items/WORK-1.yaml") == malformed_blob

    valid["progress_justifications"] = {"implementation": "two"}
    write(root, "registry/work-items/WORK-1.yaml", valid)
    repaired = commit(root, "repair duplicate key")
    repaired_blob = c.blob_sha_at(root, repaired, "registry/work-items/WORK-1.yaml")
    assert repaired_blob is not None
    return base, malformed, malformed_blob, carried, repaired, repaired_blob


def provenance(path: str, malformed: str, malformed_blob: str, repaired: str, repaired_blob: str) -> dict:
    return {
        "version": 1,
        "canonical": True,
        "historical_malformed_yaml": [
            {
                "path": path,
                "malformed_commit_sha": malformed,
                "malformed_blob_sha": malformed_blob,
                "repaired_commit_sha": repaired,
                "repaired_blob_sha": repaired_blob,
                "historical_only": True,
                "future_reuse_forbidden": True,
            }
        ],
    }


def test_exact_malformed_history_does_not_become_delete_and_reintroduction(tmp_path: Path) -> None:
    base, malformed, malformed_blob, carried, repaired, repaired_blob = init_history(tmp_path)
    path = "registry/work-items/WORK-1.yaml"
    write(tmp_path, "registry/integration-provenance.yaml", provenance(path, malformed, malformed_blob, repaired, repaired_blob))
    head = commit(tmp_path, "bind historical exception")

    findings = c.validate(tmp_path, base, head)
    assert not [finding for finding in findings if finding.rule in {"RECORD_DELETE", "STATE_INITIAL"}]
    assert c.historical_malformed_yaml_allowed(tmp_path, path, malformed, head)
    assert c.historical_malformed_yaml_allowed(tmp_path, path, carried, head)
    assert c.historical_malformed_yaml_allowed(tmp_path, path, carried, head, repaired_sha=repaired)

    bad = provenance(path, malformed, "f" * 40, repaired, repaired_blob)
    write(tmp_path, "registry/integration-provenance.yaml", bad)
    bad_head = commit(tmp_path, "corrupt historical exception")
    rules = [finding.rule for finding in c.validate(tmp_path, base, bad_head)]
    assert "RECORD_DELETE" in rules
    assert "STATE_INITIAL" in rules


def test_malformed_history_exception_fails_closed_on_structure_flags_and_repair(tmp_path: Path) -> None:
    _, malformed, malformed_blob, carried, repaired, repaired_blob = init_history(tmp_path)
    path = "registry/work-items/WORK-1.yaml"
    exact = provenance(path, malformed, malformed_blob, repaired, repaired_blob)
    exact["historical_malformed_yaml"].insert(0, "not-a-mapping")
    write(tmp_path, "registry/integration-provenance.yaml", exact)
    head = commit(tmp_path, "exact exception after nonmapping")
    assert c.historical_malformed_yaml_allowed(tmp_path, path, carried, head)

    variants = []
    wrong_path = provenance("registry/work-items/OTHER.yaml", malformed, malformed_blob, repaired, repaired_blob)
    variants.append(wrong_path)
    wrong_malformed = provenance(path, "f" * 40, malformed_blob, repaired, repaired_blob)
    variants.append(wrong_malformed)
    bad_repair_format = provenance(path, malformed, malformed_blob, "short", repaired_blob)
    variants.append(bad_repair_format)
    bad_blob_format = provenance(path, malformed, "short", repaired, repaired_blob)
    variants.append(bad_blob_format)
    bad_flags = provenance(path, malformed, malformed_blob, repaired, repaired_blob)
    bad_flags["historical_malformed_yaml"][0]["historical_only"] = False
    variants.append(bad_flags)
    bad_reuse_flag = provenance(path, malformed, malformed_blob, repaired, repaired_blob)
    bad_reuse_flag["historical_malformed_yaml"][0]["future_reuse_forbidden"] = False
    variants.append(bad_reuse_flag)
    wrong_repaired_blob = provenance(path, malformed, malformed_blob, repaired, "e" * 40)
    variants.append(wrong_repaired_blob)

    for index, value in enumerate(variants):
        write(tmp_path, "registry/integration-provenance.yaml", value)
        variant_head = commit(tmp_path, f"bad exception {index}")
        assert not c.historical_malformed_yaml_allowed(tmp_path, path, carried, variant_head)

    write(tmp_path, "registry/integration-provenance.yaml", provenance(path, malformed, malformed_blob, repaired, repaired_blob))
    good_head = commit(tmp_path, "restore exact exception")
    assert not c.historical_malformed_yaml_allowed(tmp_path, path, carried, good_head, repaired_sha="f" * 40)


def test_malformed_history_requires_exact_blob_and_ancestry(tmp_path: Path) -> None:
    _, malformed, malformed_blob, carried, repaired, repaired_blob = init_history(tmp_path)
    path = "registry/work-items/WORK-1.yaml"

    wrong_malformed_blob = provenance(path, malformed, "d" * 40, repaired, repaired_blob)
    write(tmp_path, "registry/integration-provenance.yaml", wrong_malformed_blob)
    head = commit(tmp_path, "wrong malformed blob")
    assert not c.historical_malformed_yaml_allowed(tmp_path, path, carried, head)

    git(tmp_path, "checkout", "-b", "side", malformed)
    write(tmp_path, path, {"id": "WORK-1", "status": "IN_REVIEW"})
    side_repair = commit(tmp_path, "side repair")
    side_blob = c.blob_sha_at(tmp_path, side_repair, path)
    assert side_blob is not None
    git(tmp_path, "checkout", "master")
    write(tmp_path, "registry/integration-provenance.yaml", provenance(path, malformed, malformed_blob, side_repair, side_blob))
    current = commit(tmp_path, "point at nonancestor repair")
    assert not c.historical_malformed_yaml_allowed(tmp_path, path, carried, current)

    assert c.blob_sha_at(tmp_path, "f" * 40, path) is None
