"""Default-branch-only executable-source attestor for MONDE governance.

Never checkout, import or execute pull-request code from this process.
Only compare Git tree metadata against an independently approved manifest.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib import request

SHA = re.compile(r"^[a-f0-9]{40}$")
EXECUTABLE_SUFFIXES = (
    ".py", ".pyi", ".pth", ".so", ".dylib", ".dll", ".sh", ".bash",
    ".ps1", ".bat", ".cmd", ".js", ".mjs", ".cjs", ".ts", ".rb",
    ".pl", ".whl", ".jar", ".toml", ".ini", ".cfg",
)
TRUST_ROOT_PATHS = (
    "tools/trusted_gate/",
    "tests/trusted_gate/",
    "registry/trust/",
)
TRUST_ROOT_WORKFLOW = ".github/workflows/monde-trusted-attestation.yml"


class TrustFailure(RuntimeError):
    """Fail-closed when GitHub authority or any executable file is ambiguous."""


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def trust_root_path(path: str) -> bool:
    return path == TRUST_ROOT_WORKFLOW or any(
        path.startswith(prefix) for prefix in TRUST_ROOT_PATHS
    )


def protected_path(path: str) -> bool:
    if trust_root_path(path):
        return False
    return (
        path.startswith((".github/workflows/", ".github/actions/", "requirements/", "tools/governance/"))
        or path.endswith(EXECUTABLE_SUFFIXES)
        or path.rsplit("/", 1)[-1] in {"Dockerfile", "Makefile", "Pipfile", "Gemfile"}
    )


def index_tree(payload: Any) -> dict[str, tuple[str, str]]:
    if not isinstance(payload, dict) or payload.get("truncated") is not False:
        raise TrustFailure("Git tree is absent, truncated or ambiguous")
    nodes = payload.get("tree")
    if not isinstance(nodes, list):
        raise TrustFailure("Git tree nodes are malformed")
    output: dict[str, tuple[str, str]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise TrustFailure("Git tree node is malformed")
        path = node.get("path")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
            raise TrustFailure("Git tree path is unsafe")
        if node.get("type") != "blob":
            if protected_path(path) or trust_root_path(path):
                raise TrustFailure(f"Protected path is not a blob: {path}")
            continue
        oid, mode = node.get("sha"), node.get("mode")
        if not valid_sha(oid) or mode not in {"100644", "100755", "120000"}:
            raise TrustFailure(f"Invalid Git blob identity/mode at {path}")
        if path in output:
            raise TrustFailure(f"Duplicate Git path: {path}")
        output[path] = (oid, mode)
    return output


def validate_manifest(payload: Any) -> dict[str, tuple[str, str]]:
    if not isinstance(payload, dict) or set(payload) != {"version", "origin_candidate_sha", "files"}:
        raise TrustFailure("Trusted manifest shape is invalid")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise TrustFailure("Trusted manifest version is invalid")
    if not valid_sha(payload["origin_candidate_sha"]):
        raise TrustFailure("Trusted manifest origin is invalid")
    rows = payload["files"]
    if not isinstance(rows, dict) or not rows:
        raise TrustFailure("Trusted manifest has no files")
    files: dict[str, tuple[str, str]] = {}
    for path, item in rows.items():
        if not isinstance(path, str) or not protected_path(path) or trust_root_path(path):
            raise TrustFailure(f"Unprotected manifest path: {path}")
        if not isinstance(item, dict) or set(item) != {"sha", "mode"}:
            raise TrustFailure(f"Invalid manifest entry: {path}")
        if not valid_sha(item["sha"]) or item["mode"] not in {"100644", "100755"}:
            raise TrustFailure(f"Invalid manifest blob/mode: {path}")
        files[path] = (item["sha"], item["mode"])
    for mandatory in (
        ".github/workflows/governance.yml",
        ".github/workflows/_governance-core.yml",
        "requirements/governance-ci.txt",
        "tools/governance/validate_repo.py",
        "tools/governance/github_live_gate.py",
    ):
        if mandatory not in files:
            raise TrustFailure(f"Missing mandatory trust-reviewed path: {mandatory}")
    return files


def verify_trees(
    approved: dict[str, tuple[str, str]],
    base: dict[str, tuple[str, str]],
    candidate: dict[str, tuple[str, str]],
) -> None:
    actual = {p: identity for p, identity in candidate.items() if protected_path(p)}
    if any(mode == "120000" for _sha, mode in actual.values()):
        raise TrustFailure("Executable source contains a symlink")
    if actual != approved:
        missing = sorted(set(approved) - set(actual))
        added = sorted(set(actual) - set(approved))
        changed = sorted(p for p in set(actual) & set(approved) if actual[p] != approved[p])
        raise TrustFailure(
            f"Candidate executable source differs from default-branch-approved manifest: "
            f"missing={missing[:12]}, added={added[:12]}, changed={changed[:12]}"
        )

    roots = {p: identity for p, identity in base.items() if trust_root_path(p)}
    if TRUST_ROOT_WORKFLOW not in roots or "tools/trusted_gate/attest.py" not in roots or "registry/trust/approved-governance-v1.json" not in roots:
        raise TrustFailure("Default-branch trust root is incomplete")
    actual_roots = {p: identity for p, identity in candidate.items() if trust_root_path(p)}
    if actual_roots != roots:
        raise TrustFailure("Candidate modified, removed or added trusted-root executables/metadata")


def fetch_json(url: str, token: str) -> Any:
    if not token:
        raise TrustFailure("GitHub token is missing")
    req = request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with request.urlopen(req, timeout=20) as response:
        data = response.read(16_000_001)
        if len(data) > 16_000_000:
            raise TrustFailure("GitHub API response exceeds bounded proof size")
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TrustFailure("GitHub API returned malformed JSON") from exc


def attest(
    repo: str, pr_number: int, head: str, base_sha: str,
    manifest: Any, token: str,
) -> int:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise TrustFailure("Repository selector invalid")
    if type(pr_number) is not int or pr_number <= 0 or not valid_sha(head) or not valid_sha(base_sha):
        raise TrustFailure("Pull request revision selector invalid")

    approved = validate_manifest(manifest)
    url = f"https://api.github.com/repos/{repo}"
    snapshot = fetch_json(f"{url}/pulls/{pr_number}", token)
    try:
        actual_head = snapshot["head"]["sha"]
        head_repo = snapshot["head"]["repo"]["full_name"]
        actual_base = snapshot["base"]["sha"]
        base_repo = snapshot["base"]["repo"]["full_name"]
        state = snapshot["state"]
        number = snapshot["number"]
    except (KeyError, TypeError) as exc:
        raise TrustFailure("Pull request authority snapshot is malformed") from exc
    if (
        type(number) is not int or number != pr_number
        or head_repo != repo or base_repo != repo or state != "open"
        or actual_head != head or actual_base != base_sha
    ):
        raise TrustFailure("Pull request authority changed or belongs to another repository")

    base = index_tree(fetch_json(f"{url}/git/trees/{base_sha}?recursive=1", token))
    candidate = index_tree(fetch_json(f"{url}/git/trees/{head}?recursive=1", token))
    verify_trees(approved, base, candidate)
    # Detect a concurrent PR head/base move after the multi-call proof.
    after = fetch_json(f"{url}/pulls/{pr_number}", token)
    if not isinstance(after, dict) or after.get("head", {}).get("sha") != head or after.get("base", {}).get("sha") != base_sha or after.get("state") != "open":
        raise TrustFailure("Pull request authority drifted after executable-source proof")
    return len(approved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = json.loads(args.manifest.read_text(encoding="utf-8"))
        count = attest(
            os.environ.get("GITHUB_REPOSITORY", ""),
            int(os.environ.get("MONDE_TRUST_PR_NUMBER", "0")),
            os.environ.get("MONDE_TRUST_PR_HEAD", ""),
            os.environ.get("MONDE_TRUST_PR_BASE", ""),
            raw,
            os.environ.get("GITHUB_TOKEN", ""),
        )
    except (OSError, ValueError, TrustFailure) as exc:
        print(f"MONDE trusted attestation FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"MONDE trusted attestation PASS: {count} executable paths matched approved base manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
