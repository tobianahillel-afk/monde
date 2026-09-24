from __future__ import annotations

import json
import os
import sys
import urllib.error
from dataclasses import dataclass
from typing import Any, Literal

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0049 as pending
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0069 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
THREAD_SCAN_PAGE_LIMIT = 8
DRAFT_GUARD_REQUEST_RESERVE = THREAD_SCAN_PAGE_LIMIT * 2 + 7
MAX_GUARD_PRS_PER_INVOCATION = 32

ThreadState = Literal["RESOLVED", "UNRESOLVED", "AMBIGUOUS"]


@dataclass(frozen=True)
class GuardPr:
    number: int
    node_id: str
    draft: bool
    authority: tuple[Any, ...]


def _guard_pr(pr: dict[str, Any]) -> GuardPr:
    number = pr.get("number")
    node_id = pr.get("node_id")
    draft = pr.get("draft")
    if (
        not core._positive_int(number)
        or not core._nonempty_string(node_id)
        or type(draft) is not bool
        or pr.get("state") != "open"
    ):
        raise RuntimeError("GitHub returned malformed draft-guard pull request identity")
    return GuardPr(
        int(number),
        node_id,
        draft,
        base._pr_authority_fingerprint(pr),
    )


def _guard_snapshot(prs: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    seen: set[int] = set()
    rows: list[tuple[Any, ...]] = []
    for pr in prs:
        guard = _guard_pr(pr)
        if guard.number in seen:
            raise RuntimeError("GitHub returned duplicate draft-guard pull request identity")
        seen.add(guard.number)
        rows.append((guard.number, guard.node_id, guard.draft, *guard.authority))
    return tuple(sorted(rows))


def _read_open_prs(repo: str, token: str) -> list[dict[str, Any]]:
    return core.paged(
        f"https://api.github.com/repos/{repo}/pulls?state=open",
        token,
        unique_id_field="number",
    )


def _stable_guard_prs(repo: str, token: str) -> list[dict[str, Any]]:
    first = _read_open_prs(repo, token)
    second = _read_open_prs(repo, token)
    if _guard_snapshot(first) != _guard_snapshot(second):
        raise RuntimeError("GitHub returned unstable draft-guard pull request snapshot")
    return first


def _thread_state(repo: str, pr_number: int, token: str) -> ThreadState:
    owner, name = repo.split("/", 1)
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _page in range(1, THREAD_SCAN_PAGE_LIMIT + 1):
        # Keep enough headroom for a second bounded thread observation,
        # direct PR revalidation, GraphQL draft mutation, postcondition and
        # durable fairness-state write.
        if base._remaining_request_budget() <= DRAFT_GUARD_REQUEST_RESERVE:
            return "AMBIGUOUS"
        query = (
            "query($owner:String!,$name:String!,$number:Int!,$cursor:String){"
            "repository(owner:$owner,name:$name){pullRequest(number:$number){"
            "reviewThreads(first:100,after:$cursor){nodes{isResolved} "
            "pageInfo{hasNextPage endCursor}}}}}"
        )
        payload = {
            "query": query,
            "variables": {
                "owner": owner,
                "name": name,
                "number": pr_number,
                "cursor": cursor,
            },
        }
        try:
            result = core.request_data(
                "https://api.github.com/graphql",
                token,
                "POST",
                payload,
            )
        except (RuntimeError, urllib.error.URLError, json.JSONDecodeError):
            return "AMBIGUOUS"
        if not isinstance(result, dict) or (
            "errors" in result and result["errors"] != []
        ):
            return "AMBIGUOUS"
        try:
            page = result["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError, TypeError):
            return "AMBIGUOUS"
        if not isinstance(page, dict):
            return "AMBIGUOUS"
        nodes = page.get("nodes")
        info = page.get("pageInfo")
        if not isinstance(nodes, list) or any(
            not isinstance(node, dict)
            or type(node.get("isResolved")) is not bool
            for node in nodes
        ):
            return "AMBIGUOUS"
        if not isinstance(info, dict) or type(info.get("hasNextPage")) is not bool:
            return "AMBIGUOUS"
        if "endCursor" not in info or (
            info["endCursor"] is not None
            and not isinstance(info["endCursor"], str)
        ):
            return "AMBIGUOUS"
        if any(node["isResolved"] is False for node in nodes):
            return "UNRESOLVED"
        if not info["hasNextPage"]:
            return "RESOLVED"
        next_cursor = info["endCursor"]
        if not core._nonempty_string(next_cursor) or next_cursor in seen_cursors:
            return "AMBIGUOUS"
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    return "AMBIGUOUS"


def _direct_pr(repo: str, number: int, token: str) -> dict[str, Any] | None:
    payload = core.request_data(
        f"https://api.github.com/repos/{repo}/pulls/{number}",
        token,
    )
    if not isinstance(payload, dict) or payload.get("number") != number:
        raise RuntimeError(f"GitHub returned malformed direct pull request #{number}")
    state = payload.get("state")
    if state == "closed":
        return None
    if state != "open":
        raise RuntimeError(f"GitHub returned malformed direct pull request #{number} state")
    _guard_pr(payload)
    return payload


def _convert_to_draft(
    repo: str,
    token: str,
    current: dict[str, Any],
) -> None:
    guard = _guard_pr(current)
    if guard.draft:
        return
    query = (
        "mutation($id:ID!){convertPullRequestToDraft(input:{pullRequestId:$id}){"
        "pullRequest{id number isDraft headRefOid baseRefOid}}}"
    )
    payload = {
        "query": query,
        "variables": {"id": guard.node_id},
    }
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
    if (
        not isinstance(converted, dict)
        or converted.get("id") != guard.node_id
        or converted.get("number") != guard.number
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
    observed_guard = _guard_pr(observed)
    if observed_guard.node_id != guard.node_id or observed_guard.draft is not True:
        raise RuntimeError("GitHub did not durably expose the pull request as draft")


def _guard_one(
    repo: str,
    token: str,
    original: dict[str, Any],
) -> bool:
    guard = _guard_pr(original)
    if guard.draft:
        return False

    first_state = _thread_state(repo, guard.number, token)
    if first_state == "RESOLVED":
        return False

    current = _direct_pr(repo, guard.number, token)
    if current is None or _guard_pr(current).draft:
        return False

    second_state = _thread_state(repo, guard.number, token)
    if second_state == "RESOLVED":
        return False

    current = _direct_pr(repo, guard.number, token)
    if current is None or _guard_pr(current).draft:
        return False

    # Any unresolved or ambiguous thread state is unsafe. Converting this exact
    # current PR node to draft is idempotent and remains safe even if head/base
    # authority changed between the two observations.
    _convert_to_draft(repo, token, current)
    return True


def _ordered_after_cursor(
    prs: list[dict[str, Any]],
    cursor_pr: int,
) -> list[dict[str, Any]]:
    ordered = sorted(prs, key=lambda pr: int(pr["number"]))
    if not ordered:
        return []
    split = next(
        (index for index, pr in enumerate(ordered) if int(pr["number"]) > cursor_pr),
        0,
    )
    return ordered[split:] + ordered[:split]


def _draft_guard_poll(repo: str, token: str) -> list[int]:
    state = pending._read_state(repo, token)
    if state.pending_pr:
        # Preserve any pre-REVIEW-0070 durable rerun intent until it reaches
        # its terminal accounting path. Never overwrite pending authority.
        return pending._resume_pending(repo, token, state)

    prs = _stable_guard_prs(repo, token)
    ordered = _ordered_after_cursor(prs, state.cursor_pr)
    drafted: list[int] = []
    last_cursor = state.cursor_pr
    processed = 0

    for original in ordered:
        if processed >= MAX_GUARD_PRS_PER_INVOCATION:
            break
        if base._remaining_request_budget() <= DRAFT_GUARD_REQUEST_RESERVE + 1:
            break
        processed += 1
        number = int(original["number"])
        if _guard_one(repo, token, original):
            drafted.append(number)
        last_cursor = number

    if ordered:
        pending._write_state(repo, token, pending.SchedulerStateV4(last_cursor))
    elif state != pending.SchedulerStateV4(0):
        pending._write_state(repo, token, pending.SchedulerStateV4(0))
    return drafted


def _validate_guard_contract(
    repo: str,
    pr_number: int,
    token: str,
) -> tuple[int, int, bool]:
    prs = _stable_guard_prs(repo, token)
    current = [pr for pr in prs if pr.get("number") == pr_number]
    if len(current) != 1:
        raise RuntimeError(
            f"expected exactly one open PR #{pr_number}, observed {len(current)}"
        )
    guard = _guard_pr(current[0])
    # Validation mode is read-only: ambiguity is reported as unsafe but never
    # mutates the PR.
    state = _thread_state(repo, pr_number, token)
    return len(prs), 1, state != "RESOLVED" and not guard.draft


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
