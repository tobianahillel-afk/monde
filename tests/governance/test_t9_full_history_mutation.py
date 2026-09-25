from pathlib import Path
import subprocess
import yaml

import tools.governance.t9_closure as t9


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def write_policy(root: Path, version: int) -> None:
    path = root / t9.POLICY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"version": version}), encoding="utf-8")


def commit(root: Path, message: str) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_full_history_finds_change_revert_on_merged_side_branch(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    write_policy(root, 1)
    evidence = commit(root, "policy v1")

    git(root, "checkout", "-b", "side")
    write_policy(root, 2)
    commit(root, "side policy v2")
    write_policy(root, 1)
    commit(root, "side reverts policy to v1")

    git(root, "checkout", "master")
    (root / "main.txt").write_text("main\n", encoding="utf-8")
    commit(root, "main unrelated")
    git(root, "merge", "--no-ff", "side", "-m", "merge reverted side history")
    acceptance = git(root, "rev-parse", "HEAD")

    # Endpoint bytes are equal. Only full-history traversal exposes that the
    # evidence policy was changed and reverted on a merged side branch.
    assert t9.t7.policy_blob(root, evidence) == t9.t7.policy_blob(root, acceptance)
    simplified = git(root, "rev-list", "--topo-order", f"{evidence}..{acceptance}", "--", t9.POLICY_PATH)
    full = git(root, "rev-list", "--full-history", "--topo-order", f"{evidence}..{acceptance}", "--", t9.POLICY_PATH)
    assert simplified == ""
    assert full != ""
    assert not t9.policy_stable_full_history(root, evidence, acceptance)
