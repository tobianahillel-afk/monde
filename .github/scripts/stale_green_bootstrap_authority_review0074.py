from __future__ import annotations

import os

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0073 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
MAX_GUARD_PRS_PER_INVOCATION = previous.MAX_GUARD_PRS_PER_INVOCATION
DRAFT_GUARD_REQUEST_RESERVE = previous.DRAFT_GUARD_REQUEST_RESERVE


def _identity_seed(current: dict) -> dict:
    guard = guardbase._guard_pr(current)
    return {"number": guard.number, "node_id": guard.node_id}


def _strict_guard_one(
    repo: str,
    token: str,
    original: dict,
) -> bool:
    guard = guardbase._guard_pr(original)
    if guard.draft:
        return False

    identity = {"number": guard.number, "node_id": guard.node_id}

    # Observation 1 intentionally never terminates a clean path. REVIEW-0074
    # preserves REVIEW-0071's resolved->unresolved race protection.
    guardbase._thread_state(repo, guard.number, token)

    current = previous._strict_discovered_pr(repo, token, identity)
    if current is None or guardbase._guard_pr(current).draft:
        return False

    second_state = guardbase._thread_state(repo, guard.number, token)
    if second_state == "RESOLVED":
        return False

    current = previous._strict_discovered_pr(repo, token, identity)
    if current is None or guardbase._guard_pr(current).draft:
        return False

    # REVIEW-0071 owns the exact integer ACK + REST postcondition contract.
    discovery._convert_to_draft(repo, token, current)
    return True


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
        current = previous._strict_discovered_pr(repo, token, item)
        processed += 1

        if current is not None:
            current_guard = guardbase._guard_pr(current)
            if not current_guard.draft and _strict_guard_one(repo, token, current):
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


def _strict_target_pr(
    repo: str,
    pr_number: int,
    token: str,
) -> dict:
    if not core._positive_int(pr_number):
        raise RuntimeError("target pull-request number is malformed")

    seed = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
        token,
    )
    if not isinstance(seed, dict):
        raise RuntimeError(f"GitHub returned malformed target pull request #{pr_number}")

    guard = guardbase._guard_pr(seed)
    if guard.number != pr_number:
        raise RuntimeError(f"GitHub returned malformed target pull request #{pr_number}")

    current = previous._strict_discovered_pr(
        repo,
        token,
        {"number": guard.number, "node_id": guard.node_id},
    )
    if current is None:
        raise RuntimeError(f"expected open PR #{pr_number}")
    return current


def _validate_guard_contract(
    repo: str,
    pr_number: int,
    token: str,
) -> tuple[int, int, bool]:
    current = _strict_target_pr(repo, pr_number, token)
    guard = guardbase._guard_pr(current)
    state = guardbase._thread_state(repo, guard.number, token)
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
