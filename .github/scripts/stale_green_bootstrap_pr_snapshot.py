from __future__ import annotations

from typing import Any

import stale_green_bootstrap as core

_ORIGINAL_OPEN_PULL_REQUESTS = core.open_pull_requests
_ORIGINAL_CLOSED_PR_HISTORY = core._closed_pr_history


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


def open_pull_requests(repo: str, token: str) -> list[dict[str, Any]]:
    first = _ORIGINAL_OPEN_PULL_REQUESTS(repo, token)
    second = _ORIGINAL_OPEN_PULL_REQUESTS(repo, token)
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


def install() -> None:
    core.open_pull_requests = open_pull_requests
    core._closed_pr_history = closed_pr_history


def main() -> int:
    install()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
