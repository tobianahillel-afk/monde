from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import stale_green_bootstrap as core

MAX_GITHUB_REQUESTS_PER_INVOCATION = 60
MAX_HEADS_PER_INVOCATION = 7
MAX_RERUNS_PER_INVOCATION = 3
FAIRNESS_SLOT_SECONDS = 600
_ORIGINAL_REQUEST_DATA = core.request_data
_ORIGINAL_CLOSED_PR_HISTORY = core._closed_pr_history
_REUSABLE_WORKFLOW_PATH = ".github/workflows/_governance-core.yml"
_PULL_REF = re.compile(r"refs/pull/([1-9][0-9]*)/merge")
_SHA40 = re.compile(r"[0-9a-f]{40}")
_request_count = 0


def _reset_request_budget() -> None:
    global _request_count
    _request_count = 0


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


def _pr_snapshot_fingerprint(
    pull_requests: list[dict[str, Any]],
    *,
    closed: bool,
) -> tuple[tuple[Any, ...], ...]:
    expected_state = "closed" if closed else "open"
    seen_numbers: set[int] = set()
    fingerprint: list[tuple[Any, ...]] = []
    for pr in pull_requests:
        number = pr.get("number")
        if not core._positive_int(number):
            raise RuntimeError("GitHub returned malformed pull request identity in stable snapshot")
        if number in seen_numbers:
            raise RuntimeError("GitHub returned duplicate pull request identity in stable snapshot")
        seen_numbers.add(number)
        if pr.get("state") != expected_state:
            raise RuntimeError(f"GitHub returned malformed {expected_state} pull request state in stable snapshot")
        identity = core._pr_head_identity(pr)
        created = core._pr_created_at(pr)
        fields: list[Any] = [number, expected_state, *identity, created.isoformat()]
        if closed:
            closed_at = core._closed_pr_at(pr)
            updated = core._pr_updated_at(pr)
            if closed_at < created or updated < closed_at:
                raise RuntimeError("GitHub returned closed pull request with invalid lifetime in stable snapshot")
            fields.extend((closed_at.isoformat(), updated.isoformat()))
        fingerprint.append(tuple(fields))
    return tuple(sorted(fingerprint))


def _read_open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    return core.paged(
        f"https://api.github.com/repos/{repo}/pulls?state=open",
        token,
        unique_id_field="number",
    )


def open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    first = _read_open_pull_requests(repo, token)
    second = _read_open_pull_requests(repo, token)
    if _pr_snapshot_fingerprint(first, closed=False) != _pr_snapshot_fingerprint(second, closed=False):
        raise RuntimeError("GitHub returned unstable open pull request snapshot")
    return first


def closed_pr_history(
    repo: str,
    token: str,
    owner: str,
    branch: str,
    cutoff: Any,
) -> list[dict[str, Any]]:
    first = _ORIGINAL_CLOSED_PR_HISTORY(repo, token, owner, branch, cutoff)
    second = _ORIGINAL_CLOSED_PR_HISTORY(repo, token, owner, branch, cutoff)
    if _pr_snapshot_fingerprint(first, closed=True) != _pr_snapshot_fingerprint(second, closed=True):
        raise RuntimeError("GitHub returned unstable bounded closed pull request snapshot")
    return first


def _triggering_pr_number(repo: str, run: dict[str, Any]) -> int:
    references = run.get("referenced_workflows")
    if not isinstance(references, list) or not references:
        raise RuntimeError("canonical MONDE Gate run lacks reusable-workflow PR authority")
    matches: list[int] = []
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
        matches.append(int(match.group(1)))
    if len(matches) != 1:
        raise RuntimeError("canonical MONDE Gate run has ambiguous reusable-workflow PR authority")
    return matches[0]


def _active_representatives(prs_by_number: dict[int, dict[str, Any]]) -> dict[core.HeadIdentity, dict[str, Any]]:
    ordered = sorted(prs_by_number.values(), key=core._pr_created_at, reverse=True)
    return {core._pr_head_identity(pr): pr for pr in ordered}


def _latest_runs_by_pr(
    repo: str,
    token: str,
    prs_by_number: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    if not prs_by_number:
        return {}
    runs = core._scoped_completed_gate_runs(repo, token, _active_representatives(prs_by_number))
    latest: dict[int, dict[str, Any]] = {}
    for run in runs:
        workflow_id = run.get("workflow_id")
        path = run.get("path")
        event = run.get("event")
        if (
            not core._positive_int(workflow_id)
            or workflow_id != core.CANONICAL_WORKFLOW_ID
            or path != core.CANONICAL_WORKFLOW_PATH
        ):
            raise RuntimeError("canonical workflow endpoint returned mismatched workflow identity")
        if not core._nonempty_string(event):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate event")
        if event not in core.PR_FAMILY_EVENTS:
            continue
        run_number = run.get("run_number")
        run_id = run.get("id")
        status = run.get("status")
        conclusion = run.get("conclusion")
        if (
            not core._positive_int(run_number)
            or not core._positive_int(run_id)
            or status != "completed"
            or not isinstance(conclusion, str)
            or conclusion not in core.TERMINAL_CONCLUSIONS
        ):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate run")
        run_created = core._run_created_at(run)
        run_updated = core._updated_at(run.get("updated_at"))
        if run_updated < run_created:
            raise RuntimeError("GitHub returned canonical MONDE Gate run with invalid lifetime")
        pr_number = _triggering_pr_number(repo, run)
        pr = prs_by_number.get(pr_number)
        if pr is None:
            continue
        if core._run_head_identity(run) != core._pr_head_identity(pr):
            continue
        if run_created < core._pr_created_at(pr):
            continue
        previous = latest.get(pr_number)
        if previous is None or core._run_recency(run) > core._run_recency(previous):
            latest[pr_number] = run
    return latest


def _revalidate_stale_prs(
    stale_prs: list[dict[str, Any]],
    fresh_open_prs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fresh_by_number = {pr["number"]: pr for pr in fresh_open_prs}
    fresh: list[dict[str, Any]] = []
    for old in stale_prs:
        current = fresh_by_number.get(old["number"])
        if current is None:
            continue
        if _pr_snapshot_fingerprint([old], closed=False) != _pr_snapshot_fingerprint([current], closed=False):
            continue
        fresh.append(current)
    return fresh


def _fairness_slot() -> int:
    return int(datetime.now(timezone.utc).timestamp()) // FAIRNESS_SLOT_SECONDS


def _fair_head_groups(
    pull_requests: list[dict[str, Any]],
    slot: int,
) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for pr in sorted(pull_requests, key=lambda item: item["number"]):
        head = core._pr_head_identity(pr)[2]
        groups.setdefault(head, []).append(pr)
    ordered = sorted(groups.values(), key=lambda group: group[0]["number"])
    if not ordered:
        return []
    offset = slot % len(ordered)
    return ordered[offset:] + ordered[:offset]


def poll(repo: str, token: str) -> list[int]:
    prs = open_pull_requests(repo, token)
    rerun_ids: list[int] = []
    groups = _fair_head_groups(prs, _fairness_slot())[:MAX_HEADS_PER_INVOCATION]

    for group in groups:
        if len(rerun_ids) >= MAX_RERUNS_PER_INVOCATION:
            break

        head = core._pr_head_identity(group[0])[2]
        check = core.latest_required_check(repo, head, token)
        if (
            check is None
            or check["status"] != "completed"
            or check["conclusion"] not in core.MERGE_ACCEPTABLE_CONCLUSIONS
        ):
            continue

        fresh_group = _revalidate_stale_prs(group, open_pull_requests(repo, token))
        if not fresh_group:
            continue

        fresh_by_number = {pr["number"]: pr for pr in fresh_group}
        current_runs = _latest_runs_by_pr(repo, token, fresh_by_number)

        for current in sorted(fresh_group, key=lambda item: item["number"]):
            number = current["number"]
            target_run = current_runs.get(number)
            if target_run is None:
                if core.unresolved_review_threads(repo, number, token):
                    raise RuntimeError(
                        f"effective merge-acceptable MONDE Gate for head {head} has no unambiguous run "
                        f"bound to open PR #{number} current incarnation"
                    )
                continue

            core.required_merge_gate_conclusion(repo, target_run, token)
            if not core.unresolved_review_threads(repo, number, token):
                continue

            run_id = target_run["id"]
            core.rerun_workflow(repo, run_id, token)
            rerun_ids.append(run_id)
            break

    return rerun_ids


def validate_github_contract(repo: str, pr_number: int, token: str) -> tuple[int, int, bool]:
    prs = open_pull_requests(repo, token)
    current = [pr for pr in prs if pr["number"] == pr_number]
    if len(current) != 1:
        raise RuntimeError(f"expected exactly one open PR #{pr_number}, observed {len(current)}")
    current_by_number = {pr_number: current[0]}
    runs = _latest_runs_by_pr(repo, token, current_by_number)
    target = runs.get(pr_number)
    if target is None:
        raise RuntimeError(f"no unambiguous canonical MONDE Gate run is bound to current incarnation of open PR #{pr_number}")
    identity = core._pr_head_identity(current[0])
    check = core.latest_required_check(repo, identity[2], token)
    if check is None:
        raise RuntimeError(f"no latest {core.REQUIRED_GATE_JOB_NAME!r} check exists for open PR #{pr_number} head")
    core.required_merge_gate_conclusion(repo, target, token)
    unresolved = core.unresolved_review_threads(repo, pr_number, token)
    return len(prs), len(runs), unresolved


def install() -> None:
    core.request_data = _budgeted_request_data
    core.open_pull_requests = open_pull_requests
    core._closed_pr_history = closed_pr_history
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
