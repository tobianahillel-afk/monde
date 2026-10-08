from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml

MODULE_PATH = Path(__file__).resolve().parents[2] / ".github/scripts/governance_l2_hardening.py"
SPEC = importlib.util.spec_from_file_location("governance_l2_hardening_materialization", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
h = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = h
SPEC.loader.exec_module(h)


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_review_import_rejects_consistent_but_false_materialization_commit(tmp_path: Path) -> None:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "materialization@example.invalid")
    git(tmp_path, "config", "user.name", "materialization")
    review = {
        "id": "REVIEW-1",
        "status": "COMPLETE",
        "outcome": "APPROVE",
        "artifact": {"commit_sha": "b" * 40},
        "reviewer": {"context_id": "ctx"},
        "external_import": {
            "mode": "PREAUTHORIZED_EXTERNAL_COMPLETION",
            "authorization_commit": None,
            "source_review_id": "SRC",
            "source_submitted_at": "2026-09-14T00:00:00Z",
            "import_commit": None,
        },
    }
    auth = {
        "record_id": "REVIEW-1",
        "imported_status": "COMPLETE",
        "artifact_commit_sha": "b" * 40,
        "source_review_id": "SRC",
        "source_submitted_at": "2026-09-14T00:00:00Z",
        "reviewer_context_id": "ctx",
        "expected_outcome": "APPROVE",
        "one_shot": True,
        "consumed_by_commit": None,
    }
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    auth_sha = commit(tmp_path, "authorize")
    review["external_import"]["authorization_commit"] = auth_sha
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    actual_import = commit(tmp_path, "actual complete materialization")

    review["external_import"]["import_commit"] = actual_import
    auth["consumed_by_commit"] = actual_import
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    legitimate_binding = commit(tmp_path, "legitimate binding")
    assert h.review_import_finalized(tmp_path, review, legitimate_binding, "registry/reviews/REVIEW-1.yaml")

    # Forge both self-declared strings consistently to a real later commit. Structural
    # comparison alone would accept this; Git history must recover actual_import.
    review["external_import"]["import_commit"] = legitimate_binding
    auth["consumed_by_commit"] = legitimate_binding
    dump(tmp_path / "registry/reviews/REVIEW-1.yaml", review)
    dump(tmp_path / "registry/status-machines.yaml", {"registry_machines": {"reviews": {"external_import_authorizations": [auth]}}})
    forged_head = commit(tmp_path, "forge consistent strings")
    assert not h.review_import_finalized(tmp_path, review, forged_head, "registry/reviews/REVIEW-1.yaml")
