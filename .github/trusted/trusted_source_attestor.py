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
POLICY_FILES = frozenset(['registry/acceptance-authority.yaml','registry/content-identity.yaml','registry/integration-provenance.yaml','registry/status-machines.yaml'])
SCHEMA_FILES = frozenset(['schemas/registry/assumptions.schema.json','schemas/registry/capabilities.schema.json','schemas/registry/experiments.schema.json','schemas/registry/requirements.schema.json','schemas/registry/reviews.schema.json','schemas/registry/risks.schema.json','schemas/registry/tests.schema.json','schemas/registry/work-items.schema.json'])
REQUIRED = frozenset({
    "requirements/governance-ci.txt",
    "tools/governance/validate_repo.py",
    ".github/workflows/governance.yml",
    ".github/workflows/_governance-core.yml",
}) | POLICY_FILES | SCHEMA_FILES
CONFIG_FILES = frozenset({
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini",
    ".coveragerc", "pytest.ini", ".python-version",
    "Makefile", "GNUmakefile", "Pipfile", "Pipfile.lock",
    "poetry.lock", "uv.lock", "package.json", "package-lock.json",
    ".gitmodules", ".gitattributes", ".lfsconfig",
})
# Local actions, shell scripts, plugin configs and interpreter extensions can
# execute even without a Python suffix or Git executable bit. Treat every
# Git blob under code/CI paths as an authority-bearing dependency.
# Also reject symlinks/gitlinks anywhere in the tree: they can redirect reads
# or introduce nested checkouts outside a previously approved source set.
SOURCE_PREFIXES = (".github/", "requirements/", "scripts/", "tools/", "tests/", "schemas/")
SUFFIXES = (
    ".py", ".pyc", ".pyo", ".pth", ".pyd", ".so", ".dylib", ".dll",
    ".node", ".js", ".mjs", ".cjs", ".ts", ".sh", ".ps1", ".bat",
    ".cmd", ".rb", ".go", ".rs", ".wasm", ".jar", ".whl", ".egg",
    ".zip", ".class",
)
MAX_RESPONSE_BYTES = 4_000_000


class AttestationError(RuntimeError):
    pass


def in_scope(path: str, mode: str) -> bool:
    return (
        path.endswith(SUFFIXES)
        or path.startswith(SOURCE_PREFIXES)
        or path in CONFIG_FILES
        or path in POLICY_FILES
        or mode in ("100755", "120000", "160000")
    )


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _unique_json_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous trusted manifest maps rather than silently keeping the last key."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AttestationError(f"duplicate trusted-manifest JSON key: {key}")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object_pairs)


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
            or any(part in ("", ".", "..") for part in path.split("/"))
            or "\\" in path
            or "\x00" in path
            or not isinstance(expected, dict)
            or set(expected) != {"sha", "mode"}
            or not _sha(expected["sha"])
            or expected["mode"] not in ("100644", "100755")
            or not in_scope(path, expected["mode"])
            or _base_owned(path)
        ):
            raise AttestationError(f"malformed trusted-source entry: {path!r}")
    return sources


def _base_owned(path: str) -> bool:
    return path.startswith(".github/trusted/") or path == ".github/workflows/monde-trusted-source.yml"


def verify_tree(
    manifest: dict[str, Any],
    candidate_tree: Any,
    base_tree: Any | None = None,
    *,
    require_base_owned: bool = False,
) -> int:
    expected = dict(validate_manifest(manifest))
    # These trust-root files execute solely from the default-branch checkout.
    # A pre-integration PR is not required to carry files introduced by the
    # independently reviewed base predecessor. If present in the PR tree,
    # however, they must be byte-identical to the base-owned versions.
    base_owned: dict[str, dict[str, str]] = {}
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
            # GitHub recursive trees include directory entries. They are
            # structural containers, not executable Git blobs or trust roots.
            # A different type/mode pairing is NOT exempt.
            if item.get("type") == "tree" and item.get("mode") == "040000":
                continue
            if not _base_owned(path):
                continue
            if (
                item.get("type") != "blob"
                or item.get("mode") not in ("100644", "100755")
                or not _sha(item.get("sha"))
                or path in expected
                or path in base_owned
            ):
                raise AttestationError(f"invalid default-branch trust-root source: {path}")
            base_owned[path] = {"sha": item["sha"], "mode": item["mode"]}
        if not (
            ".github/trusted/trusted_source_attestor.py" in base_owned
            and ".github/trusted/approved_sources.json" in base_owned
            and ".github/workflows/monde-trusted-source.yml" in base_owned
        ):
            raise AttestationError("missing default-branch trust-root files")
    if (
        not isinstance(candidate_tree, dict)
        or candidate_tree.get("truncated") is not False
        or not isinstance(candidate_tree.get("tree"), list)
    ):
        raise AttestationError("candidate tree missing, malformed or truncated")
    actual: dict[str, dict[str, str]] = {}
    seen_base_owned: set[str] = set()
    for node in candidate_tree["tree"]:
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            raise AttestationError("malformed candidate tree node")
        path = node["path"]
        mode = node.get("mode")
        if not isinstance(mode, str):
            raise AttestationError(f"missing Git mode for {path}")
        # Recursive Git Trees carry directories as tree/040000 entries.
        # Only this exact structural pairing can be skipped; symlinks and
        # gitlinks remain unsafe everywhere, even outside source prefixes.
        if node.get("type") == "tree" and mode == "040000":
            continue
        if not (in_scope(path, mode) or _base_owned(path)):
            continue
        if path in actual:
            raise AttestationError(f"duplicate candidate source path: {path}")
        if node.get("type") != "blob" or mode not in ("100644", "100755"):
            raise AttestationError(f"unsafe source mode/type: {path}")
        sha = node.get("sha")
        if not _sha(sha):
            raise AttestationError(f"malformed source SHA: {path}")
        if _base_owned(path):
            # The PR is free to omit base-owned files (as WORK-0002 does
            # before it integrates this predecessor), but can never replace
            # them, introduce new trust-root paths or duplicate an entry.
            if path in seen_base_owned:
                raise AttestationError(f"duplicate candidate trust-root path: {path}")
            seen_base_owned.add(path)
            if base_owned.get(path) != {"sha": sha, "mode": mode}:
                raise AttestationError(f"unapproved default-branch trust-root source: {path}")
            continue
        actual[path] = {"sha": sha, "mode": mode}
    if require_base_owned:
        # Checking only the PR tree is not enough: pre-integration absence
        # is legitimate, but the actual GitHub test-merge result MUST retain
        # every approved trust-root file from the base branch.
        if not base_owned or seen_base_owned != set(base_owned):
            raise AttestationError("merged result removed a default-branch trust-root source")
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


STATUS_CONTEXT = "MONDE / Trusted Source Attestation"


def _publish_status(
    repo: str, sha: str, token: str, state: str, description: str,
    *, base_sha: str | None = None,
) -> None:
    if not _sha(sha) or state not in {"pending", "success", "failure"}:
        raise AttestationError("invalid exact trusted-source status identity")
    if base_sha is not None and not _sha(base_sha):
        raise AttestationError("invalid trusted-source base identity")
    # A candidate-commit status alone is not merge authority: its description
    # carries the exact validated base SHA, which the downstream live gate
    # MUST compare against current main before accepting any success.
    bound_description = (
        f"base={base_sha};{description}" if base_sha is not None else description
    )
    payload = json.dumps({
        "state": state,
        "context": STATUS_CONTEXT,
        "description": bound_description[:140],
    }, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/statuses/{sha}",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.HTTPError) as exc:
        raise AttestationError("trusted candidate-status publication failed") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise AttestationError("trusted candidate-status response exceeds size bound")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttestationError("malformed trusted candidate-status response") from exc
    if (
        not isinstance(result, dict)
        or result.get("state") != state
        or result.get("context") != STATUS_CONTEXT
        or result.get("sha") != sha
    ):
        raise AttestationError("trusted candidate-status acknowledgement is not exact")


def _exact_pr_snapshot(repo: str, token: str, sha: str, base_sha: str) -> dict[str, Any]:
    pr = _get_json(repo, "pulls/2", token)
    if (
        type(pr.get("number")) is not int
        or pr["number"] != 2
        or pr.get("state") != "open"
        or pr.get("draft") is not False
        or not isinstance(pr.get("head"), dict)
        or pr["head"].get("sha") != sha
        or not isinstance(pr.get("base"), dict)
        or pr["base"].get("sha") != base_sha
        or pr["base"].get("ref") != "main"
        or pr.get("mergeable") is not True
        or not _sha(pr.get("merge_commit_sha"))
    ):
        raise AttestationError("current PR #2 authority does not match attested head/base")
    return pr


def _verify_approved_merge(repo: str, token: str, sha: str, base_sha: str) -> int:
    # The current PR snapshot binds the synthetic merge SHA to the exact
    # candidate/base; checking that merge tree prevents deleting main's
    # attestor during or after the candidate integrates the trust root.
    pr = _exact_pr_snapshot(repo, token, sha, base_sha)
    manifest = load_manifest(Path(__file__).resolve().parent / "approved_sources.json")
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

    merge_sha = pr["merge_commit_sha"]
    merge_commit = _get_json(repo, f"git/commits/{merge_sha}", token)
    parents = merge_commit.get("parents")
    if (
        merge_commit.get("sha") != merge_sha
        or not isinstance(parents, list)
        or len(parents) != 2
        or not all(isinstance(p, dict) for p in parents)
        or [p.get("sha") for p in parents] != [base_sha, sha]
        or not isinstance(merge_commit.get("tree"), dict)
        or not _sha(merge_commit["tree"].get("sha"))
    ):
        raise AttestationError("GitHub candidate merge is not bound to exact base/head parents")
    merge_tree_sha = merge_commit["tree"]["sha"]
    merge_tree = _get_json(repo, f"git/trees/{merge_tree_sha}?recursive=1", token)
    if merge_tree.get("sha") != merge_tree_sha:
        raise AttestationError("merged result tree identity mismatch")
    merged_count = verify_tree(manifest, merge_tree, base_tree, require_base_owned=True)
    if merged_count != count:
        raise AttestationError("merged result source count differs from candidate")

    current_base = _get_json(repo, "branches/main", token)
    if (
        not isinstance(current_base.get("commit"), dict)
        or current_base["commit"].get("sha") != base_sha
    ):
        raise AttestationError("trusted default branch advanced during attestation")
    if _exact_pr_snapshot(repo, token, sha, base_sha)["merge_commit_sha"] != merge_sha:
        raise AttestationError("GitHub candidate merge authority drifted during attestation")
    return count


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("MONDE_ATTEST_HEAD", "")
    pr = os.environ.get("MONDE_ATTEST_PR", "")
    base_sha = os.environ.get("MONDE_ATTEST_BASE", "")
    base_ref = os.environ.get("MONDE_ATTEST_BASE_REF", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if (
        repo != "tobianahillel-afk/monde"
        or not _sha(sha)
        or pr != "2"
        or not _sha(base_sha)
        or base_ref != "main"
        or not token
    ):
        raise AttestationError("invalid trusted-source invocation identity")
    # Pending invalidates any prior success for the same head/context before
    # reading mutable GitHub authority. A failure is published on the SAME
    # candidate head; a base-owned run status is never used as PR-head proof.
    _publish_status(
        repo, sha, token, "pending", "Validating exact PR #2 source and merge tree",
        base_sha=base_sha,
    )
    try:
        count = _verify_approved_merge(repo, token, sha, base_sha)
    except (AttestationError, OSError, ValueError):
        _publish_status(
            repo, sha, token, "failure",
            "Trusted source or merged-result authority rejected",
            base_sha=base_sha,
        )
        raise
    try:
        _publish_status(
            repo, sha, token, "success",
            "Approved source and merge result verified",
            base_sha=base_sha,
        )
    except (AttestationError, OSError, ValueError):
        # A failed/malformed acknowledgement does not mean the remote success
        # POST was rejected. Attempt a terminal compensating failure on the
        # SAME head/context/base, and never return a successful workflow run.
        # Even a confirmed compensation is not sufficient merge authority:
        # consumers must also verify the trusted run completed successfully.
        try:
            _publish_status(
                repo, sha, token, "failure",
                "Unconfirmed trusted-source success must not authorize merge",
                base_sha=base_sha,
            )
        except (AttestationError, OSError, ValueError) as compensation:
            raise AttestationError(
                "trusted-source success acknowledgement ambiguous; "
                "failure compensation also unconfirmed"
            ) from compensation
        raise
    print(f"MONDE trusted-source attestation PASS: PR #{pr}, {count} approved Git objects, head={sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AttestationError, OSError, ValueError) as exc:
        print(f"MONDE trusted-source attestation FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
