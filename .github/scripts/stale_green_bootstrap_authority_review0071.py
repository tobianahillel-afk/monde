from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
DISCOVERY_PAGE_SIZE = 100
MAX_GUARD_PRS_PER_INVOCATION = previous.MAX_GUARD_PRS_PER_INVOCATION


def _page_membership(page: Any) -> tuple[tuple[int, str], ...]:
    if not isinstance(page, list) or len(page) > DISCOVERY_PAGE_SIZE:
        raise RuntimeError("GitHub returned malformed bounded PR discovery page")
    rows: list[tuple[int, str]] = []
    seen: set[int] = set()
    previous_number = 0
    for item in page:
        if not isinstance(item, dict):
            raise RuntimeError("GitHub returned malformed bounded PR discovery page")
        number = item.get("number")
        node_id = item.get("node_id")
        if (
            not core._positive_int(number)
            or not core._nonempty_string(node_id)
            or number in seen
            or number <= previous_number
        ):
            raise RuntimeError("GitHub returned malformed bounded PR discovery identity/order")
        state = item.get("state")
        draft = item.get("draft")
        if state not in {"open", "closed"} or type(draft) is not bool:
            raise RuntimeError("GitHub returned malformed bounded PR discovery state")
        seen.add(number)
        previous_number = number
        rows.append((number, node_id))
    return tuple(rows)


def _prefix_digest(
    membership: tuple[tuple[int, str], ...],
    scan_pr: int,
) -> str:
    prefix = [row for row in membership if row[0] <= scan_pr]
    if not prefix or prefix[-1][0] != scan_pr:
        raise RuntimeError("durable PR discovery cursor is no longer present in its page prefix")
    material = json.dumps(prefix, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _read_discovery_page(
    repo: str,
    token: str,
    page_number: int,
) -> list[dict[str, Any]]:
    if type(page_number) is not int or page_number < 1:
        raise RuntimeError("bounded PR discovery page number is invalid")
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls"
        f"?state=all&sort=created&direction=asc&per_page={DISCOVERY_PAGE_SIZE}"
        f"&page={page_number}",
        token,
    )
    _page_membership(payload)
    return payload


def _validate_discovery_resume(
    state: pending.SchedulerStateV4,
    membership: tuple[tuple[int, str], ...],
) -> None:
    if state.scan_anchor == "-":
        if state.scan_pr and membership and membership[0][0] <= state.scan_pr:
            raise RuntimeError("bounded PR discovery page overlaps its durable predecessor")
        return
    observed = _prefix_digest(membership, state.scan_pr)
    if observed != state.scan_anchor:
        raise RuntimeError("bounded PR discovery page prefix drifted since durable checkpoint")


def _page_item_for_number(
    page: list[dict[str, Any]],
    number: int,
) -> dict[str, Any]:
    matches = [item for item in page if item.get("number") == number]
    if len(matches) != 1:
        raise RuntimeError("bounded PR discovery page lost exact PR identity")
    return matches[0]


def _convert_to_draft(
    repo: str,
    token: str,
    current: dict[str, Any],
) -> None:
    guard = previous._guard_pr(current)
    if guard.draft:
        return
    query = (
        "mutation($id:ID!){convertPullRequestToDraft(input:{pullRequestId:$id}){"
        "pullRequest{id number isDraft headRefOid baseRefOid}}}"
    )
    payload = {"query": query, "variables": {"id": guard.node_id}}
    result = core.request_data(
        "https://api.github.com/graphql",
        token,
        "POST",
        payload,
    )
    if not isinstance(result, dict) or (
        "errors" in result and result["errors"] != []
    ):
        raise RuntimeError("GitHub draft conversion returned malformed GraphQL response")
    try:
        converted = result["data"]["convertPullRequestToDraft"]["pullRequest"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "GitHub draft conversion returned malformed GraphQL response"
        ) from exc
    acknowledged_number = converted.get("number") if isinstance(converted, dict) else None
    if (
        not isinstance(converted, dict)
        or converted.get("id") != guard.node_id
        or not core._positive_int(acknowledged_number)
        or acknowledged_number != guard.number
        or converted.get("isDraft") is not True
    ):
        raise RuntimeError("GitHub draft conversion acknowledgement is not exact")

    observed = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls/{guard.number}",
        token,
    )
    if not isinstance(observed, dict) or observed.get("number") != guard.number:
        raise RuntimeError("GitHub draft conversion postcondition is malformed")
    if observed.get("state") == "closed":
        return
    observed_guard = previous._guard_pr(observed)
    if observed_guard.node_id != guard.node_id or observed_guard.draft is not True:
        raise RuntimeError("GitHub did not durably expose the pull request as draft")


def _guard_one(
    repo: str,
    token: str,
    original: dict[str, Any],
) -> bool:
    guard = previous._guard_pr(original)
    if guard.draft:
        return False

    # REVIEW-0071 intentionally performs both observations even when the first
    # one is RESOLVED. A newly unresolved thread between the observations must
    # not be skipped merely because the first read was clean.
    previous._thread_state(repo, guard.number, token)

    current = previous._direct_pr(repo, guard.number, token)
    if current is None or previous._guard_pr(current).draft:
        return False

    second_state = previous._thread_state(repo, guard.number, token)
    if second_state == "RESOLVED":
        return False

    current = previous._direct_pr(repo, guard.number, token)
    if current is None or previous._guard_pr(current).draft:
        return False

    _convert_to_draft(repo, token, current)
    return True


def _next_discovery_state(
    state: pending.SchedulerStateV4,
    page: list[dict[str, Any]],
    membership: tuple[tuple[int, str], ...],
    last_processed: int,
    *,
    page_complete: bool,
) -> pending.SchedulerStateV4:
    cursor = last_processed if last_processed > 0 else state.cursor_pr
    if page_complete and len(page) < DISCOVERY_PAGE_SIZE:
        return pending.SchedulerStateV4(cursor)
    if page_complete:
        return pending.SchedulerStateV4(
            cursor_pr=cursor,
            scan_pr=last_processed,
            scan_page=state.scan_page + 1,
            scan_anchor="-",
        )
    return pending.SchedulerStateV4(
        cursor_pr=cursor,
        scan_pr=last_processed,
        scan_page=state.scan_page,
        scan_anchor=_prefix_digest(membership, last_processed),
    )


def _draft_guard_poll(repo: str, token: str) -> list[int]:
    state = pending._read_state(repo, token)
    if state.pending_pr:
        # Legacy REVIEW-0049+ durable pending authority remains higher priority
        # than new draft scanning. Scheduled permissions retain Actions/Checks
        # read access solely so this path can reach terminal accounting.
        return pending._resume_pending(repo, token, state)

    page = _read_discovery_page(repo, token, state.scan_page)
    membership = _page_membership(page)
    _validate_discovery_resume(state, membership)

    if not page:
        idle = pending.SchedulerStateV4(state.cursor_pr)
        if state != idle:
            pending._write_state(repo, token, idle)
        return []

    pending_numbers = [number for number, _node in membership if number > state.scan_pr]
    drafted: list[int] = []
    last_processed = state.scan_pr
    processed = 0

    for number in pending_numbers:
        if processed >= MAX_GUARD_PRS_PER_INVOCATION:
            break
        if base._remaining_request_budget() <= previous.DRAFT_GUARD_REQUEST_RESERVE + 1:
            break
        item = _page_item_for_number(page, number)
        processed += 1

        # state=all creates append-only page membership. Mutable open/draft
        # state is only an optimization: every open ready entry is directly
        # revalidated again inside _guard_one before any mutation.
        if item["state"] == "open" and item["draft"] is False:
            if _guard_one(repo, token, item):
                drafted.append(number)
        last_processed = number

    page_complete = bool(membership) and last_processed == membership[-1][0]
    if last_processed == state.scan_pr and pending_numbers:
        # No record could be processed with the remaining budget. Preserve the
        # current durable checkpoint rather than falsely advancing.
        return drafted

    next_state = _next_discovery_state(
        state,
        page,
        membership,
        last_processed,
        page_complete=page_complete,
    )
    if next_state != state:
        pending._write_state(repo, token, next_state)
    return drafted


def _validate_guard_contract(
    repo: str,
    pr_number: int,
    token: str,
) -> tuple[int, int, bool]:
    # Read-only validation does not enumerate the repository. It validates the
    # exact target PR and bounded thread contract directly.
    current = previous._direct_pr(repo, pr_number, token)
    if current is None:
        raise RuntimeError(f"expected open PR #{pr_number}")
    guard = previous._guard_pr(current)
    state = previous._thread_state(repo, pr_number, token)
    return 1, 1, state != "RESOLVED" and not guard.draft


def install() -> None:
    previous.install()
    base.poll = _draft_guard_poll
    core.poll = _draft_guard_poll
    base.validate_github_contract = _validate_guard_contract
    core.validate_github_contract = _validate_guard_contract


def main() -> int:
    install()
    action = os.getenv("BOOTSTRAP_RECOVERY_ACTION", "").strip()
    if action:
        if action != RECOVERY_ACTION:
            raise RuntimeError(f"unsupported bootstrap recovery action: {action}")
        repo = os.getenv("GITHUB_REPOSITORY", "")
        token = os.getenv("GITHUB_TOKEN", "")
        if not repo or not token:
            raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
        return recovery._inspect_confirmed_unposted(repo, token)
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
