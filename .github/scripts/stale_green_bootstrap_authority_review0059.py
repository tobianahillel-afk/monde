from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import urllib.parse
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0056 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_LATEST_REQUIRED_CHECK = core.latest_required_check


def _authority_frontier() -> datetime:
    return core._utc_second(datetime.now(timezone.utc))


def _read_frontier_window(
    repo: str,
    head: str,
    token: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    created_range = f"{core._github_search_time(start)}..{core._github_search_time(end)}"
    query = urllib.parse.urlencode({"head_sha": head, "created": created_range})
    return core.paged(
        f"https://api.github.com/repos/{repo}/actions/workflows/{core.CANONICAL_WORKFLOW_ID}/runs?{query}",
        token,
        "workflow_runs",
        require_total_count=True,
        max_total_count=core.FILTERED_WORKFLOW_RUN_SEARCH_LIMIT,
        unique_id_field="id",
    )


def _bounded_frontier_runs(
    repo: str,
    head: str,
    token: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    start = core._utc_second(start)
    end = core._utc_second(end)
    if end < start:
        raise RuntimeError("required-check authority frontier precedes candidate run creation")
    try:
        return _read_frontier_window(repo, head, token, start, end)
    except core.FilteredSearchLimitExceeded:
        if start == end:
            raise RuntimeError(
                "canonical MONDE Gate frontier reaches GitHub search limit within one timestamp second"
            )
        span_seconds = int((end - start).total_seconds())
        midpoint = start + timedelta(seconds=span_seconds // 2)
        right_start = midpoint + timedelta(seconds=1)
        left = _bounded_frontier_runs(repo, head, token, start, midpoint)
        right = _bounded_frontier_runs(repo, head, token, right_start, end)
        ids = [row.get("id") for row in left + right]
        if any(not core._positive_int(value) for value in ids) or len(ids) != len(set(ids)):
            raise RuntimeError("canonical MONDE Gate frontier returned duplicate or malformed run identity")
        return left + right


def _frontier_run_key(run: dict[str, Any], head: str) -> tuple[datetime, int, int]:
    run_id = run.get("id")
    if not core._positive_int(run_id):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate frontier run id")
    base._validate_canonical_run(run, run_id, head, require_completed=False)
    run_number = run.get("run_number")
    if not core._positive_int(run_number):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate frontier run number")
    return (core._run_created_at(run), int(run_number), int(run_id))


def _prove_candidate_frontier(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: datetime,
) -> None:
    run_id, job_id = base._validate_gate_check(candidate, head)

    run = core.request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
    if not isinstance(run, dict):
        raise RuntimeError("GitHub returned malformed candidate canonical MONDE Gate run")
    run_attempt = base._validate_canonical_run(run, run_id, head, require_completed=False)

    job = core.request_data(f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}", token)
    if not isinstance(job, dict):
        raise RuntimeError("GitHub returned malformed candidate protected MONDE Gate job")
    base._validate_protected_job(
        job,
        job_id=job_id,
        run_id=run_id,
        run_attempt=run_attempt,
        head=head,
    )
    if job.get("conclusion") != candidate.get("conclusion") or job.get("status") != candidate.get("status"):
        raise RuntimeError("candidate required check disagrees with its protected Actions job")

    candidate_created = core._run_created_at(run)
    frontier = core._utc_second(frontier)
    if candidate_created > frontier:
        raise RuntimeError("required-check authority frontier precedes candidate run creation")

    rows = _bounded_frontier_runs(repo, head, token, candidate_created, frontier)
    if not rows:
        raise RuntimeError("candidate canonical MONDE Gate run is absent from authority frontier")

    keyed = [(_frontier_run_key(item, head), item) for item in rows]
    matches = [item for _key, item in keyed if int(item["id"]) == run_id]
    if len(matches) != 1:
        raise RuntimeError("candidate canonical MONDE Gate run is ambiguous in authority frontier")
    frontier_candidate = matches[0]
    if (
        frontier_candidate.get("run_number") != run.get("run_number")
        or frontier_candidate.get("run_attempt") != run_attempt
        or core._run_created_at(frontier_candidate) != candidate_created
    ):
        raise RuntimeError("candidate canonical MONDE Gate run changed during authority proof")

    latest_key, latest_run = max(keyed, key=lambda item: item[0])
    if int(latest_run["id"]) != run_id:
        raise RuntimeError(
            "required-check authority advanced to a newer canonical MONDE Gate run before the captured frontier"
        )
    if latest_key != _frontier_run_key(run, head):
        raise RuntimeError("candidate canonical MONDE Gate run disagrees with authority frontier")


def _frontier_latest_required_check(repo: str, head: str, token: str) -> dict[str, Any] | None:
    candidate = _ORIGINAL_LATEST_REQUIRED_CHECK(repo, head, token)
    if not base._latest_check_is_merge_acceptable(candidate):
        return candidate
    assert candidate is not None
    frontier = _authority_frontier()
    _prove_candidate_frontier(repo, head, token, candidate, frontier)
    return candidate


def install() -> None:
    previous.install()
    core.latest_required_check = _frontier_latest_required_check


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
