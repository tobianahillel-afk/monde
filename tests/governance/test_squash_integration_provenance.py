from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

import tools.governance.proof_contracts as proof_contracts
from tools.governance.proof_contracts import (
    git_tree_sha,
    pass_test_execution_revision_valid,
    squash_integration_revision_valid,
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def build_squash_graph(root: Path) -> tuple[str, str, str, str]:
    git(root, "init")
    git(root, "config", "user.email", "squash@example.invalid")
    git(root, "config", "user.name", "squash")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    base = commit(root, "base")

    git(root, "checkout", "-b", "source", base)
    (root / "governed.txt").write_text("execution\n", encoding="utf-8")
    execution = commit(root, "execution revision")
    (root / "governed.txt").write_text("final source tree\n", encoding="utf-8")
    source_head = commit(root, "source head")

    git(root, "checkout", "master")
    git(root, "checkout", "source", "--", ".")
    integrated = commit(root, "squash-equivalent integration")
    (root / "after.txt").write_text("after integration\n", encoding="utf-8")
    target = commit(root, "current head")
    return execution, source_head, integrated, target


def provenance(source_head: str, integrated: str, tree: str, eligible: list[str] | None = None) -> dict:
    return {
        "version": 1,
        "canonical": True,
        "squash_integrations": [
            {
                "work_item": "WORK-1",
                "source_head_sha": source_head,
                "integrated_commit_sha": integrated,
                "expected_tree_sha": tree,
                "eligible_test_ids": eligible or ["TEST-1"],
                "historical_only": True,
                "future_reuse_forbidden": True,
            }
        ],
    }


def test_squash_bridge_accepts_exact_equivalent_integrated_history(tmp_path: Path) -> None:
    execution, source_head, integrated, target = build_squash_graph(tmp_path)
    tree = git_tree_sha(tmp_path, source_head)
    assert tree is not None and tree == git_tree_sha(tmp_path, integrated)
    dump(tmp_path / "registry/integration-provenance.yaml", provenance(source_head, integrated, tree))
    test = {"id": "TEST-1", "execution": {"commit_sha": execution}}

    assert squash_integration_revision_valid(tmp_path, test, target)
    assert pass_test_execution_revision_valid(tmp_path, test, target)


def test_squash_bridge_fails_closed_for_unlisted_or_mismatched_provenance(tmp_path: Path) -> None:
    execution, source_head, integrated, target = build_squash_graph(tmp_path)
    tree = git_tree_sha(tmp_path, source_head)
    assert tree is not None
    test = {"id": "TEST-1", "execution": {"commit_sha": execution}}

    dump(tmp_path / "registry/integration-provenance.yaml", provenance(source_head, integrated, tree, ["OTHER"]))
    assert not squash_integration_revision_valid(tmp_path, test, target)

    bad = provenance(source_head, integrated, tree)
    bad["squash_integrations"].insert(0, "not-a-mapping")
    bad["squash_integrations"][1]["expected_tree_sha"] = "short"
    dump(tmp_path / "registry/integration-provenance.yaml", bad)
    assert not squash_integration_revision_valid(tmp_path, test, target)

    bad = provenance(source_head, integrated, "f" * 40)
    dump(tmp_path / "registry/integration-provenance.yaml", bad)
    assert not squash_integration_revision_valid(tmp_path, test, target)


def test_squash_bridge_requires_execution_source_and_integration_ancestry(tmp_path: Path) -> None:
    execution, source_head, integrated, target = build_squash_graph(tmp_path)
    tree = git_tree_sha(tmp_path, source_head)
    assert tree is not None
    test = {"id": "TEST-1", "execution": {"commit_sha": execution}}

    base = git(tmp_path, "merge-base", "source", "master")
    git(tmp_path, "checkout", "-b", "independent-source", base)
    (tmp_path / "independent.txt").write_text("independent\n", encoding="utf-8")
    independent_source = commit(tmp_path, "independent source head")
    independent_tree = git_tree_sha(tmp_path, independent_source)
    assert independent_tree is not None
    git(tmp_path, "checkout", "master")
    bad = provenance(independent_source, integrated, independent_tree)
    dump(tmp_path / "registry/integration-provenance.yaml", bad)
    assert not squash_integration_revision_valid(tmp_path, test, target)

    git(tmp_path, "checkout", "-b", "side", source_head)
    (tmp_path / "side.txt").write_text("side\n", encoding="utf-8")
    side_integrated = commit(tmp_path, "side integration")
    side_tree = git_tree_sha(tmp_path, side_integrated)
    assert side_tree is not None
    git(tmp_path, "checkout", "master")
    bad = provenance(source_head, side_integrated, side_tree)
    dump(tmp_path / "registry/integration-provenance.yaml", bad)
    assert not squash_integration_revision_valid(tmp_path, test, target)


def test_git_tree_sha_and_missing_target_fail_closed(tmp_path: Path, monkeypatch) -> None:
    assert git_tree_sha(tmp_path, "short") is None
    execution, source_head, integrated, _ = build_squash_graph(tmp_path)
    tree = git_tree_sha(tmp_path, source_head)
    assert tree is not None
    dump(tmp_path / "registry/integration-provenance.yaml", provenance(source_head, integrated, tree))
    test = {"id": "TEST-1", "execution": {"commit_sha": execution}}
    assert not pass_test_execution_revision_valid(tmp_path, test, "f" * 40)

    monkeypatch.setattr(proof_contracts, "current_head", lambda _root: None)
    assert not pass_test_execution_revision_valid(tmp_path, test)
