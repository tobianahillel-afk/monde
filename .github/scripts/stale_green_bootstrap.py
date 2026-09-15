from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAX_PAGES = 20
FILTERED_WORKFLOW_RUN_SEARCH_LIMIT = 1000
CANONICAL_WORKFLOW_ID = 354465551
CANONICAL_WORKFLOW_PATH = ".github/workflows/governance.yml"
REQUIRED_GATE_JOB_NAME = "MONDE / Merge Gate"
GITHUB_ACTIONS_APP_ID = 15368
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
CHECK_RUN_STATUSES = {"queued", "in_progress", "requested", "waiting", "pending", "completed"}
MERGE_ACCEPTABLE_CONCLUSIONS = {"success", "neutral", "skipped"}
HeadIdentity = tuple[str, str, str]
PrWindow = tuple[datetime, datetime]


class FilteredSearchLimitExceeded(RuntimeError):
    pass


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


def paged(
    url: str,
    token: str,
    collection_key: str | None = None,
    *,
    require_total_count: bool = False,
    max_total_count: int | None = None,
    unique_id_field: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    expected_total: int | None = None
    seen_ids: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        sep = "&" if "?" in url else "?"
        payload = request_data(f"{url}{sep}per_page=100&page={page}", token)
        if collection_key is None:
            items = payload
        elif isinstance(payload, dict):
            items = payload.get(collection_key)
            if require_total_count:
                total_count = payload.get("total_count")
                if type(total_count) is not int or total_count < 0:
                    raise RuntimeError("GitHub returned malformed paginated total_count")
                if max_total_count is not None and total_count >= max_total_count:
                    raise FilteredSearchLimitExceeded(
                        f"GitHub filtered collection total_count {total_count} reaches supported search limit {max_total_count}"
                    )
                if expected_total is None:
                    expected_total = total_count
                elif total_count != expected_total:
                    raise RuntimeError("GitHub returned inconsistent paginated total_count")
        else:
            items = None
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RuntimeError("GitHub returned malformed paginated JSON")
        if unique_id_field is not None:
            for item in items:
                value = item.get(unique_id_field)
                if type(value) is not int:
                    raise RuntimeError("GitHub returned malformed paginated record identity")
                if value in seen_ids:
                    raise RuntimeError("GitHub returned duplicate paginated record identity")
                seen_ids.add(value)
        out.extend(items)
        if require_total_count:
            assert expected_total is not None
            if len(out) > expected_total:
                raise RuntimeError("GitHub paginated collection exceeds total_count")
            if len(out) == expected_total:
                return out
        if len(items) < 100:
            if require_total_count:
                raise RuntimeError("GitHub returned incomplete paginated collection")
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


def _pr_updated_at(pr: dict[str, Any]) -> datetime:
    return _timestamp(pr.get("updated_at"), "closed pull request updated_at")


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


def _closed_pr_history(
    repo: str,
    token: str,
    owner: str,
    branch: str,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "state": "closed",
            "head": f"{owner}:{branch}",
            "sort": "updated",
            "direction": "desc",
        }
    )
    out: list[dict[str, Any]] = []
    previous_updated: datetime | None = None
    for page in range(1, MAX_PAGES + 1):
        payload = request_data(
            f"https://api.github.com/repos/{repo}/pulls?{query}&per_page=100&page={page}",
            token,
        )
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise RuntimeError("GitHub returned malformed closed pull request history")
        cutoff_reached = False
        for item in payload:
            number = item.get("number")
            if not _positive_int(number) or item.get("state") != "closed":
                raise RuntimeError("GitHub returned malformed closed pull request")
            _pr_head_identity(item)
            created = _pr_created_at(item)
            closed = _closed_pr_at(item)
            updated = _pr_updated_at(item)
            if closed < created or updated < closed:
                raise RuntimeError("GitHub returned closed pull request with invalid lifetime")
            if previous_updated is not None and updated > previous_updated:
                raise RuntimeError("GitHub returned closed pull request history out of requested order")
            previous_updated = updated
            if updated < cutoff:
                cutoff_reached = True
                break
            out.append(item)
        if cutoff_reached or len(payload) < 100:
            return out
    raise RuntimeError("closed pull request history exceeded bounded pagination before active-incarnation cutoff")


def overlapping_closed_pr_windows(
    repo: str,
    token: str,
    current_prs: dict[HeadIdentity, dict[str, Any]],
) -> dict[HeadIdentity, list[PrWindow]]:
    windows: dict[HeadIdentity, list[PrWindow]] = {identity: [] for identity in current_prs}
    branch_bounds: dict[tuple[str, str], datetime] = {}
    for identity, pr in current_prs.items():
        key = (_head_owner(identity), identity[1])
        created = _pr_created_at(pr)
        previous = branch_bounds.get(key)
        if previous is None or created < previous:
            branch_bounds[key] = created
    histories = {
        key: _closed_pr_history(repo, token, key[0], key[1], bound)
        for key, bound in branch_bounds.items()
    }
    for identity, current_pr in current_prs.items():
        current_created = _pr_created_at(current_pr)
        key = (_head_owner(identity), identity[1])
        for historical_pr in histories[key]:
            historical_identity = _pr_head_identity(historical_pr)
            historical_created = _pr_created_at(historical_pr)
            historical_closed = _closed_pr_at(historical_pr)
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


def _active_head_created_bounds(current_prs: dict[HeadIdentity, dict[str, Any]]) -> dict[str, datetime]:
    bounds: dict[str, datetime] = {}
    for identity, pr in current_prs.items():
        created = _pr_created_at(pr)
        head = identity[2]
        previous = bounds.get(head)
        if previous is None or created < previous:
            bounds[head] = created
    return bounds


def _utc_second(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _github_search_time(value: datetime) -> str:
    return _utc_second(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_snapshot_fingerprint(runs: list[dict[str, Any]]) -> tuple[tuple[int, str], ...]:
    fingerprint: list[tuple[int, str]] = []
    for run in runs:
        run_id = run.get("id")
        if not _positive_int(run_id):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run id in filtered snapshot")
        try:
            encoded = json.dumps(run, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("GitHub returned non-canonicalizable canonical MONDE Gate run") from exc
        fingerprint.append((run_id, encoded))
    return tuple(sorted(fingerprint))


def _read_completed_gate_window(
    repo: str,
    token: str,
    head: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    created_range = f"{_github_search_time(start)}..{_github_search_time(end)}"
    query = urllib.parse.urlencode(
        {
            "status": "completed",
            "head_sha": head,
            "created": created_range,
        }
    )
    return paged(
        f"https://api.github.com/repos/{repo}/actions/workflows/{CANONICAL_WORKFLOW_ID}/runs?{query}",
        token,
        "workflow_runs",
        require_total_count=True,
        max_total_count=FILTERED_WORKFLOW_RUN_SEARCH_LIMIT,
        unique_id_field="id",
    )


def _bounded_completed_gate_runs(
    repo: str,
    token: str,
    head: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    start = _utc_second(start)
    end = _utc_second(end)
    if end < start:
        return []

    def split_window() -> list[dict[str, Any]]:
        if start == end:
            raise RuntimeError(
                "canonical MONDE Gate filtered history reaches GitHub search limit within one timestamp second"
            )
        span_seconds = int((end - start).total_seconds())
        midpoint = start + timedelta(seconds=span_seconds // 2)
        right_start = midpoint + timedelta(seconds=1)
        return _bounded_completed_gate_runs(repo, token, head, start, midpoint) + _bounded_completed_gate_runs(
            repo, token, head, right_start, end
        )

    try:
        first = _read_completed_gate_window(repo, token, head, start, end)
    except FilteredSearchLimitExceeded:
        return split_window()
    try:
        second = _read_completed_gate_window(repo, token, head, start, end)
    except FilteredSearchLimitExceeded:
        return split_window()
    if _run_snapshot_fingerprint(first) != _run_snapshot_fingerprint(second):
        raise RuntimeError("GitHub returned unstable canonical MONDE Gate filtered snapshot")
    return first


def _scoped_completed_gate_runs(
    repo: str,
    token: str,
    active_prs: dict[HeadIdentity, dict[str, Any]],
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    scan_end = _utc_second(datetime.now(timezone.utc))
    for head, created in sorted(_active_head_created_bounds(active_prs).items()):
        runs.extend(_bounded_completed_gate_runs(repo, token, head, created, scan_end))
    return runs


def latest_completed_gate_runs(
    repo: str,
    token: str,
    current_prs: dict[HeadIdentity, dict[str, Any]] | None = None,
    overlap_windows: dict[HeadIdentity, list[PrWindow]] | None = None,
    active_prs: dict[HeadIdentity, dict[str, Any]] | None = None,
) -> dict[HeadIdentity, dict[str, Any]]:
    if active_prs is None:
        runs = paged(
            f"https://api.github.com/repos/{repo}/actions/workflows/{CANONICAL_WORKFLOW_ID}/runs?status=completed",
            token,
            "workflow_runs",
            unique_id_field="id",
        )
    else:
        runs = _scoped_completed_gate_runs(repo, token, active_prs)
    latest: dict[HeadIdentity, dict[str, Any]] = {}
    for run in runs:
        workflow_id = run.get("workflow_id")
        path = run.get("path")
        event = run.get("event")
        if not _positive_int(workflow_id) or workflow_id != CANONICAL_WORKFLOW_ID or path != CANONICAL_WORKFLOW_PATH:
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


def latest_required_check(repo: str, head: str, token: str) -> dict[str, Any] | None:
    query = urllib.parse.urlencode(
        {
            "check_name": REQUIRED_GATE_JOB_NAME,
            "filter": "latest",
            "app_id": GITHUB_ACTIONS_APP_ID,
            "per_page": 100,
        }
    )
    payload = request_data(f"https://api.github.com/repos/{repo}/commits/{head}/check-runs?{query}", token)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned malformed required-check response")
    total_count = payload.get("total_count")
    checks = payload.get("check_runs")
    if type(total_count) is not int or total_count < 0 or not isinstance(checks, list):
        raise RuntimeError("GitHub returned malformed required-check response")
    if any(not isinstance(check, dict) for check in checks) or len(checks) != total_count:
        raise RuntimeError("GitHub returned incomplete required-check response")
    if total_count == 0:
        return None
    if total_count != 1:
        raise RuntimeError(f"GitHub returned {total_count} latest required checks for head {head}; expected exactly one")
    check = checks[0]
    app = check.get("app")
    status = check.get("status")
    conclusion = check.get("conclusion")
    if (
        not _positive_int(check.get("id"))
        or check.get("name") != REQUIRED_GATE_JOB_NAME
        or check.get("head_sha") != head
        or not isinstance(app, dict)
        or not _positive_int(app.get("id"))
        or app.get("id") != GITHUB_ACTIONS_APP_ID
        or app.get("slug") != "github-actions"
        or status not in CHECK_RUN_STATUSES
    ):
        raise RuntimeError("GitHub returned malformed required MONDE Merge Gate check")
    if status == "completed":
        if not isinstance(conclusion, str) or conclusion not in TERMINAL_CONCLUSIONS:
            raise RuntimeError("GitHub returned malformed completed required MONDE Merge Gate check")
    elif conclusion is not None:
        raise RuntimeError("GitHub returned incomplete required MONDE Merge Gate check with a conclusion")
    return check


def required_merge_gate_conclusion(repo: str, run: dict[str, Any], token: str) -> str:
    run_id = run.get("id")
    run_attempt = run.get("run_attempt")
    head_sha = run.get("head_sha")
    if not _positive_int(run_id) or not _positive_int(run_attempt) or not _nonempty_string(head_sha):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate run for required-check lookup")
    jobs = paged(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?filter=latest",
        token,
        "jobs",
        require_total_count=True,
        unique_id_field="id",
    )
    required_jobs: list[dict[str, Any]] = []
    for job in jobs:
        conclusion = job.get("conclusion")
        job_run_id = job.get("run_id")
        job_run_attempt = job.get("run_attempt")
        if (
            not _positive_int(job.get("id"))
            or not _positive_int(job_run_id)
            or job_run_id != run_id
            or not _positive_int(job_run_attempt)
            or job_run_attempt != run_attempt
            or not _nonempty_string(job.get("name"))
            or job.get("status") != "completed"
            or not isinstance(conclusion, str)
            or conclusion not in TERMINAL_CONCLUSIONS
            or job.get("head_sha") != head_sha
        ):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate job")
        if job["name"] == REQUIRED_GATE_JOB_NAME:
            required_jobs.append(job)
    if len(required_jobs) != 1:
        raise RuntimeError(
            f"canonical workflow run {run_id} exposes {len(required_jobs)} {REQUIRED_GATE_JOB_NAME!r} jobs; expected exactly one"
        )
    return required_jobs[0]["conclusion"]


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
    current_runs = latest_completed_gate_runs(
        repo,
        token,
        current_prs,
        overlap_windows,
        active_prs=current_prs,
    )
    check_cache: dict[str, dict[str, Any] | None] = {}
    target_job_cache: dict[tuple[int, int], str] = {}
    for pr in prs:
        number = pr["number"]
        identity = _pr_head_identity(pr)
        head = identity[2]
        if head not in check_cache:
            check_cache[head] = latest_required_check(repo, head, token)
        check = check_cache[head]
        if check is None or check["status"] != "completed" or check["conclusion"] not in MERGE_ACCEPTABLE_CONCLUSIONS:
            continue
        if not unresolved_review_threads(repo, number, token):
            continue
        target_run = current_runs.get(identity)
        if target_run is None:
            raise RuntimeError(
                f"effective merge-acceptable MONDE Gate for head {head} has no unambiguous run bound to open PR #{number} current incarnation"
            )
        cache_key = (target_run["id"], target_run["run_attempt"])
        if cache_key not in target_job_cache:
            target_job_cache[cache_key] = required_merge_gate_conclusion(repo, target_run, token)
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
    runs = latest_completed_gate_runs(
        repo,
        token,
        current_prs,
        overlap_windows,
        active_prs=current_prs,
    )
    identity = _pr_head_identity(current[0])
    if identity not in runs:
        raise RuntimeError(f"no unambiguous canonical MONDE Gate run is bound to current incarnation of open PR #{pr_number}")
    check = latest_required_check(repo, identity[2], token)
    if check is None:
        raise RuntimeError(f"no latest {REQUIRED_GATE_JOB_NAME!r} check exists for open PR #{pr_number} head")
    required_merge_gate_conclusion(repo, runs[identity], token)
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
