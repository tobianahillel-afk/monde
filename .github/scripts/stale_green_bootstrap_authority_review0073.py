from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0072 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
MAX_GUARD_PRS_PER_INVOCATION = previous.MAX_GUARD_PRS_PER_INVOCATION
DRAFT_GUARD_REQUEST_RESERVE = previous.DRAFT_GUARD_REQUEST_RESERVE


def _strict_discovered_pr(
    repo: str,
    token: str,
    discovered: dict[str, Any],
) -> dict[str, Any] | None:
    expected_number = discovered.get("number")
    expected_node_id = discovered.get("node_id")
    if (
        not core._positive_int(expected_number)
        or not core._nonempty_string(expected_node_id)
    ):
        raise RuntimeError("validated discovery PR identity is malformed")

    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls/{expected_number}",
        token,
    )
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"GitHub returned malformed direct pull request #{expected_number}"
        )

    number = payload.get("number")
    node_id = payload.get("node_id")
    draft = payload.get("draft")
    state = payload.get("state")
    if (
        not core._positive_int(number)
        or number != expected_number
        or not core._nonempty_string(node_id)
        or node_id != expected_node_id
        or type(draft) is not bool
        or state not in {"open", "closed"}
    ):
        raise RuntimeError(
            f"GitHub returned malformed direct pull request #{expected_number}"
        )

    if state == "closed":
        return None

    # Preserve the inherited exact open-PR authority validation for head/base/
    # merge identity after REVIEW-0073's closed-path identity checks.
    guardbase._guard_pr(payload)
    return payload


def _draft_guard_poll(repo: str, token: str) -> list[int]:
    state = pending._read_state(repo, token)
    if state.pending_pr:
        return pending._resume_pending(repo, token, state)

    page = discovery._read_discovery_page(repo, token, state.scan_page)
    membership = discovery._page_membership(page)
    discovery._validate_discovery_resume(state, membership)

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
        if base._remaining_request_budget() <= DRAFT_GUARD_REQUEST_RESERVE + 2:
            break

        item = discovery._page_item_for_number(page, number)
        current = _strict_discovered_pr(repo, token, item)
        processed += 1

        if current is not None:
            current_guard = guardbase._guard_pr(current)
            if not current_guard.draft and discovery._guard_one(repo, token, current):
                drafted.append(number)
        last_processed = number

    page_complete = bool(membership) and last_processed == membership[-1][0]
    if last_processed == state.scan_pr and pending_numbers:
        return drafted

    next_state = discovery._next_discovery_state(
        state,
        page,
        membership,
        last_processed,
        page_complete=page_complete,
    )
    if next_state != state:
        pending._write_state(repo, token, next_state)
    return drafted


def install() -> None:
    previous.install()
    base.poll = _draft_guard_poll
    core.poll = _draft_guard_poll
    base.validate_github_contract = discovery._validate_guard_contract
    core.validate_github_contract = discovery._validate_guard_contract


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
