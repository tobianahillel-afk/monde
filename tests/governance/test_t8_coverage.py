from pathlib import Path

import tools.governance.t8_closure as t8


def matrix(status: str) -> dict:
    return {"phases": {"P": {"lots": {"L": {"sublots": {"S": {"work_items": {"WORK-1": {"status": status}}}}}}}}}


def test_target_work_changed_without_scoped_trigger_falls_through(monkeypatch, tmp_path: Path) -> None:
    target = "registry/work-items/WORK-1.yaml"
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: [target])
    monkeypatch.setattr(
        t8.cg,
        "show_yaml",
        lambda *_args: {"id": "WORK-1", "review_plan": {"open_findings": []}, "scope_change": {}},
    )
    assert not t8.target_work_reopening_triggered(tmp_path, "a", "b", "WORK-1")


def test_non_reopening_work_status_is_ignored(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t8.cg, "changed_files", lambda *args: ["registry/progress/matrix.yaml"])
    monkeypatch.setattr(t8.cg, "show_yaml", lambda _r, sha, _p: matrix("IN_PROGRESS" if sha == "a" else "IN_REVIEW"))
    assert t8.validate_work_reopenings(tmp_path, [("a", "b")]) == []
