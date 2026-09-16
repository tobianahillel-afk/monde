from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
from typing import Any, NamedTuple

import stale_green_bootstrap as core
import stale_green_bootstrap_pr_snapshot as snapshot

MAX_GITHUB_REQUESTS_PER_INVOCATION = 100
MAX_HEADS_PER_INVOCATION = 7
MAX_RERUNS_PER_INVOCATION = 3
TARGET_CHECK_PAGE_SIZE = 12
MAX_TARGET_PAGES_PER_INVOCATION = 2
MAX_POSTCONDITION_POLLS = 6
POSTCONDITION_POLL_SECONDS = 2.0
MIN_TARGET_REQUEST_HEADROOM = 40
STATE_WRITE_REQUEST_RESERVE = 1
SCHEDULER_STATE_TITLE = "MONDE stale-green scheduler state — machine managed"
SCHEDULER_STATE_MARKER = "MONDE_STALE_GREEN_SCHEDULER_V2"
LEGACY_SCHEDULER_STATE_MARKER = "MONDE_STALE_GREEN_SCHEDULER_V1"
_REUSABLE_WORKFLOW_PATH = ".github/workflows/_governance-core.yml"
_PULL_REF = re.compile(r"refs/pull/([1-9][0-9]*)/merge")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_request_count = 0
_ORIGINAL_REQUEST_DATA = snapshot._ORIGINAL_REQUEST_DATA


class DeferredForBudget(RuntimeError):
    pass


class SchedulerState(NamedTuple):
    cursor_pr: int
    scan_pr: int
    scan_page: int


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


def _validate_scheduler_state(state: SchedulerState) -> SchedulerState:
    if state.cursor_pr < 0 or state.scan_pr < 0 or state.scan_page < 1:
        raise RuntimeError("scheduler state values are outside their allowed range")
    if state.scan_pr == 0 and state.scan_page != 1:
        raise RuntimeError("idle scheduler state must restart target scanning at page 1")
    return state


def _scheduler_body(cursor_pr: int, scan_pr: int = 0, scan_page: int = 1) -> str:
    state = _validate_scheduler_state(SchedulerState(cursor_pr, scan_pr, scan_page))
    return (
        f"{SCHEDULER_STATE_MARKER}\n"
        f"cursor_pr: {state.cursor_pr}\n"
        f"scan_pr: {state.scan_pr}\n"
        f"scan_page: {state.scan_page}\n\n"
        "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
        "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
    )


def _parse_scheduler_state(issue: dict[str, Any], issue_number: int) -> SchedulerState:
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

    legacy = re.fullmatch(
        rf"{re.escape(LEGACY_SCHEDULER_STATE_MARKER)}\ncursor_pr: ([0-9]+)\n\n"
        r"Machine-managed durable cursor for the trusted default-branch stale-green bootstrap\. "
        r"Do not edit manually\. The scheduled bootstrap validates this exact marker before reading or updating the cursor\.",
        body,
    )
    if legacy is not None:
        return SchedulerState(int(legacy.group(1)), 0, 1)

    current = re.fullmatch(
        rf"{re.escape(SCHEDULER_STATE_MARKER)}\ncursor_pr: ([0-9]+)\n"
        r"scan_pr: ([0-9]+)\nscan_page: ([1-9][0-9]*)\n\n"
        r"Machine-managed durable cursor for the trusted default-branch stale-green bootstrap\. "
        r"Do not edit manually\. The scheduled bootstrap validates this exact marker before reading or updating the cursor\.",
        body,
    )
    if current is None:
        raise RuntimeError("scheduler state issue body does not match the closed-world cursor contract")
    return _validate_scheduler_state(
        SchedulerState(int(current.group(1)), int(current.group(2)), int(current.group(3)))
    )


def _parse_scheduler_cursor(issue: dict[str, Any], issue_number: int) -> int:
    return _parse_scheduler_state(issue, issue_number).cursor_pr


def _read_scheduler_state(repo: str, token: str) -> SchedulerState:
    issue_number = _scheduler_issue_number()
    issue = core.request_data(f"https://api.github.com/repos/{repo}/issues/{issue_number}", token)
    if not isinstance(issue, dict):
        raise RuntimeError("scheduler state issue response is malformed")
    return _parse_scheduler_state(issue, issue_number)


def _read_scheduler_cursor(repo: str, token: str) -> int:
    return _read_scheduler_state(repo, token).cursor_pr


def _write_scheduler_state(repo: str, token: str, state: SchedulerState) -> None:
    _validate_scheduler_state(state)
    issue_number = _scheduler_issue_number()
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        token,
        "PATCH",
        {"body": _scheduler_body(*state)},
    )
    if not isinstance(payload, dict) or _parse_scheduler_state(payload, issue_number) != state:
        raise RuntimeError("scheduler state issue update was not durably acknowledged")


def _write_scheduler_cursor(repo: str, token: str, cursor_pr: int) -> None:
    _write_scheduler_state(repo, token, SchedulerState(cursor_pr, 0, 1))


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


def _pr_base_identity(pr: dict[str, Any]) -> tuple[str, str, str]:
    base = pr.get("base")
    if not isinstance(base, dict):
        raise RuntimeError("GitHub returned malformed pull request base identity")
    repo = base.get("repo")
    ref = base.get("ref")
    sha = base.get("sha")
    if not isinstance(repo, dict) or not core._nonempty_string(repo.get("full_name")):
        raise RuntimeError("GitHub returned malformed pull request base repository")
    full_name = repo["full_name"]
    if full_name.count("/") != 1 or not all(full_name.split("/", 1)):
        raise RuntimeError("GitHub returned malformed pull request base repository")
    if not core._nonempty_string(ref) or not core._nonempty_string(sha) or _SHA40.fullmatch(sha) is None:
        raise RuntimeError("GitHub returned malformed pull request base ref/SHA")
    return full_name, ref, sha


def _pr_merge_sha(pr: dict[str, Any]) -> str | None:
    value = pr.get("merge_commit_sha")
    if value is None:
        return None
    if not core._nonempty_string(value) or _SHA40.fullmatch(value) is None:
        raise RuntimeError("GitHub returned malformed pull request merge_commit_sha")
    return value


def _pr_authority_fingerprint(pr: dict[str, Any]) -> tuple[Any, ...]:
    base = snapshot._pr_snapshot_fingerprint([pr], closed=False)[0]
    return (*base, *_pr_base_identity(pr), _pr_merge_sha(pr))


def _current_pr(repo: str, token: str, original: dict[str, Any]) -> dict[str, Any] | None:
    number = original["number"]
    payload = core.request_data(f"https://api.github.com/repos/{repo}/pulls/{number}", token)
    if not isinstance(payload, dict) or payload.get("number") != number:
        raise RuntimeError(f"GitHub returned malformed direct pull request #{number}")
    if payload.get("state") != "open":
        return None
    if _pr_authority_fingerprint(payload) != _pr_authority_fingerprint(original):
        return None
    return payload


def _validate_gate_check(check: dict[str, Any], head: str) -> tuple[int, int]:
    app = check.get("app")
    if (
        not core._positive_int(check.get("id"))
        or check.get("name") != core.REQUIRED_GATE_JOB_NAME
        or check.get("head_sha") != head
        or not isinstance(app, dict)
        or not core._positive_int(app.get("id"))
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


def _candidate_gate_check_page(
    repo: str,
    head: str,
    token: str,
    page: int,
) -> tuple[list[dict[str, Any]], bool]:
    if not core._positive_int(page):
        raise RuntimeError("target check page must be a positive integer")
    query = urllib.parse.urlencode(
        {
            "check_name": core.REQUIRED_GATE_JOB_NAME,
            "filter": "all",
            "app_id": core.GITHUB_ACTIONS_APP_ID,
            "per_page": TARGET_CHECK_PAGE_SIZE,
            "page": page,
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
    if len(checks) > TARGET_CHECK_PAGE_SIZE or len(checks) > total:
        raise RuntimeError("GitHub returned inconsistent MONDE Gate check history")
    offset = (page - 1) * TARGET_CHECK_PAGE_SIZE
    has_more = offset + len(checks) < total
    if has_more and len(checks) != TARGET_CHECK_PAGE_SIZE:
        raise RuntimeError("GitHub returned incomplete non-terminal MONDE Gate check page")
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
    return [item[2] for item in validated], has_more


def _triggering_pr_authority(repo: str, run: dict[str, Any]) -> tuple[int, str]:
    references = run.get("referenced_workflows")
    if not isinstance(references, list) or not references:
        raise RuntimeError("canonical MONDE Gate run lacks reusable-workflow PR authority")
    matches: list[tuple[int, str]] = []
    for reference in references:
        if not isinstance(reference, dict):
            raise RuntimeError("GitHub returned malformed referenced workflow metadata")
        path = reference.get("path")
        sha = reference.get("sha")
        ref = reference.get("ref")
        if not (
            core._nonempty_string(path)
            and core._nonempty_string(sha)
            and core._nonempty_string(ref)
            and _SHA40.fullmatch(sha)
        ):
            raise RuntimeError("GitHub returned malformed referenced workflow metadata")
        expected_path = f"{repo}/{_REUSABLE_WORKFLOW_PATH}@{sha}"
        if path != expected_path:
            continue
        match = _PULL_REF.fullmatch(ref)
        if match is None:
            raise RuntimeError("canonical reusable workflow lacks exact pull-request merge ref")
        matches.append((int(match.group(1)), sha))
    if len(matches) != 1:
        raise RuntimeError("canonical MONDE Gate run has ambiguous reusable-workflow PR authority")
    return matches[0]


def _validate_canonical_run(
    run: dict[str, Any],
    expected_run_id: int,
    head: str,
    *,
    require_completed: bool,
) -> int:
    run_id = run.get("id")
    workflow_id = run.get("workflow_id")
    attempt = run.get("run_attempt")
    event = run.get("event")
    status = run.get("status")
    conclusion = run.get("conclusion")
    if (
        not core._positive_int(run_id)
        or run_id != expected_run_id
        or not core._positive_int(workflow_id)
        or workflow_id != core.CANONICAL_WORKFLOW_ID
        or run.get("path") != core.CANONICAL_WORKFLOW_PATH
        or not core._nonempty_string(event)
        or event not in core.PR_FAMILY_EVENTS
        or not core._positive_int(attempt)
        or core._run_head_identity(run)[2] != head
    ):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
    if require_completed:
        if (
            status != "completed"
            or not isinstance(conclusion, str)
            or conclusion not in core.TERMINAL_CONCLUSIONS
        ):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
    else:
        if not core._nonempty_string(status):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        if status == "completed":
            if not isinstance(conclusion, str) or conclusion not in core.TERMINAL_CONCLUSIONS:
                raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        elif conclusion is not None:
            raise RuntimeError("GitHub returned incomplete canonical MONDE Gate run with a conclusion")
    return attempt


def _validate_protected_job(
    job: dict[str, Any],
    *,
    job_id: int,
    run_id: int,
    run_attempt: int,
    head: str,
) -> None:
    if (
        not core._positive_int(job.get("id"))
        or job.get("id") != job_id
        or not core._positive_int(job.get("run_id"))
        or job.get("run_id") != run_id
        or not core._positive_int(job.get("run_attempt"))
        or job.get("run_attempt") != run_attempt
        or job.get("name") != core.REQUIRED_GATE_JOB_NAME
        or job.get("head_sha") != head
        or job.get("status") != "completed"
        or not isinstance(job.get("conclusion"), str)
        or job.get("conclusion") not in core.TERMINAL_CONCLUSIONS
    ):
        raise RuntimeError("GitHub returned malformed protected MONDE Gate job")


def _direct_target_for_pr(
    repo: str,
    token: str,
    pr: dict[str, Any],
    start_page: int = 1,
) -> tuple[tuple[dict[str, Any], dict[str, Any]] | None, int | None]:
    if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM:
        raise DeferredForBudget("insufficient request headroom for bounded target validation and mutation")
    number = pr["number"]
    identity = core._pr_head_identity(pr)
    merge_sha = _pr_merge_sha(pr)
    if merge_sha is None:
        raise RuntimeError(f"open PR #{number} lacks a current merge-ref SHA")
    page = start_page
    for _ in range(MAX_TARGET_PAGES_PER_INVOCATION):
        if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM:
            raise DeferredForBudget("insufficient request headroom before target check page")
        checks, has_more = _candidate_gate_check_page(repo, identity[2], token, page)
        for check in checks:
            if _remaining_request_budget() <= STATE_WRITE_REQUEST_RESERVE + MAX_POSTCONDITION_POLLS + 6:
                raise DeferredForBudget("request headroom reached while validating bounded check candidates")
            run_id, job_id = _validate_gate_check(check, identity[2])
            run = core.request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
            if not isinstance(run, dict):
                raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
            run_attempt = _validate_canonical_run(run, run_id, identity[2], require_completed=True)
            if core._run_head_identity(run) != identity:
                continue
            if core._run_created_at(run) < core._pr_created_at(pr):
                continue
            if _triggering_pr_authority(repo, run) != (number, merge_sha):
                continue
            job = core.request_data(f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}", token)
            if not isinstance(job, dict):
                raise RuntimeError("GitHub returned malformed protected MONDE Gate job")
            _validate_protected_job(
                job,
                job_id=job_id,
                run_id=run_id,
                run_attempt=run_attempt,
                head=identity[2],
            )
            return (run, check), None
        if not has_more:
            return None, None
        page += 1
    return None, page


def _latest_check_is_merge_acceptable(check: dict[str, Any] | None) -> bool:
    return bool(
        check is not None
        and check.get("status") == "completed"
        and check.get("conclusion") in core.MERGE_ACCEPTABLE_CONCLUSIONS
    )


def _wait_for_terminal_invalidation(
    repo: str,
    head: str,
    token: str,
    run_id: int,
    previous_attempt: int,
    previous_check_id: int,
) -> bool:
    terminal_run: dict[str, Any] | None = None
    for poll_index in range(MAX_POSTCONDITION_POLLS):
        if terminal_run is None:
            run = core.request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
            if not isinstance(run, dict):
                raise RuntimeError("GitHub returned malformed rerun post-condition")
            attempt = _validate_canonical_run(run, run_id, head, require_completed=False)
            if attempt <= previous_attempt or run.get("status") != "completed":
                if poll_index + 1 < MAX_POSTCONDITION_POLLS:
                    time.sleep(POSTCONDITION_POLL_SECONDS)
                continue
            core.required_merge_gate_conclusion(repo, run, token)
            terminal_run = run

        latest = core.latest_required_check(repo, head, token)
        if latest is not None and latest.get("id") != previous_check_id:
            return not _latest_check_is_merge_acceptable(latest)
        if poll_index + 1 < MAX_POSTCONDITION_POLLS:
            time.sleep(POSTCONDITION_POLL_SECONDS)
    raise RuntimeError("rerun did not reach a terminal required-check post-condition within the bounded observation window")


def _ordered_group_for_scan(
    group: list[dict[str, Any]],
    scan_pr: int,
) -> list[dict[str, Any]]:
    ordered = sorted(group, key=lambda item: item["number"])
    if scan_pr == 0:
        return ordered
    selected = [pr for pr in ordered if pr["number"] == scan_pr]
    if not selected:
        return ordered
    return selected + [pr for pr in ordered if pr["number"] != scan_pr]


def _process_head_group(
    repo: str,
    token: str,
    group: list[dict[str, Any]],
    rerun_slots: int,
    scan_pr: int = 0,
    scan_page: int = 1,
) -> tuple[list[int], list[str], tuple[int, int] | None]:
    head = core._pr_head_identity(group[0])[2]
    current_check = core.latest_required_check(repo, head, token)
    if not _latest_check_is_merge_acceptable(current_check):
        return [], [], None
    assert current_check is not None
    errors: list[str] = []
    posted: list[int] = []
    for original in _ordered_group_for_scan(group, scan_pr):
        number = original["number"]
        if len(posted) >= rerun_slots:
            return posted, errors, None
        if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM + STATE_WRITE_REQUEST_RESERVE:
            raise DeferredForBudget("insufficient request headroom before sibling evaluation")
        if not core.unresolved_review_threads(repo, number, token):
            continue
        start_page = scan_page if number == scan_pr else 1
        target, next_page = _direct_target_for_pr(repo, token, original, start_page)
        if next_page is not None:
            return posted, errors, (number, next_page)
        if target is None:
            errors.append(f"open PR #{number} has unresolved threads but no canonical rerun target in complete check history")
            continue
        run, _target_check = target
        fresh = _current_pr(repo, token, original)
        if fresh is None:
            continue
        if not core.unresolved_review_threads(repo, number, token):
            continue
        latest = core.latest_required_check(repo, head, token)
        if not _latest_check_is_merge_acceptable(latest):
            return posted, errors, None
        assert latest is not None
        if len(posted) >= rerun_slots:
            return posted, errors, None
        if _remaining_request_budget() < MAX_POSTCONDITION_POLLS + STATE_WRITE_REQUEST_RESERVE + 3:
            raise DeferredForBudget("insufficient request headroom for rerun post-condition")
        run_id = int(run["id"])
        previous_attempt = int(run["run_attempt"])
        core.rerun_workflow(repo, run_id, token)
        posted.append(run_id)
        if _wait_for_terminal_invalidation(
            repo,
            head,
            token,
            run_id,
            previous_attempt,
            int(latest["id"]),
        ):
            return posted, errors, None
        if core.unresolved_review_threads(repo, number, token):
            raise RuntimeError(
                f"rerun for unresolved PR #{number} completed merge-acceptable without invalidating shared head {head}"
            )
        current_check = core.latest_required_check(repo, head, token)
        if not _latest_check_is_merge_acceptable(current_check):
            return posted, errors, None
    return posted, errors, None


def _group_for_scan(prs: list[dict[str, Any]], scan_pr: int) -> list[dict[str, Any]] | None:
    selected = next((pr for pr in prs if pr["number"] == scan_pr), None)
    if selected is None:
        return None
    head = core._pr_head_identity(selected)[2]
    return [pr for pr in prs if core._pr_head_identity(pr)[2] == head]


def poll(repo: str, token: str) -> list[int]:
    state = _read_scheduler_state(repo, token)
    prs = snapshot.open_pull_requests(repo, token)
    groups = _head_groups_after_cursor(prs, state.cursor_pr)
    if state.scan_pr:
        active = _group_for_scan(prs, state.scan_pr)
        if active is None:
            state = SchedulerState(state.cursor_pr, 0, 1)
        else:
            groups = [active] + [
                group
                for group in groups
                if core._pr_head_identity(group[0])[2] != core._pr_head_identity(active[0])[2]
            ]

    rerun_ids: list[int] = []
    errors: list[str] = []
    last_cursor = state.cursor_pr
    processed = 0
    active_scan_pr = state.scan_pr
    active_scan_page = state.scan_page

    for group in groups:
        if processed >= MAX_HEADS_PER_INVOCATION or len(rerun_ids) >= MAX_RERUNS_PER_INVOCATION:
            break
        if _remaining_request_budget() < MIN_TARGET_REQUEST_HEADROOM + STATE_WRITE_REQUEST_RESERVE:
            break
        processed += 1
        try:
            head_reruns, head_errors, continuation = _process_head_group(
                repo,
                token,
                group,
                MAX_RERUNS_PER_INVOCATION - len(rerun_ids),
                active_scan_pr,
                active_scan_page,
            )
            rerun_ids.extend(head_reruns)
            errors.extend(head_errors)
        except DeferredForBudget:
            break
        except RuntimeError as exc:
            errors.append(f"head {core._pr_head_identity(group[0])[2]}: {exc}")
            continuation = None

        if continuation is not None:
            next_state = SchedulerState(last_cursor, continuation[0], continuation[1])
            _write_scheduler_state(repo, token, next_state)
            if errors:
                raise RuntimeError("; ".join(errors))
            return rerun_ids

        last_cursor = min(pr["number"] for pr in group)
        active_scan_pr = 0
        active_scan_page = 1

    if groups:
        _write_scheduler_state(repo, token, SchedulerState(last_cursor, 0, 1))
    elif state != SchedulerState(0, 0, 1):
        _write_scheduler_state(repo, token, SchedulerState(0, 0, 1))
    if errors:
        raise RuntimeError("; ".join(errors))
    return rerun_ids


def validate_github_contract(repo: str, pr_number: int, token: str) -> tuple[int, int, bool]:
    prs = snapshot.open_pull_requests(repo, token)
    current = [pr for pr in prs if pr["number"] == pr_number]
    if len(current) != 1:
        raise RuntimeError(f"expected exactly one open PR #{pr_number}, observed {len(current)}")
    pr = current[0]
    target, next_page = _direct_target_for_pr(repo, token, pr)
    if target is None:
        if next_page is not None:
            raise RuntimeError(f"canonical MONDE Gate target scan for open PR #{pr_number} requires continuation")
        raise RuntimeError(f"no canonical MONDE Gate target is bound to current open PR #{pr_number}")
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