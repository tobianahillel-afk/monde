from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40


def load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = ROOT / ".github/scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


h = load("governance_l2_hardening", "governance_l2_hardening.py")
g = load("governance_l2_gate", "governance_l2_gate.py")


def test_progress_adoption_explicit_invalid_and_mutating_parent_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        g.h,
        "load_mapping",
        lambda *a: {
            "enforcement_adoptions": [
                {
                    "rule_id": g.RULE_ID,
                    "adoption_commit_sha": SHA_A,
                    "guard_path": "wrong/path.py",
                    "historical_only": True,
                    "future_reuse_forbidden": True,
                }
            ]
        },
    )
    assert g.progress_adoption_sha(tmp_path, SHA_C) is None

    monkeypatch.setattr(
        g.h,
        "load_mapping",
        lambda *a: {
            "enforcement_adoptions": [
                {
                    "rule_id": g.RULE_ID,
                    "adoption_commit_sha": SHA_A,
                    "guard_path": ".github/scripts/governance_l2_hardening.py",
                    "historical_only": True,
                    "future_reuse_forbidden": True,
                }
            ]
        },
    )
    monkeypatch.setattr(g.h, "git_ok", lambda *a: True)
    monkeypatch.setattr(g.h, "is_ancestor", lambda *a: True)
    monkeypatch.setattr(g.h, "commit_parents", lambda *a: [SHA_B])
    monkeypatch.setattr(g.h, "changed_files", lambda *a: ["registry/progress/matrix.yaml"])
    assert g.progress_adoption_sha(tmp_path, SHA_C) is None


def test_reopening_review_scope_miss_loops_to_next_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        h,
        "changed_files",
        lambda *a: ["registry/reviews/REVIEW-1.yaml", "registry/reviews/REVIEW-2.yaml"],
    )

    def show_yaml(root: Path, sha: str, path: str):
        if path.endswith("REVIEW-1.yaml"):
            return {
                "status": "COMPLETE",
                "outcome": "CHANGES_REQUIRED",
                "scope": {"work_items": ["WORK-2"]},
            }
        return {
            "status": "COMPLETE",
            "outcome": "APPROVE",
            "scope": {"work_items": ["WORK-1"]},
        }

    monkeypatch.setattr(h, "show_yaml", show_yaml)
    assert not h.reopening_triggered(tmp_path, SHA_A, SHA_B, "progress:work:WORK-1:gate")
