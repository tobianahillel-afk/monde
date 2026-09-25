from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from tools.governance import github_live_gate as live

WORKFLOW_FILE = "governance.yml"
MAX_PAGES = 20
PR_FAMILY_EVENTS = {"pull_request", "pull_request_review", "pull_request_review_comment"}


def _paged(url: str, token: str, collection_key: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        sep = "&" if "?" in url else "?"
        payload = live.request_data(f"{url}{sep}per_page=100&page={page}", token)
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
    return _paged(f"https://api.github.com/repos/{repo}/pulls?state=open", token)


def latest_completed_pr_runs(repo: str, token: str) -> dict[str, dict[str, Any]]:
    runs = _paged(
        f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs?status=completed",
        token,
        "workflow_runs",
    )
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if str(run.get("event") or "") not in PR_FAMILY_EVENTS:
            continue
        head = str(run.get("head_sha") or "")
        if not head:
            continue
        previous = latest.get(head)
        if previous is None or int(run.get("run_number") or 0) > int(previous.get("run_number") or 0):
            latest[head] = run
    return latest


def rerun_workflow(repo: str, run_id: int, token: str) -> None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun",
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status not in {201, 202, 204}:
            raise RuntimeError(f"unexpected rerun HTTP status {response.status}")


def poll(repo: str, token: str) -> list[int]:
    rerun_ids: list[int] = []
    runs = latest_completed_pr_runs(repo, token)
    for pr in open_pull_requests(repo, token):
        head = str(((pr.get("head") or {}).get("sha") or ""))
        number = pr.get("number")
        run = runs.get(head)
        if not head or not isinstance(number, int) or run is None or run.get("conclusion") != "success":
            continue
        threads = live.fetch_threads(repo, number, token)
        if not any(not item.get("isResolved") for item in threads):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise RuntimeError(f"successful MONDE Gate run for PR #{number} has no numeric id")
        rerun_workflow(repo, run_id, token)
        rerun_ids.append(run_id)
    return rerun_ids


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or "/" not in repo or not token:
        print("ERROR THREAD_STATE_POLL: GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2
    try:
        reruns = poll(repo, token)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR THREAD_STATE_POLL: {exc}", file=sys.stderr)
        return 2
    print(f"MONDE review-thread state poll: reran {len(reruns)} stale successful gate(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
