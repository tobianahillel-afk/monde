from __future__ import annotations

import os

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
MAX_GUARD_PRS_PER_INVOCATION = previous.MAX_GUARD_PRS_PER_INVOCATION
DRAFT_GUARD_REQUEST_RESERVE = guardbase.DRAFT_GUARD_REQUEST_RESERVE


def _draft_guard_poll(repo: str, token: str) -> list[int]:
    state = pending._read_state(repo, token)
    if state.pending_pr:
        return pending._resume_pending(repo, token, state)

    page = previous._read_discovery_page(repo, token, state.scan_page)
    membership = previous._page_membership(page)
    previous._validate_discovery_resume(state, membership)

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
        # REVIEW-0072 spends one request to re-read the exact current PR before
        # any skip decision. Keep that request plus the eventual durable state
        # write outside REVIEW-0070's bounded guard reserve.
        if base._remaining_request_budget() <= DRAFT_GUARD_REQUEST_RESERVE + 2:
            break

        previous._page_item_for_number(page, number)
        current = guardbase._direct_pr(repo, number, token)
        processed += 1

        # Page-level state/draft is discovery metadata only. Mutable authority
        # comes exclusively from the direct current-PR read above.
        if current is not None:
            current_guard = guardbase._guard_pr(current)
            if not current_guard.draft and previous._guard_one(repo, token, current):
                drafted.append(number)
        last_processed = number

    page_complete = bool(membership) and last_processed == membership[-1][0]
    if last_processed == state.scan_pr and pending_numbers:
        return drafted

    next_state = previous._next_discovery_state(
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
    base.validate_github_contract = previous._validate_guard_contract
    core.validate_github_contract = previous._validate_guard_contract


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
