from pathlib import Path

import tools.governance.t11_closure as t11
import tools.governance.thread_state_poll as poller


def _bridge_fixture(monkeypatch, *, directory: str = "reviews"):
    imp = "1" * 40
    source = "2" * 40
    integrated = "3" * 40
    tree = "4" * 40
    eligible_key = "eligible_review_ids" if directory == "reviews" else "eligible_test_ids"
    entry = {
        eligible_key: ["ITEM-X"],
        "source_head_sha": source,
        "integrated_commit_sha": integrated,
        "expected_tree_sha": tree,
        "historical_only": True,
        "future_reuse_forbidden": True,
    }
    record = {"id": "ITEM-X", "status": "COMPLETE" if directory == "reviews" else "PASS"}
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: {"squash_integrations": [entry]})
    monkeypatch.setattr(t11.cg, "is_ancestor", lambda *_: True)
    monkeypatch.setattr(t11, "first_status_commit_full_history", lambda *_: imp)
    monkeypatch.setattr(t11, "_tree_sha", lambda _root, sha: tree if sha in {source, integrated} else None)
    return imp, source, integrated, tree, entry, record


def test_first_status_wrong_status_branch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t11.cg, "git", lambda *_: "a\n")
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: {"status": "OPEN"})
    assert t11.first_status_commit_full_history(tmp_path, "p", "COMPLETE", "h") is None


def test_squash_bridge_rejection_branches(monkeypatch, tmp_path: Path) -> None:
    imp, source, integrated, tree, entry, record = _bridge_fixture(monkeypatch)

    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, "bad", integrated, "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, "wrong", "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    monkeypatch.setattr(t11.cg, "is_ancestor", lambda _r, ancestor, _desc: ancestor != integrated)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    monkeypatch.setattr(t11, "first_status_commit_full_history", lambda *_: "other")
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    monkeypatch.setattr(t11.cg, "is_ancestor", lambda _r, ancestor, _desc: ancestor != imp)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    monkeypatch.setattr(t11, "_tree_sha", lambda _r, sha: "5" * 40 if sha == source else tree)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False

    _bridge_fixture(monkeypatch)
    monkeypatch.setattr(t11, "_tree_sha", lambda _r, sha: tree if sha == source else "5" * 40)
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "reviews") is False


def test_squash_bridge_test_id_and_future_reuse_branch(monkeypatch, tmp_path: Path) -> None:
    imp, _source, integrated, _tree, entry, record = _bridge_fixture(monkeypatch, directory="tests")
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "tests") is True

    bad = dict(entry, future_reuse_forbidden=False)
    monkeypatch.setattr(t11.cg, "show_yaml", lambda *_: {"squash_integrations": [None, bad]})
    assert t11.squash_bridge_allows_first_status(tmp_path, "p", record, imp, integrated, "head", "tests") is False


def test_poller_collection_nonobject_branch(monkeypatch) -> None:
    monkeypatch.setattr(poller.live, "request_data", lambda *_: ["not-an-object"])
    try:
        poller._paged("https://example.invalid/runs", "t", "workflow_runs")
    except RuntimeError as exc:
        assert "malformed" in str(exc)
    else:
        raise AssertionError("malformed collection payload must fail closed")


def test_latest_runs_keeps_newer_existing_entry(monkeypatch) -> None:
    monkeypatch.setattr(
        poller,
        "_paged",
        lambda *_a, **_k: [
            {"head_sha": "h", "run_number": 2, "id": 20},
            {"head_sha": "h", "run_number": 1, "id": 10},
        ],
    )
    assert poller.latest_completed_pr_runs("o/r", "t")["h"]["id"] == 20
