from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0061 as chronology
import stale_green_bootstrap_authority_review0062 as terminal
import stale_green_bootstrap_authority_review0063 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_ACTIVE_LATEST = chronology._chronology_latest_required_check
_ORIGINAL_TERMINAL_PROVE = terminal._terminal_stability_prove


def _required_check_temporal_snapshot(
    check: dict[str, Any],
) -> tuple[Any, Any | None]:
    started = core._timestamp(
        check.get("started_at"),
        "required MONDE Merge Gate started_at",
    )
    completed_raw = check.get("completed_at")
    if check.get("status") == "completed":
        completed = core._timestamp(
            completed_raw,
            "required MONDE Merge Gate completed_at",
        )
        if completed < started:
            raise RuntimeError(
                "GitHub returned completed required MONDE Merge Gate check completing before it started"
            )
        return started, completed
    if completed_raw is not None:
        raise RuntimeError(
            "GitHub returned incomplete required MONDE Merge Gate check with completed_at"
        )
    return started, None


def _temporal_latest_required_check(
    repo: str,
    head: str,
    token: str,
) -> dict[str, Any] | None:
    original_paged = core.paged

    def guarded_paged(url: str, *args: Any, **kwargs: Any) -> Any:
        rows = original_paged(url, *args, **kwargs)
        if "/check-runs?" in url and "filter=latest" in url:
            for row in rows:
                _required_check_temporal_snapshot(row)
        return rows

    core.paged = guarded_paged
    try:
        return _ORIGINAL_ACTIVE_LATEST(repo, head, token)
    finally:
        core.paged = original_paged


def _temporal_prove_candidate_attempt_frontier(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: Any,
) -> None:
    check_started, check_completed = _required_check_temporal_snapshot(candidate)
    if check_completed is None:
        raise RuntimeError("merge-acceptable required check lacks terminal completion")
    normalized_frontier = core._utc_second(frontier)
    if check_completed > normalized_frontier:
        raise RuntimeError(
            "required-check authority frontier precedes candidate check completion"
        )

    _run_id, job_id = base._validate_gate_check(candidate, head)
    original_request = core.request_data
    direct_job: dict[str, Any] | None = None

    def guarded_request(url: str, request_token: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal direct_job
        payload = original_request(url, request_token, *args, **kwargs)
        if url == f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}":
            if isinstance(payload, dict):
                direct_job = dict(payload)
        return payload

    core.request_data = guarded_request
    try:
        _ORIGINAL_TERMINAL_PROVE(repo, head, token, candidate, frontier)
    finally:
        core.request_data = original_request

    if direct_job is None:
        raise RuntimeError(
            "candidate protected MONDE Gate job timing was not observed during authority proof"
        )
    job_started = core._timestamp(
        direct_job.get("started_at"),
        "candidate protected MONDE Gate job started_at",
    )
    job_completed = core._timestamp(
        direct_job.get("completed_at"),
        "candidate protected MONDE Gate job completed_at",
    )
    if job_started != check_started:
        raise RuntimeError(
            "candidate required check disagrees with protected job start timing"
        )
    if job_completed != check_completed:
        raise RuntimeError(
            "candidate required check disagrees with protected job completion timing"
        )


def install() -> None:
    previous.install()
    chronology._chronology_prove_candidate_attempt_frontier = (
        _temporal_prove_candidate_attempt_frontier
    )
    core.latest_required_check = _temporal_latest_required_check


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
