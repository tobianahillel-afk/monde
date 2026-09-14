import json
from pathlib import Path

import yaml

from tools.governance import github_live_gate as g


class Resp:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self):
        return json.dumps(self.data).encode()


def test_request_data_and_json(monkeypatch):
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda req, timeout: Resp({"x": 1}))
    assert g.request_data("https://x.test", "t") == {"x": 1}
    assert g.request_json("https://x.test", "t") == {"x": 1}
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda req, timeout: Resp([1]))
    assert g.request_data("https://x.test", "t") == [1]
    try:
        g.request_json("https://x.test", "t")
    except RuntimeError:
        pass
    else:
        assert False


def test_graphql_pagination_and_errors(monkeypatch):
    pages = iter([
        {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"id": "a"}, "bad"], "pageInfo": {"hasNextPage": True, "endCursor": "c"}}}}}},
        {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"id": "b"}], "pageInfo": {"hasNextPage": False}}}}}},
    ])
    monkeypatch.setattr(g, "request_json", lambda *a, **k: next(pages))
    assert [item["id"] for item in g.fetch_threads("o/r", 1, "t")] == ["a", "b"]

    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"errors": ["x"]})
    try:
        g.fetch_threads("o/r", 1, "t")
    except RuntimeError:
        pass
    else:
        assert False

    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {}})
    try:
        g.fetch_threads("o/r", 1, "t")
    except RuntimeError:
        pass
    else:
        assert False

    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": []}}}})
    try:
        g.fetch_threads("o/r", 1, "t")
    except RuntimeError:
        pass
    else:
        assert False

    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": "bad", "pageInfo": {}}}}}})
    try:
        g.fetch_threads("o/r", 1, "t")
    except RuntimeError:
        pass
    else:
        assert False

    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True}}}}}})
    try:
        g.fetch_threads("o/r", 1, "t")
    except RuntimeError:
        pass
    else:
        assert False


def test_fetch_reviews_wrapper(monkeypatch):
    monkeypatch.setattr(g, "_paginate_graphql", lambda *a: [{"id": "r"}])
    assert g.fetch_reviews("o/r", 1, "t") == [{"id": "r"}]


def test_independent_exact_head_approvers_latest_state():
    reviews = [
        {"author": {"login": ""}, "commit": {"oid": "h"}, "submittedAt": "1", "state": "APPROVED"},
        {"author": {"login": "author"}, "commit": {"oid": "h"}, "submittedAt": "1", "state": "APPROVED"},
        {"author": {"login": "old"}, "commit": {"oid": "other"}, "submittedAt": "1", "state": "APPROVED"},
        {"author": {"login": "reviewer"}, "commit": {"oid": "h"}, "submittedAt": "1", "state": "APPROVED"},
        {"author": {"login": "reviewer"}, "commit": {"oid": "h"}, "submittedAt": "2", "state": "CHANGES_REQUESTED"},
        {"author": {"login": "good"}, "commit": {"oid": "h"}, "submittedAt": "2", "state": "APPROVED"},
        {"author": {"login": "good"}, "commit": {"oid": "h"}, "submittedAt": "1", "state": "COMMENTED"},
    ]
    assert g.independent_exact_head_approvers(reviews, "h", "author") == {"good"}


def test_durable_open_findings(tmp_path: Path):
    assert g.durable_open_findings(tmp_path) is None
    target = tmp_path / "registry/work-items/WORK-0002.yaml"
    target.parent.mkdir(parents=True)
    target.write_text("- bad\n", encoding="utf-8")
    assert g.durable_open_findings(tmp_path) is None
    target.write_text("review_plan: bad\n", encoding="utf-8")
    assert g.durable_open_findings(tmp_path) is None
    target.write_text("review_plan:\n  open_findings: [ok, '']\n", encoding="utf-8")
    assert g.durable_open_findings(tmp_path) is None
    target.write_text(yaml.safe_dump({"review_plan": {"open_findings": ["A", "B"]}}), encoding="utf-8")
    assert g.durable_open_findings(tmp_path) == ["A", "B"]


def test_repository_owner_permission(monkeypatch):
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"owner": {"login": "other"}, "full_name": "other/r"})
    assert g.validate_repository_owner_permission("o/r", "t")[0].rule == "REPOSITORY_IDENTITY"

    def bad_permission(url, *args, **kwargs):
        if "/collaborators/" in url:
            return {"permission": "write"}
        return {"owner": {"login": "o"}, "full_name": "o/r"}
    monkeypatch.setattr(g, "request_json", bad_permission)
    assert g.validate_repository_owner_permission("o/r", "t")[0].rule == "REPOSITORY_OWNER_PERMISSION"

    def good(url, *args, **kwargs):
        if "/collaborators/" in url:
            return {"permission": "admin"}
        return {"owner": {"login": "o"}, "full_name": "o/r"}
    monkeypatch.setattr(g, "request_json", good)
    assert g.validate_repository_owner_permission("o/r", "t") == []


def test_validate_draft_and_ready(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"head": {"sha": "h"}, "draft": True, "state": "open", "mergeable": True})
    findings, status = g.validate("o/r", 1, "h", "t", tmp_path)
    assert not findings and status == "DEFERRED_DRAFT"

    info = {"head": {"sha": "other"}, "draft": False, "state": "closed", "mergeable": None, "user": {"login": "author"}}
    monkeypatch.setattr(g, "request_json", lambda *a, **k: info)
    monkeypatch.setattr(g, "validate_repository_owner_permission", lambda *a: [])
    monkeypatch.setattr(g, "fetch_threads", lambda *a: [{"id": "1", "isResolved": False}])
    monkeypatch.setattr(g, "durable_open_findings", lambda *a: [])
    monkeypatch.setattr(g, "fetch_reviews", lambda *a: [])
    findings, status = g.validate("o/r", 1, "h", "t", tmp_path)
    rules = {item.rule for item in findings}
    assert {"HEAD_MISMATCH", "PR_STATE", "MERGEABLE", "UNRESOLVED_THREADS", "DURABLE_FINDING_SET", "INDEPENDENT_EXACT_HEAD_APPROVAL"} <= rules
    assert status == "READY_CHECKED"


def test_validate_happy_exact_head_approval(monkeypatch, tmp_path: Path):
    info = {"head": {"sha": "h"}, "draft": False, "state": "open", "mergeable": True, "user": {"login": "author"}}
    monkeypatch.setattr(g, "request_json", lambda *a, **k: info)
    monkeypatch.setattr(g, "validate_repository_owner_permission", lambda *a: [])
    monkeypatch.setattr(g, "fetch_threads", lambda *a: [])
    monkeypatch.setattr(g, "durable_open_findings", lambda *a: [])
    monkeypatch.setattr(g, "fetch_reviews", lambda *a: [{"author": {"login": "reviewer"}, "commit": {"oid": "h"}, "submittedAt": "1", "state": "APPROVED"}])
    assert g.validate("o/r", 1, "h", "t", tmp_path) == ([], "READY_CHECKED")


def test_main(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert g.main(["--repo", "o/r", "--pr", "1", "--head", "h"]) == 2
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(g, "validate", lambda *a: ([], "READY_CHECKED"))
    out = tmp_path / "o.json"
    assert g.main(["--repo", "o/r", "--pr", "1", "--head", "h", "--root", str(tmp_path), "--json-out", str(out)]) == 0
    monkeypatch.setattr(g, "validate", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    assert g.main(["--repo", "o/r", "--pr", "1", "--head", "h"]) == 2


def test_live_finding_render():
    assert g.LiveFinding("R", "m").render() == "ERROR R: m"
