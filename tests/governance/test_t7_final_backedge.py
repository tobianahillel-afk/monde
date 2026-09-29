from pathlib import Path

import tools.governance.t7_closure as t7


def test_first_commit_matching_continues_past_already_present_parent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(t7.cg, "git", lambda *args: "one\ntwo\n")

    def text_at(_root: Path, sha: str, _path: str) -> str | None:
        return {
            "one": "yes",
            "parent": "yes",
            "two": "yes",
        }.get(sha)

    monkeypatch.setattr(t7, "text_at", text_at)
    monkeypatch.setattr(
        t7.cg,
        "commit_parents",
        lambda _root, sha: ["parent"] if sha == "one" else [],
    )

    assert t7.first_commit_matching(tmp_path, "head", "path", lambda text: text == "yes") == "two"
