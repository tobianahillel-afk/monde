from __future__ import annotations

import pytest

import tools.governance.thread_state_poll as poller


def test_paged_list_and_collection(monkeypatch) -> None:
    calls: list[str] = []

    def fake_request(url: str, _token: str):
        calls.append(url)
        return [{"id": 1}]

    monkeypatch.setattr(poller.live, "request_data", fake_request)
    assert poller._paged("https://example.invalid/items", "t") == [{"id": 1}]
    assert "per_page=100&page=1" in calls[0]

    monkeypatch.setattr(poller.live, "request_data", lambda *_: {"workflow_runs": [{"id": 2}]})
    assert poller._paged("https://example.invalid/runs?x=1", "t", "workflow_runs") == [{"id": 2}]


def test_paged_rejects_malformed_and_unbounded(monkeypatch) -> None:
    monkeypatch.setattr(poller.live, "request_data", lambda *_: {"bad": []})
    with pytest.raises(RuntimeError, match="malformed"):
        poller._paged("https://example.invalid", "t", "workflow_runs")

    monkeypatch.setattr(poller.live, "request_data", lambda *_: [{} for _ in range(100)])
    with pytest.raises(RuntimeError, match="pagination exceeded"):
        poller._paged("https://example.invalid", "t")


def test_open_prs_and_latest_runs_include_review_family(monkeypatch) -> None:
    rows = [
        {"event": "pull_request", "head_sha": "h", "run_number": 1, "id": 10},
        {"event": "pull_request_review", "head_sha": "h", "run_number": 2, "id": 20},
        {"event": "pull_request_review_comment", "head_sha": "other", "run_number": 3, "id": 30},
        {"event": "push", "head_sha": "h", "run_number": 99, "id": 99},
        {"event": "pull_request", "head_sha": "", "run_number": 100, "id": 100},
    ]

    def fake_paged(url, _token, collection_key=None):
        if "/pulls?" in url:
            return [{"number": 1}]
        assert "event=pull_request" not in url
        assert collection_key == "workflow_runs"
        return rows

    monkeypatch.setattr(poller, "_paged", fake_paged)
    assert poller.open_pull_requests("o/r", "t") == [{"number": 1}]
    latest = poller.latest_completed_pr_runs("o/r", "t")
    assert latest["h"]["id"] == 20
    assert latest["other"]["id"] == 30


def test_latest_runs_keeps_newer_existing_entry(monkeypatch) -> None:
    monkeypatch.setattr(
        poller,
        "_paged",
        lambda *_a, **_k: [
            {"event": "pull_request_review", "head_sha": "h", "run_number": 2, "id": 20},
            {"event": "pull_request", "head_sha": "h", "run_number": 1, "id": 10},
        ],
    )
    assert poller.latest_completed_pr_runs("o/r", "t")["h"]["id"] == 20


def test_rerun_workflow_validates_status(monkeypatch) -> None:
    seen: list[object] = []

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        seen.extend([request, timeout])
        return Response()

    monkeypatch.setattr(poller.urllib.request, "urlopen", fake_urlopen)
    poller.rerun_workflow("o/r", 7, "tok")
    assert seen[1] == 20

    class BadResponse(Response):
        status = 200

    monkeypatch.setattr(poller.urllib.request, "urlopen", lambda *_a, **_k: BadResponse())
    with pytest.raises(RuntimeError, match="unexpected rerun"):
        poller.rerun_workflow("o/r", 7, "tok")


def test_poll_reruns_only_stale_successful_gate(monkeypatch) -> None:
    prs = [
        {"number": 1, "head": {"sha": "stale"}},
        {"number": 2, "head": {"sha": "clean"}},
        {"number": 3, "head": {"sha": "failed"}},
        {"number": "bad", "head": {"sha": "bad"}},
        {"number": 5, "head": {}},
    ]
    runs = {
        "stale": {"id": 101, "conclusion": "success"},
        "clean": {"id": 102, "conclusion": "success"},
        "failed": {"id": 103, "conclusion": "failure"},
        "bad": {"id": 104, "conclusion": "success"},
    }
    monkeypatch.setattr(poller, "open_pull_requests", lambda *_: prs)
    monkeypatch.setattr(poller, "latest_completed_pr_runs", lambda *_: runs)
    monkeypatch.setattr(
        poller.live,
        "fetch_threads",
        lambda _repo, number, _token: [{"isResolved": False}] if number == 1 else [{"isResolved": True}],
    )
    reruns: list[int] = []
    monkeypatch.setattr(poller, "rerun_workflow", lambda _repo, run_id, _token: reruns.append(run_id))
    assert poller.poll("o/r", "t") == [101]
    assert reruns == [101]


def test_poll_fails_closed_on_missing_success_run_id(monkeypatch) -> None:
    monkeypatch.setattr(poller, "open_pull_requests", lambda *_: [{"number": 1, "head": {"sha": "h"}}])
    monkeypatch.setattr(poller, "latest_completed_pr_runs", lambda *_: {"h": {"id": "bad", "conclusion": "success"}})
    monkeypatch.setattr(poller.live, "fetch_threads", lambda *_: [{"isResolved": False}])
    with pytest.raises(RuntimeError, match="no numeric id"):
        poller.poll("o/r", "t")


def test_main_paths(monkeypatch, capsys) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert poller.main() == 2
    assert "GITHUB_REPOSITORY" in capsys.readouterr().err

    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(poller, "poll", lambda *_: [1, 2])
    assert poller.main() == 0
    assert "reran 2" in capsys.readouterr().out

    monkeypatch.setattr(poller, "poll", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    assert poller.main() == 2
    assert "ERROR THREAD_STATE_POLL: boom" in capsys.readouterr().err
