import json
import urllib.error
from pathlib import Path

import pytest
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


def approval_body(head: str, *, level: str = "L2", fresh: str = "true", separated: str = "true", context: str = "ctx", hats: bool = True) -> str:
    suffix = "\n".join(sorted(g.REQUIRED_L2_HATS)) if hats else "SECURITY"
    return (
        f"{g.L2_APPROVAL_MARKER}\n"
        f"reviewed_head: {head}\n"
        f"independence_level: {level}\n"
        f"fresh_context: {fresh}\n"
        f"authoring_context_separated: {separated}\n"
        f"context_id: {context}\n"
        f"{suffix}\n"
    )


def write_work(root: Path, work_id: str, findings: list[str] | None = None, status: str = "IN_REVIEW") -> str:
    path = f"registry/work-items/{work_id}.yaml"
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump({"id": work_id, "status": status, "review_plan": {"open_findings": findings or []}}), encoding="utf-8")
    return path


def test_request_data_and_json(monkeypatch):
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda req, timeout: Resp({"x": 1}))
    assert g.request_data("https://x.test", "t") == {"x": 1}
    assert g.request_json("https://x.test", "t") == {"x": 1}
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda req, timeout: Resp([1]))
    assert g.request_data("https://x.test", "t") == [1]
    with pytest.raises(RuntimeError):
        g.request_json("https://x.test", "t")


def test_graphql_pagination_and_errors(monkeypatch):
    pages = iter([
        {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"id": "a"}, "bad"], "pageInfo": {"hasNextPage": True, "endCursor": "c"}}}}}},
        {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"id": "b"}], "pageInfo": {"hasNextPage": False}}}}}},
    ])
    monkeypatch.setattr(g, "request_json", lambda *a, **k: next(pages))
    assert [item["id"] for item in g.fetch_threads("o/r", 1, "t")] == ["a", "b"]
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"errors": ["x"]})
    with pytest.raises(RuntimeError): g.fetch_threads("o/r", 1, "t")
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {}})
    with pytest.raises(RuntimeError): g.fetch_threads("o/r", 1, "t")
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": []}}}})
    with pytest.raises(RuntimeError): g.fetch_threads("o/r", 1, "t")
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": "bad", "pageInfo": {}}}}}})
    with pytest.raises(RuntimeError): g.fetch_threads("o/r", 1, "t")
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": True}}}}}})
    with pytest.raises(RuntimeError): g.fetch_threads("o/r", 1, "t")


def test_fetch_reviews_wrapper(monkeypatch):
    monkeypatch.setattr(g, "_paginate_graphql", lambda *a: [{"id": "r"}])
    assert g.fetch_reviews("o/r", 1, "t") == [{"id": "r"}]


def test_fetch_pr_files_pages_and_malformed(monkeypatch):
    pages = iter([[{"filename": "a"}] * 100, [{"filename": "b"}, {"nope": "x"}]])
    monkeypatch.setattr(g, "request_data", lambda *_a, **_k: next(pages))
    files = g.fetch_pr_files("o/r", 1, "t")
    assert files.count("a") == 100 and files[-1] == "b"
    monkeypatch.setattr(g, "request_data", lambda *_a, **_k: {"bad": True})
    with pytest.raises(RuntimeError, match="malformed pull-request file list"):
        g.fetch_pr_files("o/r", 1, "t")
    monkeypatch.setattr(g, "request_data", lambda *_a, **_k: [{"filename": "a"}] * 100)
    monkeypatch.setattr(g, "MAX_PAGES", 1)
    with pytest.raises(RuntimeError, match="pagination exceeded"):
        g.fetch_pr_files("o/r", 1, "t")


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


def test_l2_approval_body_contract():
    head = "a" * 40
    assert g.l2_approval_body_valid(approval_body(head), head)
    assert g.l2_approval_body_valid(approval_body(head, level="L3"), head)
    assert not g.l2_approval_body_valid("reviewed_head: x", head)
    assert not g.l2_approval_body_valid(approval_body("b" * 40), head)
    assert not g.l2_approval_body_valid(approval_body(head, level="L1"), head)
    assert not g.l2_approval_body_valid(approval_body(head, fresh="false"), head)
    assert not g.l2_approval_body_valid(approval_body(head, separated="false"), head)
    assert not g.l2_approval_body_valid(approval_body(head, context=""), head)
    assert not g.l2_approval_body_valid(approval_body(head, hats=False), head)


def test_reviewer_permission_fail_closed(monkeypatch):
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"permission": "write"})
    assert g.reviewer_permission("o/r", "reviewer", "t") == "write"
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"permission": 7})
    assert g.reviewer_permission("o/r", "reviewer", "t") is None
    def forbidden(*args, **kwargs): raise urllib.error.HTTPError("https://x", 404, "missing", {}, None)
    monkeypatch.setattr(g, "request_json", forbidden)
    assert g.reviewer_permission("o/r", "reviewer", "t") is None
    def broken(*args, **kwargs): raise urllib.error.HTTPError("https://x", 500, "broken", {}, None)
    monkeypatch.setattr(g, "request_json", broken)
    with pytest.raises(urllib.error.HTTPError): g.reviewer_permission("o/r", "reviewer", "t")


def test_trusted_exact_head_approvers_require_permission_and_l2_body(monkeypatch):
    head = "h"
    reviews = [
        {"id": "r1", "author": {"login": "outside"}, "commit": {"oid": head}, "submittedAt": "1", "state": "APPROVED", "body": approval_body(head)},
        {"id": "r2", "author": {"login": "trusted"}, "commit": {"oid": head}, "submittedAt": "1", "state": "APPROVED", "body": approval_body(head)},
        {"id": "r3", "author": {"login": "shallow"}, "commit": {"oid": head}, "submittedAt": "1", "state": "APPROVED", "body": "looks good"},
        {"id": "r4", "author": {"login": "commenter"}, "commit": {"oid": head}, "submittedAt": "1", "state": "COMMENTED", "body": approval_body(head)},
    ]
    monkeypatch.setattr(g, "reviewer_permission", lambda _repo, actor, _token: {"outside": "read", "trusted": "write", "shallow": "write", "commenter": "write"}[actor])
    assert g.trusted_exact_head_approvers("o/r", reviews, head, "author", "t") == {"trusted"}


def test_dynamic_work_resolution_and_durable_thread_ids(tmp_path: Path):
    work3 = write_work(tmp_path, "WORK-0003", ["PRRT_A / P1: one", "PRRT_B / P2: two"])
    assert g.resolve_closure_work(tmp_path, [work3, "tools/x.py"]) == (work3, "WORK-0003")
    assert g.durable_finding_ids(g.durable_open_findings(tmp_path, work3)) == {"PRRT_A", "PRRT_B"}
    write_work(tmp_path, "WORK-0004", [])
    assert g.resolve_closure_work(tmp_path, [work3, "registry/work-items/WORK-0004.yaml"]) is None
    assert g.resolve_closure_work(tmp_path, ["tools/x.py"]) is None
    assert g.durable_finding_ids(["REVIEW-1/F-1"]) is None
    assert g.durable_finding_ids(["PRRT_A", "PRRT_A duplicate"]) is None


def test_work_loader_rejects_bad_records(tmp_path: Path):
    missing = "registry/work-items/WORK-0009.yaml"
    assert g._load_work(tmp_path, missing) is None
    target = tmp_path / missing
    target.parent.mkdir(parents=True)
    target.write_text("- bad\n", encoding="utf-8")
    assert g._load_work(tmp_path, missing) is None
    target.write_text("id: WRONG\nstatus: IN_REVIEW\n", encoding="utf-8")
    assert g.resolve_closure_work(tmp_path, [missing]) is None
    target.write_text("id: WORK-0009\nstatus: PLANNED\n", encoding="utf-8")
    assert g.resolve_closure_work(tmp_path, [missing]) is None


def test_durable_open_findings_validation(tmp_path: Path):
    path = write_work(tmp_path, "WORK-0008")
    target = tmp_path / path
    target.write_text("review_plan: bad\n", encoding="utf-8")
    assert g.durable_open_findings(tmp_path, path) is None
    target.write_text("review_plan:\n  open_findings: [ok, '']\n", encoding="utf-8")
    assert g.durable_open_findings(tmp_path, path) is None


def test_repository_owner_permission(monkeypatch):
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"owner": {"login": "other"}, "full_name": "other/r"})
    assert g.validate_repository_owner_permission("o/r", "t")[0].rule == "REPOSITORY_IDENTITY"
    def bad_permission(url, *args, **kwargs):
        if "/collaborators/" in url: return {"permission": "write"}
        return {"owner": {"login": "o"}, "full_name": "o/r"}
    monkeypatch.setattr(g, "request_json", bad_permission)
    assert g.validate_repository_owner_permission("o/r", "t")[0].rule == "REPOSITORY_OWNER_PERMISSION"
    def good(url, *args, **kwargs):
        if "/collaborators/" in url: return {"permission": "admin"}
        return {"owner": {"login": "o"}, "full_name": "o/r"}
    monkeypatch.setattr(g, "request_json", good)
    assert g.validate_repository_owner_permission("o/r", "t") == []


def setup_live(monkeypatch, tmp_path: Path, *, head="h", unresolved=None, durable=None, work_id="WORK-0003"):
    info = {"head": {"sha": head}, "draft": False, "state": "open", "mergeable": True, "user": {"login": "author"}}
    work_path = write_work(tmp_path, work_id, durable or [])
    monkeypatch.setattr(g, "request_json", lambda *a, **k: info)
    monkeypatch.setattr(g, "validate_repository_owner_permission", lambda *a: [])
    monkeypatch.setattr(g, "fetch_pr_files", lambda *a: [work_path, "tools/governance/x.py"])
    monkeypatch.setattr(g, "fetch_threads", lambda *a: unresolved or [])
    monkeypatch.setattr(g, "fetch_reviews", lambda *a: [])
    return info, work_path


def test_validate_draft_and_failure_paths(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(g, "request_json", lambda *a, **k: {"head": {"sha": "h"}, "draft": True, "state": "open", "mergeable": True})
    findings, status = g.validate("o/r", 1, "h", "t", tmp_path)
    assert not findings and status == "DEFERRED_DRAFT"

    info, _ = setup_live(monkeypatch, tmp_path, head="other", unresolved=[{"id": "PRRT_1", "isResolved": False}], durable=["PRRT_OTHER / stale"])
    info.update({"state": "closed", "mergeable": None})
    findings, status = g.validate("o/r", 1, "h", "t", tmp_path)
    rules = {item.rule for item in findings}
    assert {"HEAD_MISMATCH", "PR_STATE", "MERGEABLE", "UNRESOLVED_THREADS", "DURABLE_FINDING_SET", "INDEPENDENT_EXACT_HEAD_APPROVAL"} <= rules
    assert status == "READY_CHECKED"


def test_validate_fails_closed_without_unique_changed_work(monkeypatch, tmp_path: Path):
    info = {"head": {"sha": "h"}, "draft": False, "state": "open", "mergeable": True, "user": {"login": "author"}}
    monkeypatch.setattr(g, "request_json", lambda *a, **k: info)
    monkeypatch.setattr(g, "validate_repository_owner_permission", lambda *a: [])
    monkeypatch.setattr(g, "fetch_pr_files", lambda *a: ["tools/governance/x.py"])
    monkeypatch.setattr(g, "fetch_threads", lambda *a: [])
    monkeypatch.setattr(g, "fetch_reviews", lambda *a: [])
    findings, _ = g.validate("o/r", 1, "h", "t", tmp_path)
    assert "ACTIVE_WORK_RESOLUTION" in {item.rule for item in findings}


def test_validate_happy_exact_head_approval_on_work0003(monkeypatch, tmp_path: Path):
    head = "h"
    info, work_path = setup_live(monkeypatch, tmp_path, head=head)
    def request(url, *args, **kwargs):
        if "/collaborators/reviewer/permission" in url: return {"permission": "write"}
        return info
    monkeypatch.setattr(g, "request_json", request)
    monkeypatch.setattr(g, "fetch_pr_files", lambda *a: [work_path])
    monkeypatch.setattr(g, "fetch_reviews", lambda *a: [{"id": "r", "author": {"login": "reviewer"}, "commit": {"oid": head}, "submittedAt": "1", "state": "APPROVED", "body": approval_body(head)}])
    assert g.validate("o/r", 1, head, "t", tmp_path) == ([], "READY_CHECKED")


def test_validate_identity_matched_open_threads(monkeypatch, tmp_path: Path):
    setup_live(monkeypatch, tmp_path, unresolved=[{"id": "PRRT_A", "isResolved": False}], durable=["PRRT_A / P1: x"])
    findings, _ = g.validate("o/r", 1, "h", "t", tmp_path)
    assert "DURABLE_FINDING_SET" not in {item.rule for item in findings}
    assert "UNRESOLVED_THREADS" in {item.rule for item in findings}


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
