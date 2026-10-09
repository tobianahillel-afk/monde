"""Default-branch-owned attestation of WORK-0002 executable source identities.

This file MUST run only from a trusted base-branch workflow. It never imports,
checks out, installs dependencies from, or executes pull-request code.
The manifest is a PROPOSED trust anchor until its own PR is independently
reviewed and merged into the default branch.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SHA = re.compile(r"[0-9a-f]{40}\Z")
REQUIRED = frozenset({
    "requirements/governance-ci.txt",
    "tools/governance/validate_repo.py",
    ".github/workflows/governance.yml",
    ".github/workflows/_governance-core.yml",
})
CONFIG_FILES = frozenset({
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini",
    ".coveragerc", "pytest.ini",
})
SUFFIXES = (".py", ".pyc", ".pth", ".pyd", ".so")
MAX_RESPONSE_BYTES = 4_000_000


class AttestationError(RuntimeError):
    pass


def in_scope(path: str, mode: str) -> bool:
    return (
        path.endswith(SUFFIXES)
        or path.startswith(".github/workflows/")
        or path.startswith("requirements/")
        or path in CONFIG_FILES
        or mode == "100755"
    )


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def validate_manifest(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise AttestationError("unsupported trusted-source manifest version")
    if type(value.get("target_pr")) is not int or value["target_pr"] != 2:
        raise AttestationError("trusted-source manifest target PR mismatch")
    sources = value.get("source_files")
    if not isinstance(sources, dict) or not sources:
        raise AttestationError("trusted-source manifest has no source files")
    if not REQUIRED.issubset(sources):
        raise AttestationError("trusted-source manifest omits a mandatory source")
    for path, expected in sources.items():
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or ".." in Path(path).parts
            or not isinstance(expected, dict)
            or set(expected) != {"sha", "mode"}
            or not _sha(expected["sha"])
            or expected["mode"] not in ("100644", "100755")
            or not in_scope(path, expected["mode"])
        ):
            raise AttestationError(f"malformed trusted-source entry: {path!r}")
    return sources


def _base_owned(path: str) -> bool:
    return path.startswith(".github/trusted/") or path == ".github/workflows/monde-trusted-source.yml"


def verify_tree(
    manifest: dict[str, Any], candidate_tree: Any, base_tree: Any | None = None
) -> int:
    expected = dict(validate_manifest(manifest))
    if base_tree is not None:
        if (
            not isinstance(base_tree, dict)
            or base_tree.get("truncated") is not False
            or not isinstance(base_tree.get("tree"), list)
        ):
            raise AttestationError("default-branch trust-root tree is incomplete")
        for item in base_tree["tree"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise AttestationError("default-branch trust-root node is malformed")
            path = item["path"]
            if not _base_owned(path):
                continue
            if (
                item.get("type") != "blob"
                or item.get("mode") not in ("100644", "100755")
                or not _sha(item.get("sha"))
                or path in expected
            ):
                raise AttestationError(f"invalid default-branch trust-root source: {path}")
            expected[path] = {"sha": item["sha"], "mode": item["mode"]}
        if not (
            ".github/trusted/trusted_source_attestor.py" in expected
            and ".github/trusted/approved_sources.json" in expected
            and ".github/workflows/monde-trusted-source.yml" in expected
        ):
            raise AttestationError("missing default-branch trust-root files")
    if (
        not isinstance(candidate_tree, dict)
        or candidate_tree.get("truncated") is not False
        or not isinstance(candidate_tree.get("tree"), list)
    ):
        raise AttestationError("candidate tree missing, malformed or truncated")
    actual: dict[str, dict[str, str]] = {}
    for node in candidate_tree["tree"]:
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            raise AttestationError("malformed candidate tree node")
        path = node["path"]
        mode = node.get("mode")
        if not isinstance(mode, str):
            raise AttestationError(f"missing Git mode for {path}")
        if not (in_scope(path, mode) or _base_owned(path)):
            continue
        if path in actual:
            raise AttestationError(f"duplicate candidate source path: {path}")
        if node.get("type") != "blob" or mode not in ("100644", "100755"):
            raise AttestationError(f"unsafe source mode/type: {path}")
        sha = node.get("sha")
        if not _sha(sha):
            raise AttestationError(f"malformed source SHA: {path}")
        actual[path] = {"sha": sha, "mode": mode}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    drift = sorted(path for path in set(expected) & set(actual) if expected[path] != actual[path])
    if missing or unexpected or drift:
        raise AttestationError(
            f"unapproved governance source change: missing={missing[:8]}, "
            f"unexpected={unexpected[:8]}, drift={drift[:8]}"
        )
    return len(actual)


def _get_json(repo: str, route: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/{route}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.HTTPError) as exc:
        raise AttestationError("GitHub trust-source request failed") from exc
    if len(data) > MAX_RESPONSE_BYTES:
        raise AttestationError("GitHub trust-source response exceeds size bound")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError("malformed GitHub trust-source response") from exc
    if not isinstance(value, dict):
        raise AttestationError("non-object GitHub trust-source response")
    return value


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("MONDE_ATTEST_HEAD", "")
    pr = os.environ.get("MONDE_ATTEST_PR", "")
    base_sha = os.environ.get("MONDE_ATTEST_BASE", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if (
        repo != "tobianahillel-afk/monde"
        or not _sha(sha)
        or pr != "2"
        or not _sha(base_sha)
        or not token
    ):
        raise AttestationError("invalid trusted-source invocation identity")
    manifest = json.loads(
        (Path(__file__).resolve().parent / "approved_sources.json").read_text(encoding="utf-8")
    )
    commit = _get_json(repo, f"git/commits/{sha}", token)
    if commit.get("sha") != sha or not isinstance(commit.get("tree"), dict):
        raise AttestationError("candidate commit identity mismatch")
    tree_sha = commit["tree"].get("sha")
    if not _sha(tree_sha):
        raise AttestationError("candidate commit lacks exact tree SHA")
    tree = _get_json(repo, f"git/trees/{tree_sha}?recursive=1", token)
    if tree.get("sha") != tree_sha:
        raise AttestationError("candidate tree identity mismatch")
    base_commit = _get_json(repo, f"git/commits/{base_sha}", token)
    if base_commit.get("sha") != base_sha or not isinstance(base_commit.get("tree"), dict):
        raise AttestationError("trusted default-branch commit identity mismatch")
    base_tree_sha = base_commit["tree"].get("sha")
    if not _sha(base_tree_sha):
        raise AttestationError("trusted default-branch commit lacks tree SHA")
    base_tree = _get_json(repo, f"git/trees/{base_tree_sha}?recursive=1", token)
    if base_tree.get("sha") != base_tree_sha:
        raise AttestationError("trusted default-branch tree identity mismatch")
    count = verify_tree(manifest, tree, base_tree)
    print(f"MONDE trusted-source attestation PASS: PR #{pr}, {count} approved Git objects, head={sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttestationError, OSError, ValueError) as exc:
        print(f"MONDE trusted-source attestation FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
