from __future__ import annotations

from pathlib import Path

import tools.governance.github_live_gate as live
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
    first = "a" * 40
    second = "b" * 40
    record = {"id": "REVIEW-X", "status": "COMPLETE", "external_import": {"import_commit": first}}
    monkeypatch.setattr(t11, "_registry_paths", lambda _r, _h, directory: iter([path]) if directory == "reviews" else iter([]))
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: record)
    monkeypatch.setattr(t11, "first_status_boundaries_full_history", lambda *_: [first, second])
    findings = t11.validate_ambiguous_import_materialization_history(tmp_path, "head")
    assert len(findings) == 1
    assert findings[0].rule == "IMPORT_FIRST_STATUS_AMBIGUOUS"
    assert first in findings[0].message and second in findings[0].message


def test_single_first_status_boundary_is_not_ambiguous(monkeypatch, tmp_path: Path) -> None:
    path = "registry/tests/TEST-X.yaml"
    first = "a" * 40
    record = {"id": "TEST-X", "status": "PASS", "external_import": {"import_commit": first}}
    monkeypatch.setattr(t11, "_registry_paths", lambda _r, _h, directory: iter([path]) if directory == "tests" else iter([]))
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: record)
    monkeypatch.setattr(t11, "first_status_boundaries_full_history", lambda *_: [first])
    assert t11.validate_ambiguous_import_materialization_history(tmp_path, "head") == []


def test_workflow_command_matching_requires_executable_argv() -> None:
    expected = ("python", "-m", "tools.governance.thread_state_poll")
    assert not t11._steps_execute_prefix({"steps": [{"run": 'echo "python -m tools.governance.thread_state_poll"'}]}, expected)
    assert not t11._steps_execute_prefix({"steps": [{"run": "# python -m tools.governance.thread_state_poll\necho safe"}]}, expected)
    assert not t11._steps_execute_prefix({"steps": [{"run": "echo 'unterminated"}]}, expected)
    assert t11._steps_execute_prefix({"steps": [{"run": "python -m \\\n tools.governance.thread_state_poll --extra value"}]}, expected)


def test_workflow_command_matching_rejects_failure_masking_step_controls() -> None:
    poll_expected = ("python", "-m", "tools.governance.thread_state_poll")
    safe_poll = {
        "if": "github.event_name == 'schedule'",
        "steps": [
            {
                "run": "python -m tools.governance.thread_state_poll",
                "continue-on-error": False,
                "env": {"GITHUB_TOKEN": "token"},
            }
        ],
    }
    assert t11._steps_execute_prefix(
        safe_poll,
        poll_expected,
        allowed_job_ifs=frozenset({"github.event_name == 'schedule'"}),
    )

    assert not t11._steps_execute_prefix(
        {**safe_poll, "continue-on-error": True},
        poll_expected,
        allowed_job_ifs=frozenset({"github.event_name == 'schedule'"}),
    )
    assert not t11._steps_execute_prefix(
        {**safe_poll, "if": "false"},
        poll_expected,
        allowed_job_ifs=frozenset({"github.event_name == 'schedule'"}),
    )

    base_step = {"run": "python -m tools.governance.thread_state_poll"}
    for controls in (
        {"continue-on-error": True},
        {"if": "false"},
        {"shell": "bash"},
        {"working-directory": "subdir"},
        {"env": {"PATH": "/tmp/fake"}},
        {"env": {"PYTHONPATH": "attacker"}},
        {"env": "not-a-map"},
    ):
        assert not t11._steps_execute_prefix(
            {"steps": [{**base_step, **controls}]},
            poll_expected,
        )

    t11_expected = ("python", "-m", "tools.governance.t11_closure", ".")
    guarded = {
        "steps": [
            {
                "if": "startsWith(inputs.event_name, 'pull_request')",
                "run": "python -m tools.governance.t11_closure . --base x --head y",
            }
        ]
    }
    assert not t11._steps_execute_prefix(guarded, t11_expected)
    assert t11._steps_execute_prefix(
        guarded,
        t11_expected,
        allowed_step_ifs=frozenset({"startsWith(inputs.event_name, 'pull_request')"}),
    )


def test_logical_run_parser_covers_nonsteps_and_trailing_continuations() -> None:
    assert t11._logical_run_commands({}) == []
    assert t11._logical_run_commands({"steps": ["bad", {"run": 123}]}) == []

    trailing = "python -m tools.governance.thread_state_poll " + "\\"
    assert t11._logical_run_commands({"steps": [{"run": trailing}]}) == [
        ["python", "-m", "tools.governance.thread_state_poll"]
    ]

    malformed_trailing = "echo 'unterminated " + "\\"
    assert t11._logical_run_commands({"steps": [{"run": malformed_trailing}]}) == [[]]


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


def test_durable_open_findings_fails_closed_when_work_cannot_load(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(live, "_load_work", lambda *_: None)
    assert live.durable_open_findings(tmp_path, "registry/work-items/WORK-X.yaml") is None
