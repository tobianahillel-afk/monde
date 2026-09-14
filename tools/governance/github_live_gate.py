from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LiveFinding:
    rule: str
    message: str

    def render(self) -> str:
        return f"ERROR {self.rule}: {self.message}"


def request_data(url: str, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())


def request_json(url: str, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed = request_data(url, token, method, body)
    if not isinstance(parsed, dict):
        raise RuntimeError("GitHub returned non-object JSON")
    return parsed


def _graphql_page(repo: str, pr: int, token: str, field: str, selection: str, cursor: str | None) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    query = (
        "query($owner:String!,$name:String!,$number:Int!,$cursor:String){"
        "repository(owner:$owner,name:$name){pullRequest(number:$number){"
        f"{field}(first:100,after:$cursor){{nodes{{{selection}}} pageInfo{{hasNextPage endCursor}}}}"
        "}}}"
    )
    payload = {"query": query, "variables": {"owner": owner, "name": name, "number": pr, "cursor": cursor}}
    result = request_json("https://api.github.com/graphql", token, "POST", payload)
    if result.get("errors"):
        raise RuntimeError(f"GraphQL errors: {result['errors']}")
    try:
        page = result["data"]["repository"]["pullRequest"][field]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"malformed {field} response") from exc
    if not isinstance(page, dict):
        raise RuntimeError(f"malformed {field} response")
    return page


def _paginate_graphql(repo: str, pr: int, token: str, field: str, selection: str) -> list[dict[str, Any]]:
    cursor: str | None = None
    nodes: list[dict[str, Any]] = []
    while True:
        page = _graphql_page(repo, pr, token, field, selection, cursor)
        raw_nodes = page.get("nodes") or []
        if not isinstance(raw_nodes, list):
            raise RuntimeError(f"malformed {field} nodes")
        nodes.extend(item for item in raw_nodes if isinstance(item, dict))
        info = page.get("pageInfo") or {}
        if not isinstance(info, dict) or not info.get("hasNextPage"):
            break
        cursor = info.get("endCursor")
        if not cursor:
            raise RuntimeError("pagination says next page but endCursor is missing")
    return nodes


def fetch_threads(repo: str, pr: int, token: str) -> list[dict[str, Any]]:
    return _paginate_graphql(repo, pr, token, "reviewThreads", "id isResolved")


def fetch_reviews(repo: str, pr: int, token: str) -> list[dict[str, Any]]:
    return _paginate_graphql(repo, pr, token, "reviews", "id state submittedAt commit{oid} author{login}")


def independent_exact_head_approvers(reviews: list[dict[str, Any]], head: str, author: str) -> set[str]:
    latest: dict[str, tuple[str, str]] = {}
    for review in reviews:
        actor = str(((review.get("author") or {}).get("login") or ""))
        commit = str(((review.get("commit") or {}).get("oid") or ""))
        submitted = str(review.get("submittedAt") or "")
        state = str(review.get("state") or "")
        if not actor or actor == author or commit != head:
            continue
        previous = latest.get(actor)
        if previous is None or submitted >= previous[0]:
            latest[actor] = (submitted, state)
    return {actor for actor, (_, state) in latest.items() if state == "APPROVED"}


def durable_open_findings(root: Path) -> list[str] | None:
    path = root / "registry/work-items/WORK-0002.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    review_plan = data.get("review_plan") or {}
    values = review_plan.get("open_findings") if isinstance(review_plan, dict) else None
    if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
        return None
    return values


def validate_repository_owner_permission(repo: str, token: str) -> list[LiveFinding]:
    info = request_json(f"https://api.github.com/repos/{repo}", token)
    owner = str(((info.get("owner") or {}).get("login") or ""))
    full_name = str(info.get("full_name") or info.get("name") or "")
    if "/" not in full_name:
        full_name = repo
    if not owner or owner != repo.split("/", 1)[0] or full_name != repo:
        return [LiveFinding("REPOSITORY_IDENTITY", f"GitHub repository metadata does not establish expected repository {repo}")]
    permission = request_json(
        f"https://api.github.com/repos/{repo}/collaborators/{urllib.parse.quote(owner, safe='')}/permission",
        token,
    )
    if permission.get("permission") != "admin":
        return [LiveFinding("REPOSITORY_OWNER_PERMISSION", f"GitHub reports owner {owner!r} permission={permission.get('permission')!r}, expected admin")]
    return []


def validate(repo: str, pr: int, head: str, token: str, root: Path | None = None) -> tuple[list[LiveFinding], str]:
    root = (root or Path(".")).resolve()
    info = request_json(f"https://api.github.com/repos/{repo}/pulls/{pr}", token)
    findings: list[LiveFinding] = []
    actual = ((info.get("head") or {}).get("sha"))
    if actual != head:
        findings.append(LiveFinding("HEAD_MISMATCH", f"expected {head}, GitHub reports {actual}"))
    if info.get("draft") is True:
        return findings, "DEFERRED_DRAFT"
    if info.get("state") != "open":
        findings.append(LiveFinding("PR_STATE", f"PR is {info.get('state')!r}, expected open"))
    if info.get("mergeable") is not True:
        findings.append(LiveFinding("MERGEABLE", f"GitHub mergeable={info.get('mergeable')!r}; fail closed"))

    findings.extend(validate_repository_owner_permission(repo, token))

    threads = fetch_threads(repo, pr, token)
    unresolved = [str(item.get("id") or "") for item in threads if not item.get("isResolved")]
    if unresolved:
        findings.append(LiveFinding("UNRESOLVED_THREADS", f"{len(unresolved)} unresolved review thread(s)"))

    durable = durable_open_findings(root)
    if durable is None or len(durable) != len(unresolved):
        findings.append(LiveFinding("DURABLE_FINDING_SET", f"WORK-0002 durable open_findings count={None if durable is None else len(durable)} does not match live unresolved thread count={len(unresolved)}"))

    author = str(((info.get("user") or {}).get("login") or ""))
    approvers = independent_exact_head_approvers(fetch_reviews(repo, pr, token), head, author)
    if not approvers:
        findings.append(LiveFinding("INDEPENDENT_EXACT_HEAD_APPROVAL", "no independent GitHub APPROVED review is bound to the exact current PR HEAD"))

    return findings, "READY_CHECKED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--head", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR LIVE_GATE: GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    try:
        findings, status = validate(args.repo, args.pr, args.head, token, Path(args.root))
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR LIVE_GATE: {exc}", file=sys.stderr)
        return 2
    for finding in findings:
        print(finding.render(), file=sys.stderr)
    payload = {"status": status, "findings": [asdict(item) for item in findings], "repo": args.repo, "pr": args.pr, "head": args.head}
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"MONDE GitHub live gate: {status}, {len(findings)} error(s)")
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
