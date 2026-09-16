from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0048 as observation
import stale_green_bootstrap_authority_review0049 as previous


SCHEDULER_STATE_MARKER = "MONDE_STALE_GREEN_SCHEDULER_V5"
_PENDING_NONE = "-"
_STATE_TRAILER = previous._STATE_TRAILER
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class SchedulerStateV5:
    cursor_pr: int
    scan_pr: int = 0
    scan_page: int = 1
    scan_anchor: str = "-"
    pending_pr: int = 0
    pending_authority: str = _PENDING_NONE
    pending_head: str = _PENDING_NONE
    pending_run_id: int = 0
    pending_baseline_attempt: int = 0
    pending_check_id: int = 0


def _validate_state(state: SchedulerStateV5) -> SchedulerStateV5:
    if not (
        previous._nonnegative_exact_int(state.cursor_pr)
        and previous._nonnegative_exact_int(state.scan_pr)
        and type(state.scan_page) is int
        and state.scan_page >= 1
    ):
        raise RuntimeError("scheduler V5 state values are outside their allowed range")
    if not isinstance(state.scan_anchor, str) or (
        state.scan_anchor != "-" and _SHA256.fullmatch(state.scan_anchor) is None
    ):
        raise RuntimeError("scheduler V5 scan anchor is malformed")
    if state.scan_pr == 0 and (state.scan_page != 1 or state.scan_anchor != "-"):
        raise RuntimeError("idle scheduler V5 state must restart target scanning at page 1")

    pending_values = (
        state.pending_pr,
        state.pending_run_id,
        state.pending_baseline_attempt,
        state.pending_check_id,
    )
    if state.pending_pr == 0:
        if (
            state.pending_authority != _PENDING_NONE
            or state.pending_head != _PENDING_NONE
            or any(value != 0 for value in pending_values[1:])
        ):
            raise RuntimeError("idle scheduler V5 state contains partial pending mutation data")
        return state

    if (
        not all(core._positive_int(value) for value in pending_values)
        or not isinstance(state.pending_authority, str)
        or _SHA256.fullmatch(state.pending_authority) is None
        or not isinstance(state.pending_head, str)
        or base._SHA40.fullmatch(state.pending_head) is None
        or state.scan_pr != state.pending_pr
        or state.scan_page != 1
        or state.scan_anchor != "-"
    ):
        raise RuntimeError("pending scheduler V5 mutation identity is malformed")
    return state


def _coerce_state(state: Any) -> SchedulerStateV5:
    if isinstance(state, SchedulerStateV5):
        return _validate_state(state)
    try:
        pending_pr = state.pending_pr
        cursor_pr = state.cursor_pr
        scan_pr = state.scan_pr
        scan_page = state.scan_page
        scan_anchor = state.scan_anchor
    except AttributeError as exc:
        raise RuntimeError("scheduler state cannot be coerced into V5") from exc
    if pending_pr:
        raise RuntimeError("active pre-V5 pending mutation lacks reversible pending head authority")
    return _validate_state(
        SchedulerStateV5(cursor_pr, scan_pr, scan_page, scan_anchor)
    )


def _scheduler_body(state: SchedulerStateV5) -> str:
    state = _validate_state(state)
    return (
        f"{SCHEDULER_STATE_MARKER}\n"
        f"cursor_pr: {state.cursor_pr}\n"
        f"scan_pr: {state.scan_pr}\n"
        f"scan_page: {state.scan_page}\n"
        f"scan_anchor: {state.scan_anchor}\n"
        f"pending_pr: {state.pending_pr}\n"
        f"pending_authority: {state.pending_authority}\n"
        f"pending_head: {state.pending_head}\n"
        f"pending_run_id: {state.pending_run_id}\n"
        f"pending_baseline_attempt: {state.pending_baseline_attempt}\n"
        f"pending_check_id: {state.pending_check_id}\n\n"
        f"{_STATE_TRAILER}"
    )


def _parse_state(issue: dict[str, Any], issue_number: int) -> SchedulerStateV5:
    body = previous._validate_issue_identity(issue, issue_number)
    if not body.startswith(f"{SCHEDULER_STATE_MARKER}\n"):
        return _coerce_state(previous._parse_state(issue, issue_number))

    match = re.fullmatch(
        rf"{re.escape(SCHEDULER_STATE_MARKER)}\n"
        r"cursor_pr: ([0-9]+)\n"
        r"scan_pr: ([0-9]+)\n"
        r"scan_page: ([1-9][0-9]*)\n"
        r"scan_anchor: (-|[0-9a-f]{64})\n"
        r"pending_pr: ([0-9]+)\n"
        r"pending_authority: (-|[0-9a-f]{64})\n"
        r"pending_head: (-|[0-9a-f]{40})\n"
        r"pending_run_id: ([0-9]+)\n"
        r"pending_baseline_attempt: ([0-9]+)\n"
        r"pending_check_id: ([0-9]+)\n\n"
        + re.escape(_STATE_TRAILER),
        body,
    )
    if match is None:
        raise RuntimeError("scheduler state issue body does not match the V5 closed-world contract")
    return _validate_state(
        SchedulerStateV5(
            cursor_pr=int(match.group(1)),
            scan_pr=int(match.group(2)),
            scan_page=int(match.group(3)),
            scan_anchor=match.group(4),
            pending_pr=int(match.group(5)),
            pending_authority=match.group(6),
            pending_head=match.group(7),
            pending_run_id=int(match.group(8)),
            pending_baseline_attempt=int(match.group(9)),
            pending_check_id=int(match.group(10)),
        )
    )


def _read_state(repo: str, token: str) -> SchedulerStateV5:
    issue_number = base._scheduler_issue_number()
    issue = core.request_data(f"https://api.github.com/repos/{repo}/issues/{issue_number}", token)
    if not isinstance(issue, dict):
        raise RuntimeError("scheduler state issue response is malformed")
    return _parse_state(issue, issue_number)


def _write_state(repo: str, token: str, state: Any) -> None:
    current = _coerce_state(state)
    issue_number = base._scheduler_issue_number()
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/issues/{issue_number}",
        token,
        "PATCH",
        {"body": _scheduler_body(current)},
    )
    if not isinstance(payload, dict) or _parse_state(payload, issue_number) != current:
        raise RuntimeError("scheduler V5 state update was not durably acknowledged")


def _clear_pending(
    state: Any,
    *,
    cursor_pr: int | None = None,
    scan_pr: int = 0,
    scan_page: int = 1,
    scan_anchor: str = "-",
) -> SchedulerStateV5:
    current = _coerce_state(state) if not getattr(state, "pending_pr", 0) else state
    return _validate_state(
        SchedulerStateV5(
            current.cursor_pr if cursor_pr is None else cursor_pr,
            scan_pr,
            scan_page,
            scan_anchor,
        )
    )


def _pending_state(
    state: Any,
    pr: dict[str, Any],
    run_id: int,
    baseline_attempt: int,
    check_id: int,
) -> SchedulerStateV5:
    current = _coerce_state(state)
    number = pr.get("number")
    head = core._pr_head_identity(pr)[2]
    if not (
        core._positive_int(number)
        and core._positive_int(run_id)
        and core._positive_int(baseline_attempt)
        and core._positive_int(check_id)
        and base._SHA40.fullmatch(head) is not None
    ):
        raise RuntimeError("pending rerun mutation contains malformed reversible identity")
    return _validate_state(
        SchedulerStateV5(
            cursor_pr=current.cursor_pr,
            scan_pr=number,
            pending_pr=number,
            pending_authority=previous._authority_digest(pr),
            pending_head=head,
            pending_run_id=run_id,
            pending_baseline_attempt=baseline_attempt,
            pending_check_id=check_id,
        )
    )


def _pending_origin_pr(repo: str, token: str, state: SchedulerStateV5) -> dict[str, Any]:
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
    if pr_state == "open" and (
        previous._authority_digest(payload) != state.pending_authority
        or core._pr_head_identity(payload)[2] != state.pending_head
    ):
        raise RuntimeError("pending pull-request authority changed before mutation observation completed")
    return payload


def _unresolved_same_head(repo: str, token: str, head: str) -> list[dict[str, Any]]:
    matches = [
        pr
        for pr in base.snapshot.open_pull_requests(repo, token)
        if core._pr_head_identity(pr)[2] == head
    ]
    unresolved = [
        pr
        for pr in sorted(matches, key=lambda item: item["number"])
        if core.unresolved_review_threads(repo, pr["number"], token)
    ]
    return unresolved


def _resume_pending(repo: str, token: str, state: SchedulerStateV5) -> list[int]:
    state = _validate_state(state)
    if state.pending_pr == 0:
        raise RuntimeError("cannot resume an idle scheduler state")
    origin = _pending_origin_pr(repo, token, state)

    run = core.request_data(
        f"https://api.github.com/repos/{repo}/actions/runs/{state.pending_run_id}", token
    )
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed pending workflow run")
    attempt = base._validate_canonical_run(
        run,
        state.pending_run_id,
        state.pending_head,
        require_completed=False,
    )
    expected_attempt = state.pending_baseline_attempt + 1
    if attempt < state.pending_baseline_attempt:
        raise RuntimeError("pending workflow run attempt regressed below its mutation baseline")
    if attempt > expected_attempt:
        raise previous.PendingMutationUncertain(
            "pending rerun advanced beyond the single expected attempt; refusing another mutation"
        )

    original_pr = origin if origin["state"] == "open" else None
    try:
        invalidated = observation._wait_for_terminal_invalidation(
            repo,
            state.pending_head,
            token,
            state.pending_run_id,
            state.pending_baseline_attempt,
            state.pending_check_id,
            original_pr,
            True,
        )
    except base.DeferredObservation:
        return []

    if invalidated:
        _write_state(repo, token, _clear_pending(state))
        return []

    unresolved = _unresolved_same_head(repo, token, state.pending_head)
    if unresolved:
        _write_state(
            repo,
            token,
            _clear_pending(state, scan_pr=unresolved[0]["number"]),
        )
        return []

    _write_state(repo, token, _clear_pending(state))
    return []


def install() -> None:
    previous.install()
    previous._read_state = _read_state
    previous._write_state = _write_state
    previous._clear_pending = _clear_pending
    previous._pending_state = _pending_state
    previous._resume_pending = _resume_pending
    base.poll = previous.poll
    core.poll = previous.poll


def main() -> int:
    install()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
