from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

MAX_PAGES = 20
CANONICAL_WORKFLOW_ID = 354465551
CANONICAL_WORKFLOW_PATH = ".github/workflows/governance.yml"
PR_FAMILY_EVENTS = {"pull_request", "pull_request_review", "pull_request_review_comment"}


def request_data(url: str, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode()) if raw else {}


def paged(url: str, token: str, collection_key: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        sep = "&" if "?" in url else "?"
        payload = request_data(f"{url}{sep}per_page=100&page={page}", token)
        if collection_key is None:
            items = payload
        elif isinstance(payload, dict):
            items = payload.get(collection_key)
        else:
            items = None
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RuntimeError("GitHub returned malformed paginated JSON")
        out.extend(items)
        if len(items) < 100:
            return out
    raise RuntimeError(f"GitHub pagination exceeded {MAX_PAGES} pages")


def open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    items = paged(f"https://api.github.com/repos/{repo}/pulls?state=open", token)
    for item in items:
        head = item.get("head")
        if not isinstance(item.get("number"), int) or not isinstance(head, dict) or not isinstance(head.get("sha"), str) or not head["sha"]:
            raise RuntimeError("GitHub returned malformed open pull request")
    return items


def latest_completed_gate_runs(repo: str, token: str) -> dict[str, dict[str, Any]]:
    runs = paged(
        f"https://api.github.com/repos/{repo}/actions/runs?status=completed",
        token,
        "workflow_runs",
    )
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        workflow_id = run.get("workflow_id")
        path = run.get("path")
        event = run.get("event")
        head = run.get("head_sha")
        run_number = run.get("run_number")
        run_id = run.get("id")
        conclusion = run.get("conclusion")
        if workflow_id != CANONICAL_WORKFLOW_ID or path != CANONICAL_WORKFLOW_PATH:
            continue
        if event not in PR_FAMILY_EVENTS:
            continue
        if not isinstance(head, str) or not head or not isinstance(run_number, int) or not isinstance(run_id, int) or not isinstance(conclusion, str):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        previous = latest.get(head)
        if previous is None or run_number > int(previous["run_number"]):
            latest[head] = run
    return latest


def unresolved_review_threads(repo: str, pr: int, token: str) -> bool:
    owner, name = repo.split("/", 1)
    cursor: str | None = None
    while True:
        query = (
            "query($owner:String!,$name:String!,$number:Int!,$cursor:String){"
            "repository(owner:$owner,name:$name){pullRequest(number:$number){"
            "reviewThreads(first:100,after:$cursor){nodes{isResolved} pageInfo{hasNextPage endCursor}}"
            "}}}"
        )
        payload = {
            "query": query,
            "variables": {"owner": owner, "name": name, "number": pr, "cursor": cursor},
        }
        result = request_data("https://api.github.com/graphql", token, "POST", payload)
        if not isinstance(result, dict) or result.get("errors"):
            raise RuntimeError(f"malformed GraphQL response: {result!r}")
        try:
            page = result["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("malformed reviewThreads response") from exc
        if not isinstance(page, dict):
            raise RuntimeError("malformed reviewThreads response")
        nodes = page.get("nodes")
        info = page.get("pageInfo")
        if not isinstance(nodes, list) or any(
            not isinstance(node, dict) or not isinstance(node.get("isResolved"), bool) for node in nodes
        ):
            raise RuntimeError("malformed reviewThreads nodes")
        if not isinstance(info, dict) or not isinstance(info.get("hasNextPage"), bool):
            raise RuntimeError("malformed reviewThreads pageInfo")
        if any(node["isResolved"] is False for node in nodes):
            return True
        if not info["hasNextPage"]:
            return False
        cursor = info.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise RuntimeError("reviewThreads pagination missing cursor")


def rerun_workflow(repo: str, run_id: int, token: str) -> None:
    request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun", token, "POST", {})


def poll(repo: str, token: str) -> list[int]:
    rerun_ids: list[int] = []
    runs = latest_completed_gate_runs(repo, token)
    for pr in open_pull_requests(repo, token):
        number = pr["number"]
        head = pr["head"]["sha"]
        run = runs.get(head)
        if run is None or run["conclusion"] != "success":
            continue
        if not unresolved_review_threads(repo, number, token):
            continue
        run_id = run["id"]
        rerun_workflow(repo, run_id, token)
        rerun_ids.append(run_id)
    return rerun_ids


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or "/" not in repo or not token:
        print("ERROR BOOTSTRAP_POLL: GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2
    try:
        reruns = poll(repo, token)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR BOOTSTRAP_POLL: {exc}", file=sys.stderr)
        return 2
    print(f"MONDE bootstrap stale-green poll: reran {len(reruns)} stale successful gate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
