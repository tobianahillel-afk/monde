from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0070 as guardbase
import stale_green_bootstrap_authority_review0071 as discovery
import stale_green_bootstrap_authority_review0073 as strict
import stale_green_bootstrap_authority_review0074 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION


def _strict_convert_to_draft(
    repo: str,
    token: str,
    current: dict[str, Any],
) -> None:
    guard = guardbase._guard_pr(current)
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

    # REVIEW-0075 closes the REVIEW-0074 L2 postcondition gap by reusing the
    # already-proven strict current-PR identity primitive. A closed response is
    # accepted only after exact number, node_id, Boolean draft and closed-world
    # state validation; an open response must still be the exact same PR.
    observed = strict._strict_discovered_pr(
        repo,
        token,
        {"number": guard.number, "node_id": guard.node_id},
    )
    if observed is None:
        return

    observed_guard = guardbase._guard_pr(observed)
    if observed_guard.node_id != guard.node_id or observed_guard.draft is not True:
        raise RuntimeError("GitHub did not durably expose the pull request as draft")


def install() -> None:
    previous.install()
    # REVIEW-0074's strict guard resolves this shared module attribute at call
    # time, so replacing only the conversion primitive preserves its complete
    # double-observation and strict-reread architecture.
    discovery._convert_to_draft = _strict_convert_to_draft


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
