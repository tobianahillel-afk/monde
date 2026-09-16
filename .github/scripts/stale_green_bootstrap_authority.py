from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_pr_snapshot as snapshot

MAX_GITHUB_REQUESTS_PER_INVOCATION = 100
MAX_HEADS_PER_INVOCATION = 7
MAX_RERUNS_PER_INVOCATION = 3
MAX_TARGET_CHECK_CANDIDATES = 12
MAX_POSTCONDITION_POLLS = 6
POSTCONDITION_POLL_SECONDS = 2.0
MIN_TARGET_REQUEST_HEADROOM = 24
STATE_WRITE_REQUEST_RESERVE = 1
SCHEDULER_STATE_TITLE = "MONDE stale-green scheduler state — machine managed"
SCHEDULER_STATE_MARKER = "MONDE_STALE_GREEN_SCHEDULER_V1"
_REUSABLE_WORKFLOW_PATH = ".github/workflows/_governance-core.yml"
_PULL_REF = re.compile(r"refs/pull/([1-9][0-9]*)/merge")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_request_count = 0
_ORIGINAL_REQUEST_DATA = snapshot._ORIGINAL_REQUEST_DATA


class DeferredForBudget(RuntimeError):
    pass


def _reset_request_budget() -> None:
    global _request_count
    _request_count = 0


def _remaining_request_budget() -> int:
    return MAX_GITHUB_REQUESTS_PER_INVOCATION - _request_count


def _budgeted_request_data(
    url: str,
    token: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> Any:
    global _request_count
    if _request_count >= MAX_GITHUB_REQUESTS_PER_INVOCATION:
        raise RuntimeError(
            f"bootstrap GitHub request budget exceeded ({_request_count}/{MAX_GITHUB_REQUESTS_PER_INVOCATION})"
        )
    _request_count += 1
    return _ORIGINAL_REQUEST_DATA(url, token, method, body)


def _scheduler_issue_number() -> int:
    raw = os.environ.get("BOOTSTRAP_STATE_ISSUE", "")
    try:
        number = int(raw)
    except ValueError as exc:
        raise RuntimeError("BOOTSTRAP_STATE_ISSUE must be a positive integer") from exc
    if number < 1:
        raise RuntimeError("BOOTSTRAP_STATE_ISSUE must be a positive integer")
    return number


def _scheduler_body(cursor_pr: int) -> str:
    return (
        f"{SCHEDULER_STATE_MARKER}\n"
        f"cursor_pr: {cursor_pr}\n\n"
        "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
        "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
    )


def _parse_scheduler_cursor(issue: dict[str, Any], issue_number: int) -> int:
    if (
        issue.get("number") != issue_number
        or issue.get("title") != SCHEDULER_STATE_TITLE
        or issue.get("state") != "open"
        or "pull_request" in issue
    ):
        raise RuntimeError("scheduler state issue identity is malformed or no longer authoritative")
    body = issue.get("body")
    if not isinstance(body, str):
        raise RuntimeError("scheduler state issue body is malformed")
    match = re.fullmatch(
        rf"{re.escape(SCHEDULER_STATE_MARKER)}\ncursor_pr: ([0-9]+)\n\n"
        r"Machine-managed durable cursor for the trusted default-branch stale-green bootstrap\. "
        r"Do not edit manually\. The scheduled bootstrap validates this exact marker before reading or updating the cursor\.",
        body,
    )
    if match is None:
        raise RuntimeError("scheduler state issue body does not match the closed-world cursor contract")
    return int(match.group(1))


def _read_scheduler_cursor(repo: str, token: str) -> int:
    issue_number = _scheduler_issue_number()
    issue = core.request_data(f"https://api.github.com/repos/{repo}/issues/{issue_number}", token)
    if not isinstance(issue, dict):
        raise RuntimeError("scheduler state issue response is malformed")
    return _parse_scheduler_cursor(issue, issue_number)


def _write_scheduler_cursor(repo: str, token: str, cursor_pr: int) -> None:
    if cursor_pr < 0:
        raise RuntimeError("scheduler cursor cannot be negative")
    issue_number = _scheduler_issue_number()
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        token,
        "PATCH",
        {"body": _scheduler_body(cursor_pr)},
    )
    if not isinstance(payload, dict) or _parse_scheduler_cursor(payload, issue_number) != cursor_pr:
        raise RuntimeError("scheduler state issue update was not durably acknowledged")


def _head_groups_after_cursor(
    pull_requests: list[dict[str, Any]],
    cursor_pr: int,
) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for pr in pull_requests:
        head = core._pr_head_identity(pr)[2]
        groups.setdefault(head, []).append(pr)
    ordered = [sorted(group, key=lambda item: item["number"]) for group in groups.values()]
    ordered.sort(key=lambda group: group[0]["number"])
    if not ordered:
        return []
    split = next((index for index, group in enumerate(ordered) if group[0]["number"] > cursor_pr), 0)
    return ordered[split:] + ordered[:split]


def _current_pr(repo: str, token: str, original: dict[str, Any]) -> dict[str, Any] | None:
    number = original["number"]
    payload = core.request_data(f"https://api.github.com/repos/{repo}/pulls/{number}", token)
    if not isinstance(payload, dict) or payload.get("number") != number:
        raise RuntimeError(f"GitHub returned malformed direct pull request #{number}")
    if payload.get("state") != "open":
        return None
    if snapshot._pr_snapshot_fingerprint([payload], closed=False) != snapshot._pr_snapshot_fingerprint(
        [original], closed=False
    ):
        return None
    return payload


def _validate_gate_check(check: dict[str, Any], head: str) -> tuple[int, int]:
    app = check.get("app")
    if (
        not core._positive_int(check.get("id"))
        or check.get("name") != core.REQUIRED_GATE_JOB_NAME
        or check.get("head_sha") != head
        or not isinstance(app, dict)
        or app.get("id") != core.GITHUB_ACTIONS_APP_ID
        or app.get("slug") != "github-actions"
    ):
        raise RuntimeError("GitHub returned malformed MONDE Gate check candidate")
    details = check.get("details_url")
    if not core._nonempty_string(details):
        raise RuntimeError("MONDE Gate check candidate lacks Actions details URL")
    match = re.fullmatch(r"https://github\.com/[^/]+/[^/]+/actions/runs/([1-9][0-9]*)/job/([1-9][0-9]*)", details)
    if match is None:
        raise RuntimeError("MONDE Gate check candidate has non-canonical Actions details URL")
    run_id = int(match.group(1))
    job_id = int(match.group(2))
    if check["id"] != job_id:
        raise RuntimeError("MONDE Gate check id does not match its Actions job id")
    return run_id, job_id


def _candidate_gate_checks(repo: str, head: str, token: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "check_name": core.REQUIRED_GATE_JOB_NAME,
            "filter": "all",
            "app_id": core.GITHUB_ACTIONS_APP_ID,
            "per_page": 100,
        }
    )
    payload = core.request_data(f"https://api.github.com/repos/{repo}/commits/{head}/check-runs?{query}", token)
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub returned malformed MONDE Gate check history")
    total = payload.get("total_count")
    checks = payload.get("check_runs")
    if type(total) is not int or total < 0 or not isinstance(checks, list) or any(
        not isinstance(check, dict) for check in checks
    ):
        raise RuntimeError("GitHub returned malformed MONDE Gate check history")
    if len(checks) > 100 or len(checks) > total:
        raise RuntimeError("GitHub returned inconsistent MONDE Gate check history")
    validated: list[tuple[Any, int, dict[str, Any]]] = []
    for check in checks:
        _validate_gate_check(check, head)
        status = check.get("status")
        conclusion = check.get("conclusion")
        if status != "completed" or not isinstance(conclusion, str) or conclusion not in core.TERMINAL_CONCLUSIONS:
            continue
        completed = core._timestamp(check.get("completed_at"), "MONDE Gate check completed_at")
        validated.append((completed, int(check["id"]), check))
    validated.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in validated[:MAX_TARGET_CHECK_CANDIDATES]]


def _direct_target_for_pr(
    repo: str,
    token: str,
    pr: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM:
        raise DeferredForBudget("insufficient request headroom for bounded target validation and mutation")
    number = pr["number"]
    identity = core._pr_head_identity(pr)
    for check in _candidate_gate_checks(repo, identity[2], token):
        if _remaining_request_budget() <= STATE_WRITE_REQUEST_RESERVE + MAX_POSTCONDITION_POLLS + 6:
            raise DeferredForBudget("request headroom reached while validating bounded check candidates")
        run_id, job_id = _validate_gate_check(check, identity[2])
        run = core.request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
        if not isinstance(run, dict):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        if (
            run.get("id") != run_id
            or run.get("workflow_id") != core.CANONICAL_WORKFLOW_ID
            or run.get("path") != core.CANONICAL_WORKFLOW_PATH
            or run.get("event") not in core.PR_FAMILY_EVENTS
            or run.get("status") != "completed"
            or not isinstance(run.get("conclusion"), str)
            or run.get("conclusion") not in core.TERMINAL_CONCLUSIONS
            or not core._positive_int(run.get("run_attempt"))
        ):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        if core._run_head_identity(run) != identity:
            continue
        if core._run_created_at(run) < core._pr_created_at(pr):
            continue
        if snapshot._triggering_pr_number(repo, run) != number:
            continue
        job = core.request_data(f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}", token)
        if not isinstance(job, dict):
            raise RuntimeError("GitHub returned malformed protected MONDE Gate job")
        if (
            job.get("id") != job_id
            or job.get("run_id") != run_id
            or job.get("run_attempt") != run.get("run_attempt")
            or job.get("name") != core.REQUIRED_GATE_JOB_NAME
            or job.get("head_sha") != identity[2]
            or job.get("status") != "completed"
            or not isinstance(job.get("conclusion"), str)
            or job.get("conclusion") not in core.TERMINAL_CONCLUSIONS
        ):
            raise RuntimeError("GitHub returned malformed protected MONDE Gate job")
        return run, check
    return None


def _latest_check_is_merge_acceptable(check: dict[str, Any] | None) -> bool:
    return bool(
        check is not None
        and check.get("status") == "completed"
        and check.get("conclusion") in core.MERGE_ACCEPTABLE_CONCLUSIONS
    )


def _wait_for_invalidation(repo: str, head: str, token: str, previous_check_id: int) -> bool:
    for attempt in range(MAX_POSTCONDITION_POLLS):
        check = core.latest_required_check(repo, head, token)
        if check is not None and check.get("id") != previous_check_id:
            if check.get("status") != "completed" or check.get("conclusion") not in core.MERGE_ACCEPTABLE_CONCLUSIONS:
                return True
            return False
        if attempt + 1 < MAX_POSTCONDITION_POLLS:
            time.sleep(POSTCONDITION_POLL_SECONDS)
    raise RuntimeError("rerun did not publish a new required-check post-condition within the bounded observation window")


def _process_head_group(repo: str, token: str, group: list[dict[str, Any]]) -> tuple[list[int], list[str]]:
    head = core._pr_head_identity(group[0])[2]
    current_check = core.latest_required_check(repo, head, token)
    if not _latest_check_is_merge_acceptable(current_check):
        return [], []
    assert current_check is not None
    errors: list[str] = []
    for original in group:
        number = original["number"]
        if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM + STATE_WRITE_REQUEST_RESERVE:
            raise DeferredForBudget("insufficient request headroom before sibling evaluation")
        if not core.unresolved_review_threads(repo, number, token):
            continue
        target = _direct_target_for_pr(repo, token, original)
        if target is None:
            errors.append(f"open PR #{number} has unresolved threads but no bounded canonical rerun target")
            continue
        run, _target_check = target
        fresh = _current_pr(repo, token, original)
        if fresh is None:
            continue
        if not core.unresolved_review_threads(repo, number, token):
            continue
        latest = core.latest_required_check(repo, head, token)
        if not _latest_check_is_merge_acceptable(latest):
            return [], errors
        assert latest is not None
        if _remaining_request_budget() < MAX_POSTCONDITION_POLLS + STATE_WRITE_REQUEST_RESERVE + 1:
            raise DeferredForBudget("insufficient request headroom for rerun post-condition")
        core.rerun_workflow(repo, int(run["id"]), token)
        if _wait_for_invalidation(repo, head, token, int(latest["id"])):
            return [int(run["id"])], errors
        if core.unresolved_review_threads(repo, number, token):
            raise RuntimeError(
                f"rerun for unresolved PR #{number} completed merge-acceptable without invalidating shared head {head}"
            )
        current_check = core.latest_required_check(repo, head, token)
        if not _latest_check_is_merge_acceptable(current_check):
            return [int(run["id"])], errors
    return [], errors


def poll(repo: str, token: str) -> list[int]:
    cursor = _read_scheduler_cursor(repo, token)
    prs = snapshot.open_pull_requests(repo, token)
    groups = _head_groups_after_cursor(prs, cursor)
    rerun_ids: list[int] = []
    errors: list[str] = []
    last_cursor = cursor
    processed = 0
    for group in groups:
        if processed >= MAX_HEADS_PER_INVOCATION or len(rerun_ids) >= MAX_RERUNS_PER_INVOCATION:
            break
        if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM + STATE_WRITE_REQUEST_RESERVE:
            break
        processed += 1
        last_cursor = group[0]["number"]
        try:
            head_reruns, head_errors = _process_head_group(repo, token, group)
            rerun_ids.extend(head_reruns)
            errors.extend(head_errors)
        except DeferredForBudget:
            break
        except RuntimeError as exc:
            errors.append(f"head {core._pr_head_identity(group[0])[2]}: {exc}")
    if groups:
        _write_scheduler_cursor(repo, token, last_cursor)
    elif cursor != 0:
        _write_scheduler_cursor(repo, token, 0)
    if errors:
        raise RuntimeError("; ".join(errors))
    return rerun_ids


def validate_github_contract(repo: str, pr_number: int, token: str) -> tuple[int, int, bool]:
    prs = snapshot.open_pull_requests(repo, token)
    current = [pr for pr in prs if pr["number"] == pr_number]
    if len(current) != 1:
        raise RuntimeError(f"expected exactly one open PR #{pr_number}, observed {len(current)}")
    pr = current[0]
    target = _direct_target_for_pr(repo, token, pr)
    if target is None:
        raise RuntimeError(f"no bounded canonical MONDE Gate target is bound to current open PR #{pr_number}")
    identity = core._pr_head_identity(pr)
    check = core.latest_required_check(repo, identity[2], token)
    if check is None:
        raise RuntimeError(f"no latest {core.REQUIRED_GATE_JOB_NAME!r} check exists for open PR #{pr_number} head")
    unresolved = core.unresolved_review_threads(repo, pr_number, token)
    return len(prs), 1, unresolved


def install() -> None:
    core.request_data = _budgeted_request_data
    core.open_pull_requests = snapshot.open_pull_requests
    core._closed_pr_history = snapshot.closed_pr_history
    core.poll = poll
    core.validate_github_contract = validate_github_contract


def main() -> int:
    _reset_request_budget()
    install()
    try:
        return core.main()
    finally:
        print(f"MONDE bootstrap GitHub request budget: {_request_count}/{MAX_GITHUB_REQUESTS_PER_INVOCATION}")


if __name__ == "__main__":
    raise SystemExit(main())
