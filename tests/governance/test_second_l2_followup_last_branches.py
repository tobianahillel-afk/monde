from pathlib import Path

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc


def test_nonnegative_review_falls_through(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "changed_files", lambda *args: ["registry/reviews/R.yaml"])
    monkeypatch.setattr(
        cg,
        "show_yaml",
        lambda root, sha, path: {"status": "COMPLETE", "outcome": "APPROVE", "scope": {"work_items": ["WORK-1"]}},
    )
    assert not rc.reopening_evidence_valid(tmp_path, "b", "h", "work:WORK-1", {})


def test_progress_changed_with_no_instances(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "changed_files", lambda *args: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(cg, "show_yaml", lambda *args: {})
    assert rc.validate_progress_reopening(tmp_path, [("b", "h")]) == []
