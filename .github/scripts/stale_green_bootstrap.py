from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

MAX_PAGES = 20
WORKFLOW_NAME = "MONDE Gate"
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
        if not isinstance(items, list):
            raise RuntimeError("GitHub returned malformed paginated JSON")
        out.extend(item for item in items if isinstance(item, dict))
        if len(items) < 100:
            return out
    raise RuntimeError(f"GitHub pagination exceeded {MAX_PAGES} pages")


def open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    return paged(f"https://api.github.com/repos/{repo}/pulls?state=open", token)


def latest_completed_gate_runs(repo: str, token: str) -> dict[str, dict[str, Any]]:
    runs = paged(
        f"https://api.github.com/repos/{repo}/actions/runs?status=completed",
        token,
        "workflow_runs",
    )
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if str(run.get("name") or "") != WORKFLOW_NAME:
            continue
        if str(run.get("event") or "") not in PR_FAMILY_EVENTS:
            continue
        head = str(run.get("head_sha") or "")
        if not head:
            continue
        previous = latest.get(head)
        if previous is None or int(run.get("run_number") or 0) > int(previous.get("run_number") or 0):
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
        nodes = page.get("nodes") if isinstance(page, dict) else None
        if not isinstance(nodes, list):
            raise RuntimeError("malformed reviewThreads nodes")
        if any(isinstance(node, dict) and node.get("isResolved") is False for node in nodes):
            return True
        info = page.get("pageInfo") or {}
        if not isinstance(info, dict) or not info.get("hasNextPage"):
            return False
        cursor = info.get("endCursor")
        if not cursor:
            raise RuntimeError("reviewThreads pagination missing cursor")


def rerun_workflow(repo: str, run_id: int, token: str) -> None:
    request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun", token, "POST", {})


def poll(repo: str, token: str) -> list[int]:
    rerun_ids: list[int] = []
    runs = latest_completed_gate_runs(repo, token)
    for pr in open_pull_requests(repo, token):
        number = pr.get("number")
        head = str(((pr.get("head") or {}).get("sha") or ""))
        if not isinstance(number, int) or not head:
            continue
        run = runs.get(head)
        if run is None or run.get("conclusion") != "success":
            continue
        if not unresolved_review_threads(repo, number, token):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise RuntimeError(f"successful {WORKFLOW_NAME} run for PR #{number} has no numeric id")
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
