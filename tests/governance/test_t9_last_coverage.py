from pathlib import Path

import tools.governance.t9_closure as t9


def test_base_scope_skips_active_low_assurance_and_wrong_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9.cg, "git", lambda *_: "registry/work-items/W1.yaml\nregistry/work-items/W2.yaml")
    records = {
        "registry/work-items/W1.yaml": {
            "status": "IN_REVIEW", "assurance": {"level": "A2"},
            "scope_change": {"approved": True}, "affected_paths": ["registry/content-identity.yaml"],
        },
        "registry/work-items/W2.yaml": {
            "status": "IN_REVIEW", "assurance": {"level": "A3"},
            "scope_change": {"approved": True}, "affected_paths": ["README.md"],
        },
    }
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, _s, path: records[path])
    assert not t9.base_preexisting_work_covers(tmp_path, "base", "registry/content-identity.yaml")


def test_policy_authority_skips_edges_without_protected_changes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: ["README.md"])
    assert t9.validate_base_preexisting_policy_authority(tmp_path, "base", "head") == []


def test_reopening_handles_nonlist_findings_and_nonmatching_status(monkeypatch, tmp_path: Path) -> None:
    work = "registry/work-items/WORK-1.yaml"
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: [work])
    monkeypatch.setattr(
        t9.cg,
        "show_yaml",
        lambda _r, sha, _p: {
            "review_plan": {"open_findings": "bad"},
            "scope_change": {"approved": True, "rationale": "already approved"},
        },
    )
    assert not t9.new_reopening_trigger(tmp_path, "before", "after", "WORK-1")

    monkeypatch.setattr(t9, "t9_adoption_sha", lambda *_: "adopt")
    monkeypatch.setattr(t9.cg, "pr_commit_edges", lambda *a, **k: ([], [("pre", "post")]))
    monkeypatch.setattr(t9.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t9.cg, "changed_files", lambda *_: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(t9.t8, "matrix_work_statuses", lambda data: {"WORK-1": data["status"]})
    monkeypatch.setattr(t9.cg, "show_yaml", lambda _r, sha, _p: {"status": "IN_REVIEW"})
    assert t9.validate_new_reopening_triggers(tmp_path, "base", "head") == []
