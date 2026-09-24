from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as previous


SCHEDULER_STATE_MARKER = "MONDE_STALE_GREEN_SCHEDULER_V4"
_PENDING_NONE = "-"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_STATE_TRAILER = (
    "Machine-managed durable cursor for the trusted default-branch stale-green bootstrap. "
    "Do not edit manually. The scheduled bootstrap validates this exact marker before reading or updating the cursor."
)
MUTATION_REQUEST_RESERVE = base.POSTCONDITION_REQUEST_RESERVE + 3


class PendingMutationObservation(RuntimeError):
    def __init__(self, run_id: int) -> None:
        super().__init__("pending rerun awaits a causally-bound terminal post-condition")
        self.run_id = run_id


class PendingMutationUncertain(RuntimeError):
    pass


@dataclass(frozen=True)
class SchedulerStateV4:
    cursor_pr: int
    scan_pr: int = 0
    scan_page: int = 1
    scan_anchor: str = "-"
    pending_pr: int = 0
    pending_authority: str = _PENDING_NONE
    pending_run_id: int = 0
    pending_baseline_attempt: int = 0
    pending_check_id: int = 0


def _nonnegative_exact_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _validate_state(state: SchedulerStateV4) -> SchedulerStateV4:
    if not (
        _nonnegative_exact_int(state.cursor_pr)
        and _nonnegative_exact_int(state.scan_pr)
        and type(state.scan_page) is int
        and state.scan_page >= 1
    ):
        raise RuntimeError("scheduler V4 state values are outside their allowed range")
    if not isinstance(state.scan_anchor, str) or (
        state.scan_anchor != "-" and _SHA256.fullmatch(state.scan_anchor) is None
    ):
        raise RuntimeError("scheduler V4 scan anchor is malformed")
    if state.scan_pr == 0 and (state.scan_page != 1 or state.scan_anchor != "-"):
        raise RuntimeError("idle scheduler V4 state must restart target scanning at page 1")

    pending_values = (
        state.pending_pr,
        state.pending_run_id,
        state.pending_baseline_attempt,
        state.pending_check_id,
    )
    if state.pending_pr == 0:
        if (
            state.pending_authority != _PENDING_NONE
            or any(value != 0 for value in pending_values[1:])
        ):
            raise RuntimeError("idle scheduler V4 state contains partial pending mutation data")
        return state

    if (
        not all(core._positive_int(value) for value in pending_values)
        or not isinstance(state.pending_authority, str)
        or _SHA256.fullmatch(state.pending_authority) is None
        or state.scan_pr != state.pending_pr
        or state.scan_page != 1
        or state.scan_anchor != "-"
    ):
        raise RuntimeError("pending scheduler V4 mutation identity is malformed")
    return state


def _authority_digest(pr: dict[str, Any]) -> str:
    material = base._pr_authority_fingerprint(pr)
    encoded = json.dumps(material, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _scheduler_body(state: SchedulerStateV4) -> str:
    state = _validate_state(state)
    return (
        f"{SCHEDULER_STATE_MARKER}\n"
        f"cursor_pr: {state.cursor_pr}\n"
        f"scan_pr: {state.scan_pr}\n"
        f"scan_page: {state.scan_page}\n"
        f"scan_anchor: {state.scan_anchor}\n"
        f"pending_pr: {state.pending_pr}\n"
        f"pending_authority: {state.pending_authority}\n"
        f"pending_run_id: {state.pending_run_id}\n"
        f"pending_baseline_attempt: {state.pending_baseline_attempt}\n"
        f"pending_check_id: {state.pending_check_id}\n\n"
        f"{_STATE_TRAILER}"
    )


def _validate_issue_identity(issue: dict[str, Any], issue_number: int) -> str:
    number = issue.get("number")
    if (
        not core._positive_int(number)
        or number != issue_number
        or issue.get("title") != base.SCHEDULER_STATE_TITLE
        or issue.get("state") != "open"
        or "pull_request" in issue
        or not isinstance(issue.get("body"), str)
    ):
        raise RuntimeError("scheduler state issue identity is malformed or no longer authoritative")
    return issue["body"]


def _parse_state(issue: dict[str, Any], issue_number: int) -> SchedulerStateV4:
    body = _validate_issue_identity(issue, issue_number)
    if not body.startswith(f"{SCHEDULER_STATE_MARKER}\n"):
        legacy = base._parse_scheduler_state(issue, issue_number)
        return _validate_state(
            SchedulerStateV4(
                legacy.cursor_pr,
                legacy.scan_pr,
                legacy.scan_page,
                legacy.scan_anchor,
            )
        )

    match = re.fullmatch(
        rf"{re.escape(SCHEDULER_STATE_MARKER)}\n"
        r"cursor_pr: ([0-9]+)\n"
        r"scan_pr: ([0-9]+)\n"
        r"scan_page: ([1-9][0-9]*)\n"
        r"scan_anchor: (-|[0-9a-f]{64})\n"
        r"pending_pr: ([0-9]+)\n"
        r"pending_authority: (-|[0-9a-f]{64})\n"
        r"pending_run_id: ([0-9]+)\n"
        r"pending_baseline_attempt: ([0-9]+)\n"
        r"pending_check_id: ([0-9]+)\n\n"
        + re.escape(_STATE_TRAILER),
        body,
    )
    if match is None:
        raise RuntimeError("scheduler state issue body does not match the V4 closed-world contract")
    return _validate_state(
        SchedulerStateV4(
            cursor_pr=int(match.group(1)),
            scan_pr=int(match.group(2)),
            scan_page=int(match.group(3)),
            scan_anchor=match.group(4),
            pending_pr=int(match.group(5)),
            pending_authority=match.group(6),
            pending_run_id=int(match.group(7)),
            pending_baseline_attempt=int(match.group(8)),
            pending_check_id=int(match.group(9)),
        )
    )


def _read_state(repo: str, token: str) -> SchedulerStateV4:
    issue_number = base._scheduler_issue_number()
    issue = core.request_data(f"https://api.github.com/repos/{repo}/issues/{issue_number}", token)
    if not isinstance(issue, dict):
        raise RuntimeError("scheduler state issue response is malformed")
    return _parse_state(issue, issue_number)


def _write_state(repo: str, token: str, state: SchedulerStateV4) -> None:
    state = _validate_state(state)
    issue_number = base._scheduler_issue_number()
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        token,
        "PATCH",
        {"body": _scheduler_body(state)},
    )
    if not isinstance(payload, dict) or _parse_state(payload, issue_number) != state:
        raise RuntimeError("scheduler V4 state update was not durably acknowledged")


def _clear_pending(
    state: SchedulerStateV4,
    *,
    cursor_pr: int | None = None,
    scan_pr: int = 0,
    scan_page: int = 1,
    scan_anchor: str = "-",
) -> SchedulerStateV4:
    return _validate_state(
        SchedulerStateV4(
            state.cursor_pr if cursor_pr is None else cursor_pr,
            scan_pr,
            scan_page,
            scan_anchor,
        )
    )


def _pending_state(
    state: SchedulerStateV4,
    pr: dict[str, Any],
    run_id: int,
    baseline_attempt: int,
    check_id: int,
) -> SchedulerStateV4:
    number = pr.get("number")
    if not (
        core._positive_int(number)
        and core._positive_int(run_id)
        and core._positive_int(baseline_attempt)
        and core._positive_int(check_id)
    ):
        raise RuntimeError("pending rerun mutation contains malformed identity")
    return _validate_state(
        SchedulerStateV4(
            cursor_pr=state.cursor_pr,
            scan_pr=number,
            scan_page=1,
            scan_anchor="-",
            pending_pr=number,
            pending_authority=_authority_digest(pr),
            pending_run_id=run_id,
            pending_baseline_attempt=baseline_attempt,
            pending_check_id=check_id,
        )
    )


def _current_pending_pr(
    repo: str,
    token: str,
    state: SchedulerStateV4,
) -> dict[str, Any] | None:
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls/{state.pending_pr}", token
    )
    if (
        not isinstance(payload, dict)
        or not core._positive_int(payload.get("number"))
        or payload["number"] != state.pending_pr
    ):
        raise RuntimeError("GitHub returned malformed pending pull-request authority")
    pr_state = payload.get("state")
    if pr_state not in {"open", "closed"}:
        raise RuntimeError("GitHub returned malformed pending pull-request state")
    if pr_state == "closed":
        return None
    if _authority_digest(payload) != state.pending_authority:
        raise RuntimeError("pending pull-request authority changed before mutation observation completed")
    return payload


def _resume_pending(repo: str, token: str, state: SchedulerStateV4) -> list[int]:
    state = _validate_state(state)
    if state.pending_pr == 0:
        raise RuntimeError("cannot resume an idle scheduler state")
    current = _current_pending_pr(repo, token, state)
    if current is None:
        _write_state(repo, token, _clear_pending(state))
        return []

    head = core._pr_head_identity(current)[2]
    run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{state.pending_run_id}", token
    )
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed pending workflow run")
    attempt = base._validate_canonical_run(
        run,
        state.pending_run_id,
        head,
        require_completed=False,
    )
    expected_attempt = state.pending_baseline_attempt + 1
    if attempt < state.pending_baseline_attempt:
        raise RuntimeError("pending workflow run attempt regressed below its mutation baseline")
    if attempt > expected_attempt:
        raise PendingMutationUncertain(
            "pending rerun advanced beyond the single expected attempt; refusing another mutation"
        )

    try:
        invalidated = previous._wait_for_terminal_invalidation(
            repo,
            head,
            token,
            state.pending_run_id,
            state.pending_baseline_attempt,
            state.pending_check_id,
            current,
            True,
        )
    except base.DeferredObservation:
        return []

    unresolved = core.unresolved_review_threads(repo, state.pending_pr, token)
    next_state = _clear_pending(state, scan_pr=state.pending_pr)
    _write_state(repo, token, next_state)
    if invalidated or not unresolved:
        return []
    return []


def _process_head_group(
    repo: str,
    token: str,
    group: list[dict[str, Any]],
    rerun_slots: int,
    state: SchedulerStateV4,
    scan_pr: int = 0,
    scan_page: int = 1,
    scan_anchor: str = "-",
) -> tuple[list[int], list[str], tuple[int, int] | None]:
    head = core._pr_head_identity(group[0])[2]
    current_check = core.latest_required_check(repo, head, token)
    if current_check is None:
        return [], [], None
    if current_check.get("status") != "completed":
        for original in base._ordered_group_for_scan(group, scan_pr):
            if core.unresolved_review_threads(repo, original["number"], token):
                return [], [], (original["number"], base.ScanPage(1))
        return [], [], None
    if not base._latest_check_is_merge_acceptable(current_check):
        return [], [], None

    errors: list[str] = []
    posted: list[int] = []
    for original in base._ordered_group_for_scan(group, scan_pr):
        number = original["number"]
        if len(posted) >= rerun_slots:
            return posted, errors, None
        if (
            base._remaining_request_budget()
            < base.MIN_TARGET_REQUEST_HEADROOM + base.STATE_WRITE_REQUEST_RESERVE
        ):
            raise base.DeferredForBudget(
                "insufficient request headroom before sibling evaluation"
            )
        if not core.unresolved_review_threads(repo, number, token):
            continue

        start_page = scan_page if number == scan_pr else 1
        if number == scan_pr and scan_anchor != "-":
            target, next_page = previous._direct_target_for_pr(
                repo, token, original, start_page, scan_anchor
            )
        else:
            target, next_page = previous._direct_target_for_pr(
                repo, token, original, start_page
            )
        if next_page is not None:
            return posted, errors, (number, next_page)
        if target is None:
            errors.append(
                f"open PR #{number} has unresolved threads but no canonical rerun target in complete check history"
            )
            continue

        run, _target_check = target
        fresh = base._current_pr(repo, token, original)
        if fresh is None:
            continue
        if not core.unresolved_review_threads(repo, number, token):
            continue
        latest = core.latest_required_check(repo, head, token)
        if not base._latest_check_is_merge_acceptable(latest):
            return posted, errors, None
        assert latest is not None
        mutation_fresh = base._current_pr(repo, token, original)
        if mutation_fresh is None:
            return posted, errors, (number, base.ScanPage(1))
        if base._remaining_request_budget() < MUTATION_REQUEST_RESERVE:
            raise base.DeferredForBudget(
                "insufficient request headroom for durable rerun mutation and observation"
            )

        run_id = int(run["id"])
        baseline_attempt = previous._mutation_baseline(
            repo, token, mutation_fresh, run_id
        )
        if baseline_attempt is None:
            return posted, errors, (number, base.ScanPage(1))

        final_pr = base._current_pr(repo, token, original)
        if final_pr is None:
            return posted, errors, (number, base.ScanPage(1))
        if not core.unresolved_review_threads(repo, number, token):
            continue

        pending = _pending_state(
            state,
            final_pr,
            run_id,
            baseline_attempt,
            int(latest["id"]),
        )
        _write_state(repo, token, pending)
        try:
            core.rerun_workflow(repo, run_id, token)
        except Exception as exc:
            raise PendingMutationUncertain(
                "rerun POST outcome is ambiguous; durable pending state retained and automatic retry forbidden"
            ) from exc
        posted.append(run_id)

        try:
            invalidated = previous._wait_for_terminal_invalidation(
                repo,
                head,
                token,
                run_id,
                baseline_attempt,
                int(latest["id"]),
                final_pr,
                True,
            )
        except base.DeferredObservation as exc:
            raise PendingMutationObservation(run_id) from exc

        unresolved = core.unresolved_review_threads(repo, number, token)
        cleared = _clear_pending(pending, scan_pr=number)
        _write_state(repo, token, cleared)
        if invalidated:
            return posted, errors, None
        if unresolved:
            return posted, errors, (number, base.ScanPage(1))
        current_check = core.latest_required_check(repo, head, token)
        if not base._latest_check_is_merge_acceptable(current_check):
            return posted, errors, None

    return posted, errors, None


def poll(repo: str, token: str) -> list[int]:
    state = _read_state(repo, token)
    if state.pending_pr:
        return _resume_pending(repo, token, state)

    prs = base.snapshot.open_pull_requests(repo, token)
    groups = base._head_groups_after_cursor(prs, state.cursor_pr)
    if state.scan_pr:
        active = base._group_for_scan(prs, state.scan_pr)
        if active is None:
            state = _clear_pending(state)
        else:
            groups = [active] + [
                group
                for group in groups
                if core._pr_head_identity(group[0])[2]
                != core._pr_head_identity(active[0])[2]
            ]

    rerun_ids: list[int] = []
    errors: list[str] = []
    last_cursor = state.cursor_pr
    processed = 0
    active_scan_pr = state.scan_pr
    active_scan_page = state.scan_page
    active_scan_anchor = state.scan_anchor

    for group in groups:
        if (
            processed >= base.MAX_HEADS_PER_INVOCATION
            or len(rerun_ids) >= base.MAX_RERUNS_PER_INVOCATION
        ):
            break
        if (
            base._remaining_request_budget()
            < base.MIN_TARGET_REQUEST_HEADROOM + base.STATE_WRITE_REQUEST_RESERVE
        ):
            break
        processed += 1
        working = SchedulerStateV4(
            last_cursor,
            active_scan_pr,
            active_scan_page,
            active_scan_anchor,
        )
        try:
            head_reruns, head_errors, continuation = _process_head_group(
                repo,
                token,
                group,
                base.MAX_RERUNS_PER_INVOCATION - len(rerun_ids),
                working,
                active_scan_pr,
                active_scan_page,
                active_scan_anchor,
            )
            rerun_ids.extend(head_reruns)
            errors.extend(head_errors)
        except PendingMutationObservation as exc:
            rerun_ids.append(exc.run_id)
            return rerun_ids
        except PendingMutationUncertain:
            raise
        except base.DeferredForBudget:
            break
        except RuntimeError as exc:
            errors.append(f"head {core._pr_head_identity(group[0])[2]}: {exc}")
            continuation = None

        if continuation is not None:
            continuation_page = continuation[1]
            anchor = getattr(continuation_page, "anchor", "-")
            _write_state(
                repo,
                token,
                SchedulerStateV4(
                    last_cursor,
                    continuation[0],
                    int(continuation_page),
                    anchor,
                ),
            )
            if errors:
                raise RuntimeError("; ".join(errors))
            return rerun_ids

        last_cursor = min(pr["number"] for pr in group)
        active_scan_pr = 0
        active_scan_page = 1
        active_scan_anchor = "-"

    if groups:
        _write_state(repo, token, SchedulerStateV4(last_cursor))
    elif state != SchedulerStateV4(0):
        _write_state(repo, token, SchedulerStateV4(0))
    if errors:
        raise RuntimeError("; ".join(errors))
    return rerun_ids


def install() -> None:
    previous.install()
    base.poll = poll
    core.poll = poll


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
