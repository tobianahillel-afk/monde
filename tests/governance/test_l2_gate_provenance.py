from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / ".github/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("governance_l2_gate_test", SCRIPTS / "governance_l2_gate.py")
assert SPEC is not None and SPEC.loader is not None
g = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = g
SPEC.loader.exec_module(g)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def init(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "gate@example.invalid")
    git(root, "config", "user.name", "gate")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_progress_adoption_is_exact_and_nonreusable(tmp_path: Path) -> None:
    init(tmp_path)
    dump(tmp_path / ".github/scripts/governance_l2_hardening.py", {"guard": True})
    adoption = commit(tmp_path, "adopt guard")
    dump(tmp_path / "registry/integration-provenance.yaml", {"enforcement_adoptions": [{"rule_id": g.RULE_ID, "adoption_commit_sha": adoption, "guard_path": ".github/scripts/governance_l2_hardening.py", "historical_only": True, "future_reuse_forbidden": True}]})
    head = commit(tmp_path, "record adoption")
    assert g.progress_adoption_sha(tmp_path, head) == adoption
    dump(tmp_path / "registry/integration-provenance.yaml", {"enforcement_adoptions": [{"rule_id": g.RULE_ID, "adoption_commit_sha": adoption, "guard_path": ".github/scripts/governance_l2_hardening.py", "historical_only": False, "future_reuse_forbidden": True}]})
    assert g.progress_adoption_sha(tmp_path, head) is None


def build_squash_history(root: Path) -> tuple[str, str, str, str, dict]:
    init(root)
    dump(root / "seed.txt", "seed")
    base = commit(root, "base")
    git(root, "checkout", "-b", "source")
    review = {"id": "REVIEW-1", "status": "COMPLETE", "external_import": {"import_commit": None}}
    dump(root / "registry/reviews/REVIEW-1.yaml", review)
    import_sha = commit(root, "materialize review")
    review["external_import"]["import_commit"] = import_sha
    dump(root / "registry/reviews/REVIEW-1.yaml", review)
    source_head = commit(root, "bind review")
    source_tree = git(root, "rev-parse", f"{source_head}^{{tree}}")
    git(root, "checkout", "-b", "integrated", base)
    git(root, "read-tree", "--reset", "-u", source_head)
    integrated = commit(root, "squash-equivalent tree")
    assert git(root, "rev-parse", f"{integrated}^{{tree}}") == source_tree
    return import_sha, source_head, integrated, source_tree, review


def test_review_squash_bridge_requires_explicit_review_id(tmp_path: Path) -> None:
    import_sha, source_head, integrated, tree, review = build_squash_history(tmp_path)
    provenance = {"squash_integrations": [{"source_head_sha": source_head, "integrated_commit_sha": integrated, "expected_tree_sha": tree, "eligible_review_ids": ["REVIEW-1"], "historical_only": True, "future_reuse_forbidden": True}]}
    dump(tmp_path / "registry/integration-provenance.yaml", provenance)
    head = commit(tmp_path, "record provenance")
    assert g.review_squash_materialization_valid(tmp_path, review, head, "registry/reviews/REVIEW-1.yaml")
    provenance["squash_integrations"][0]["eligible_review_ids"] = ["REVIEW-OTHER"]
    dump(tmp_path / "registry/integration-provenance.yaml", provenance)
    assert not g.review_squash_materialization_valid(tmp_path, review, head, "registry/reviews/REVIEW-1.yaml")
