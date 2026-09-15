from __future__ import annotations

from datetime import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAX_PAGES = 20
CANONICAL_WORKFLOW_ID = 354465551
CANONICAL_WORKFLOW_PATH = ".github/workflows/governance.yml"
PR_FAMILY_EVENTS = {"pull_request", "pull_request_review", "pull_request_review_comment"}
TERMINAL_CONCLUSIONS = {
    "success",
    "failure",
    "neutral",
    "cancelled",
    "skipped",
    "timed_out",
    "action_required",
    "stale",
    "startup_failure",
}
MERGE_ACCEPTABLE_CONCLUSIONS = {"success", "neutral", "skipped"}
HeadIdentity = tuple[str, str, str]
PrWindow = tuple[datetime, datetime]


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


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _timestamp(value: Any, label: str) -> datetime:
    if not _nonempty_string(value):
        raise RuntimeError(f"GitHub returned malformed {label}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"GitHub returned malformed {label}") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"GitHub returned malformed {label}")
    return parsed


def _pr_head_identity(pr: dict[str, Any]) -> HeadIdentity:
    head = pr.get("head")
    if not isinstance(head, dict):
        raise RuntimeError("GitHub returned malformed pull request head")
    head_repo = head.get("repo")
    repo_name = head_repo.get("full_name") if isinstance(head_repo, dict) else None
    branch = head.get("ref")
    sha = head.get("sha")
    if not (_nonempty_string(repo_name) and _nonempty_string(branch) and _nonempty_string(sha)):
        raise RuntimeError("GitHub returned malformed pull request head identity")
    return (repo_name, branch, sha)


def _run_head_identity(run: dict[str, Any]) -> HeadIdentity:
    head_repo = run.get("head_repository")
    repo_name = head_repo.get("full_name") if isinstance(head_repo, dict) else None
    branch = run.get("head_branch")
    sha = run.get("head_sha")
    if not (_nonempty_string(repo_name) and _nonempty_string(branch) and _nonempty_string(sha)):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate head identity")
    repo_parts = repo_name.split("/")
    if len(repo_parts) != 2 or not all(repo_parts):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate head repository full_name")
    return (repo_name, branch, sha)


def _pr_created_at(pr: dict[str, Any]) -> datetime:
    return _timestamp(pr.get("created_at"), "pull request created_at")


def _run_created_at(run: dict[str, Any]) -> datetime:
    return _timestamp(run.get("created_at"), "canonical MONDE Gate created_at")


def _closed_pr_at(pr: dict[str, Any]) -> datetime:
    return _timestamp(pr.get("closed_at"), "closed pull request closed_at")


def _head_owner(identity: HeadIdentity) -> str:
    owner, separator, _name = identity[0].partition("/")
    if not separator or not owner:
        raise RuntimeError("GitHub returned malformed pull request head repository full_name")
    return owner


def open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    items = paged(f"https://api.github.com/repos/{repo}/pulls?state=open", token)
    seen: dict[HeadIdentity, int] = {}
    for item in items:
        number = item.get("number")
        if not _positive_int(number):
            raise RuntimeError("GitHub returned malformed open pull request")
        identity = _pr_head_identity(item)
        _pr_created_at(item)
        if item.get("state") != "open":
            raise RuntimeError("GitHub returned malformed open pull request state")
        previous = seen.get(identity)
        if previous is not None and previous != number:
            raise RuntimeError(
                f"open PRs #{previous} and #{number} share indistinguishable head identity {identity!r}"
            )
        seen[identity] = number
    return items


def overlapping_closed_pr_windows(
    repo: str,
    token: str,
    current_prs: dict[HeadIdentity, dict[str, Any]],
) -> dict[HeadIdentity, list[PrWindow]]:
    windows: dict[HeadIdentity, list[PrWindow]] = {identity: [] for identity in current_prs}
    cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for identity, current_pr in current_prs.items():
        current_created = _pr_created_at(current_pr)
        owner = _head_owner(identity)
        cache_key = (owner, identity[1])
        if cache_key not in cache:
            query = urllib.parse.urlencode({"state": "closed", "head": f"{owner}:{identity[1]}"})
            cache[cache_key] = paged(f"https://api.github.com/repos/{repo}/pulls?{query}", token)
        for historical_pr in cache[cache_key]:
            number = historical_pr.get("number")
            if not _positive_int(number) or historical_pr.get("state") != "closed":
                raise RuntimeError("GitHub returned malformed closed pull request")
            historical_identity = _pr_head_identity(historical_pr)
            historical_created = _pr_created_at(historical_pr)
            historical_closed = _closed_pr_at(historical_pr)
            if historical_closed < historical_created:
                raise RuntimeError("GitHub returned closed pull request with invalid lifetime")
            same_repo_branch = historical_identity[:2] == identity[:2]
            if not same_repo_branch or historical_closed < current_created:
                continue
            overlap_start = max(current_created, historical_created)
            windows[identity].append((overlap_start, historical_closed))
    return windows


def _updated_at(value: Any) -> datetime:
    return _timestamp(value, "canonical MONDE Gate updated_at")


def _run_recency(run: dict[str, Any]) -> tuple[datetime, int, int]:
    return (_updated_at(run.get("updated_at")), int(run["run_number"]), int(run["id"]))


def _run_is_ambiguous(run_created: datetime, windows: list[PrWindow]) -> bool:
    return any(start <= run_created <= end for start, end in windows)


def latest_completed_gate_runs(
    repo: str,
    token: str,
    current_prs: dict[HeadIdentity, dict[str, Any]] | None = None,
    overlap_windows: dict[HeadIdentity, list[PrWindow]] | None = None,
) -> dict[HeadIdentity, dict[str, Any]]:
    runs = paged(
        f"https://api.github.com/repos/{repo}/actions/workflows/{CANONICAL_WORKFLOW_ID}/runs?status=completed",
        token,
        "workflow_runs",
    )
    latest: dict[HeadIdentity, dict[str, Any]] = {}
    for run in runs:
        workflow_id = run.get("workflow_id")
        path = run.get("path")
        event = run.get("event")
        if workflow_id != CANONICAL_WORKFLOW_ID or path != CANONICAL_WORKFLOW_PATH:
            raise RuntimeError("canonical workflow endpoint returned mismatched workflow identity")
        if not _nonempty_string(event):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate event")
        if event not in PR_FAMILY_EVENTS:
            continue
        run_number = run.get("run_number")
        run_id = run.get("id")
        status = run.get("status")
        conclusion = run.get("conclusion")
        if (
            not _positive_int(run_number)
            or not _positive_int(run_id)
            or status != "completed"
            or not isinstance(conclusion, str)
            or conclusion not in TERMINAL_CONCLUSIONS
        ):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        run_created = _run_created_at(run)
        run_updated = _updated_at(run.get("updated_at"))
        if run_updated < run_created:
            raise RuntimeError("GitHub returned canonical MONDE Gate run with invalid lifetime")
        key = _run_head_identity(run)
        if current_prs is not None:
            pr = current_prs.get(key)
            if pr is None:
                continue
            if run_created < _pr_created_at(pr):
                continue
            windows = [] if overlap_windows is None else overlap_windows.get(key, [])
            if _run_is_ambiguous(run_created, windows):
                continue
        previous = latest.get(key)
        if previous is None or _run_recency(run) > _run_recency(previous):
            latest[key] = run
    return latest


def effective_gate_runs_by_head(runs: dict[HeadIdentity, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for (_repo_name, _branch, head), run in runs.items():
        previous = latest.get(head)
        if previous is None or _run_recency(run) > _run_recency(previous):
            latest[head] = run
    return latest


def unresolved_review_threads(repo: str, pr: int, token: str) -> bool:
    owner, name = repo.split("/", 1)
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _page_number in range(1, MAX_PAGES + 1):
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
        if not isinstance(result, dict):
            raise RuntimeError(f"malformed GraphQL response: {result!r}")
        if "errors" in result and result["errors"] != []:
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
        if "endCursor" not in info or (info["endCursor"] is not None and not isinstance(info["endCursor"], str)):
            raise RuntimeError("malformed reviewThreads pageInfo")
        next_cursor = info["endCursor"]
        if info["hasNextPage"] and not _nonempty_string(next_cursor):
            raise RuntimeError("reviewThreads pagination missing cursor")
        if any(node["isResolved"] is False for node in nodes):
            return True
        if not info["hasNextPage"]:
            return False
        if next_cursor in seen_cursors:
            raise RuntimeError("reviewThreads pagination repeated cursor")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise RuntimeError(f"reviewThreads pagination exceeded {MAX_PAGES} pages")


def rerun_workflow(repo: str, run_id: int, token: str) -> None:
    request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/rerun", token, "POST", {})


def _current_prs(prs: list[dict[str, Any]]) -> dict[HeadIdentity, dict[str, Any]]:
    return {_pr_head_identity(pr): pr for pr in prs}


def poll(repo: str, token: str) -> list[int]:
    rerun_ids: list[int] = []
    prs = open_pull_requests(repo, token)
    current_prs = _current_prs(prs)
    overlap_windows = overlapping_closed_pr_windows(repo, token, current_prs)
    runs = latest_completed_gate_runs(repo, token)
    current_runs = latest_completed_gate_runs(repo, token, current_prs, overlap_windows)
    effective = effective_gate_runs_by_head(runs)
    for pr in prs:
        number = pr["number"]
        identity = _pr_head_identity(pr)
        head = identity[2]
        effective_run = effective.get(head)
        if effective_run is None or effective_run["conclusion"] not in MERGE_ACCEPTABLE_CONCLUSIONS:
            continue
        target_run = current_runs.get(identity)
        if target_run is None:
            raise RuntimeError(
                f"effective merge-acceptable MONDE Gate for head {head} has no unambiguous run bound to open PR #{number} current incarnation"
            )
        if not unresolved_review_threads(repo, number, token):
            continue
        run_id = target_run["id"]
        rerun_workflow(repo, run_id, token)
        rerun_ids.append(run_id)
    return rerun_ids


def validate_github_contract(repo: str, pr_number: int, token: str) -> tuple[int, int, bool]:
    prs = open_pull_requests(repo, token)
    current = [pr for pr in prs if pr["number"] == pr_number]
    if len(current) != 1:
        raise RuntimeError(f"expected exactly one open PR #{pr_number}, observed {len(current)}")
    current_prs = _current_prs(current)
    overlap_windows = overlapping_closed_pr_windows(repo, token, current_prs)
    runs = latest_completed_gate_runs(repo, token, current_prs, overlap_windows)
    effective_gate_runs_by_head(runs)
    identity = _pr_head_identity(current[0])
    if identity not in runs:
        raise RuntimeError(f"no unambiguous canonical MONDE Gate run is bound to current incarnation of open PR #{pr_number}")
    unresolved = unresolved_review_threads(repo, pr_number, token)
    return len(prs), len(runs), unresolved


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repo or "/" not in repo or not token:
        print("ERROR BOOTSTRAP_POLL: GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2
    try:
        validate_pr = os.environ.get("BOOTSTRAP_VALIDATE_PR", "")
        if validate_pr:
            pr_number = int(validate_pr)
            if pr_number < 1:
                raise ValueError("PR number must be positive")
            open_count, gate_heads, unresolved = validate_github_contract(repo, pr_number, token)
            print(
                f"MONDE bootstrap GitHub contract: open_prs={open_count}, gate_heads={gate_heads}, "
                f"target_pr={pr_number}, unresolved_threads={str(unresolved).lower()}"
            )
            return 0
        reruns = poll(repo, token)
    except (RuntimeError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"ERROR BOOTSTRAP_POLL: {exc}", file=sys.stderr)
        return 2
    print(f"MONDE bootstrap stale-green poll: reran {len(reruns)} stale merge-acceptable gate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())