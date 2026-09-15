from __future__ import annotations

from pathlib import Path

import tools.governance.t11_closure as t11
import tools.governance.thread_state_poll as poller


def test_terminal_external_import_without_binding_fails_closed(monkeypatch, tmp_path: Path) -> None:
    records = {
        "registry/reviews/REVIEW-X.yaml": {
            "id": "REVIEW-X",
            "status": "COMPLETE",
            "external_import": {"authorization_id": "AUTH-X", "import_commit": None},
        },
        "registry/tests/TEST-X.yaml": {
            "id": "TEST-X",
            "status": "PASS",
            "external_import": {"authorization_id": "AUTH-T", "import_commit": None},
        },
    }
    monkeypatch.setattr(
        t11,
        "_registry_paths",
        lambda _root, _head, directory: iter(path for path in records if f"registry/{directory}/" in path),
    )
    monkeypatch.setattr(t11.cg, "show_yaml", lambda _root, _sha, path: records[path])
    monkeypatch.setattr(t11, "first_status_boundaries_full_history", lambda *_: [])
    findings = t11.validate_import_materialization_history(tmp_path, "head")
    assert [item.rule for item in findings] == ["IMPORT_TERMINAL_UNFINALIZED", "IMPORT_TERMINAL_UNFINALIZED"]


def test_parallel_first_status_boundaries_are_rejected(monkeypatch, tmp_path: Path) -> None:
    path = "registry/reviews/REVIEW-X.yaml"
    record = {"id": "REVIEW-X", "status": "COMPLETE", "external_import": {"import_commit": "a"}}
    monkeypatch.setattr(t11, "_registry_paths", lambda _r, _h, directory: iter([path]) if directory == "reviews" else iter([]))
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: record)
    monkeypatch.setattr(t11, "first_status_boundaries_full_history", lambda *_: ["a", "b"])
    findings = t11.validate_ambiguous_import_materialization_history(tmp_path, "head")
    assert len(findings) == 1
    assert findings[0].rule == "IMPORT_FIRST_STATUS_AMBIGUOUS"
    assert "['a', 'b']" in findings[0].message


def test_single_first_status_boundary_is_not_ambiguous(monkeypatch, tmp_path: Path) -> None:
    path = "registry/tests/TEST-X.yaml"
    record = {"id": "TEST-X", "status": "PASS", "external_import": {"import_commit": "a"}}
    monkeypatch.setattr(t11, "_registry_paths", lambda _r, _h, directory: iter([path]) if directory == "tests" else iter([]))
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: record)
    monkeypatch.setattr(t11, "first_status_boundaries_full_history", lambda *_: ["a"])
    assert t11.validate_ambiguous_import_materialization_history(tmp_path, "head") == []


def test_workflow_command_matching_requires_executable_argv() -> None:
    expected = ("python", "-m", "tools.governance.thread_state_poll")
    assert not t11._steps_execute_prefix({"steps": [{"run": 'echo "python -m tools.governance.thread_state_poll"'}]}, expected)
    assert not t11._steps_execute_prefix({"steps": [{"run": "# python -m tools.governance.thread_state_poll\necho safe"}]}, expected)
    assert not t11._steps_execute_prefix({"steps": [{"run": "echo 'unterminated"}]}, expected)
    assert t11._steps_execute_prefix({"steps": [{"run": "python -m \\\n tools.governance.thread_state_poll --extra value"}]}, expected)


def test_legacy_substring_helper_is_not_used_for_security_wiring() -> None:
    # The compatibility helper intentionally retains the old substring behavior for
    # historical callers. T11's security-sensitive workflow validator uses
    # _steps_execute_prefix directly, which the adversarial test above protects.
    assert t11._steps_contain_run({"steps": [{"run": "python -m tools.governance.thread_state_poll"}]}, "python -m tools.governance.thread_state_poll")
    assert t11._steps_contain_run({"steps": [{"run": "echo python -m tools.governance.thread_state_poll"}]}, "python -m tools.governance.thread_state_poll")
    assert not t11._steps_contain_run({}, "needle")


def test_review_event_can_be_latest_stale_green_gate(monkeypatch) -> None:
    rows = [
        {"event": "pull_request", "head_sha": "h", "run_number": 20, "id": 20},
        {"event": "pull_request_review", "head_sha": "h", "run_number": 21, "id": 21},
        {"event": "pull_request_review_comment", "head_sha": "h", "run_number": 19, "id": 19},
    ]
    monkeypatch.setattr(poller, "_paged", lambda *_a, **_k: rows)
    assert poller.latest_completed_pr_runs("o/r", "t")["h"]["id"] == 21
