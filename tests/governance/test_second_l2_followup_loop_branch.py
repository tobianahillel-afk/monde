from pathlib import Path

import tools.governance.change_guard as cg
import tools.governance.review_closure as rc


def test_progress_loop_continues_after_non_reopening_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cg, "changed_files", lambda *args: ["registry/progress/matrix.yaml"])
    values = {
        ("b", "registry/progress/matrix.yaml"): {"reopen": "DONE", "stable": "READY"},
        ("h", "registry/progress/matrix.yaml"): {"reopen": "IN_REVIEW", "stable": "READY"},
    }
    monkeypatch.setattr(cg, "show_yaml", lambda root, sha, path: values[(sha, path)])
    monkeypatch.setattr(rc, "flatten_progress", lambda value: value)
    monkeypatch.setattr(rc, "reopening_evidence_valid", lambda *args: False)
    findings = rc.validate_progress_reopening(tmp_path, [("b", "h")])
    assert [item.rule for item in findings] == ["PROGRESS_REOPENING_EVIDENCE"]
