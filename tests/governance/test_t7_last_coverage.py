from pathlib import Path

import tools.governance.t7_closure as t7
from tools.governance import github_live_gate as live


def test_first_commit_matching_skips_then_matches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "git", lambda *args: "one\ntwo\n")
    monkeypatch.setattr(t7, "text_at", lambda _r, sha, _p: "no" if sha == "one" else "yes")
    monkeypatch.setattr(t7.cg, "commit_parents", lambda *args: [])
    assert t7.first_commit_matching(tmp_path, "h", "p", lambda text: text == "yes") == "two"


def test_policy_blob_delegates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "blob_sha_at", lambda *args: "blob")
    assert t7.policy_blob(tmp_path, "sha") == "blob"


def test_owner_repo_name_fallback(monkeypatch) -> None:
    def request(url, *args, **kwargs):
        if "/collaborators/" in url:
            return {"permission": "admin"}
        return {"owner": {"login": "o"}, "name": "r"}
    monkeypatch.setattr(live, "request_json", request)
    assert live.validate_repository_owner_permission("o/r", "t") == []


def test_live_main_prints_findings_without_json(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(live, "validate", lambda *args: ([live.LiveFinding("X", "bad")], "READY_CHECKED"))
    assert live.main(["--repo", "o/r", "--pr", "1", "--head", "h"]) == 1
    assert "ERROR X" in capsys.readouterr().err
