from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0059 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_LATEST_REQUIRED_CHECK = previous._ORIGINAL_LATEST_REQUIRED_CHECK
_ACTIONS_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _run_attempt_started_at(run: dict[str, Any]) -> datetime:
    created = core._run_created_at(run)
    started = core._timestamp(run.get("run_started_at"), "canonical MONDE Gate run_started_at")
    updated = core._updated_at(run.get("updated_at"))
    if started < created or updated < started:
        raise RuntimeError("GitHub returned canonical MONDE Gate run with invalid attempt lifetime")
    return started


def _protected_gate_job(
    repo: str,
    token: str,
    run: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    run_id = run.get("id")
    if not core._positive_int(run_id):
        raise RuntimeError("GitHub returned malformed canonical MONDE Gate run id")
    attempt = base._validate_canonical_run(run, int(run_id), head, require_completed=False)
    jobs = core.paged(
        f"https://api.github.com/repos/{repo}/actions/runs/{int(run_id)}/jobs?filter=latest",
        token,
        "jobs",
        require_total_count=True,
        unique_id_field="id",
    )
    matches: list[dict[str, Any]] = []
    for job in jobs:
        if job.get("name") != core.REQUIRED_GATE_JOB_NAME:
            continue
        if (
            not core._positive_int(job.get("id"))
            or job.get("run_id") != run_id
            or job.get("run_attempt") != attempt
            or job.get("head_sha") != head
            or job.get("status") not in core.CHECK_RUN_STATUSES
        ):
            raise RuntimeError("GitHub returned malformed current protected MONDE Gate job")
        status = job.get("status")
        conclusion = job.get("conclusion")
        if status == "completed":
            if not isinstance(conclusion, str) or conclusion not in core.TERMINAL_CONCLUSIONS:
                raise RuntimeError("GitHub returned malformed completed current protected MONDE Gate job")
        elif conclusion is not None:
            raise RuntimeError("GitHub returned incomplete current protected MONDE Gate job with a conclusion")
        started = core._timestamp(job.get("started_at"), "protected MONDE Gate job started_at")
        completed_raw = job.get("completed_at")
        if status == "completed":
            completed = core._timestamp(completed_raw, "protected MONDE Gate job completed_at")
            if completed < started:
                raise RuntimeError("GitHub returned protected MONDE Gate job with invalid lifetime")
        elif completed_raw is not None:
            raise RuntimeError("GitHub returned incomplete current protected MONDE Gate job with completed_at")
        matches.append(job)
    if len(matches) != 1:
        raise RuntimeError(
            f"canonical workflow run {run_id} exposes {len(matches)} current "
            f"{core.REQUIRED_GATE_JOB_NAME!r} jobs; expected exactly one"
        )
    return matches[0]


def _attempt_frontier_runs(repo: str, head: str, token: str, frontier: datetime) -> list[dict[str, Any]]:
    return previous._bounded_frontier_runs(
        repo,
        head,
        token,
        _ACTIONS_EPOCH,
        core._utc_second(frontier),
    )


def _attempt_authority_key(job: dict[str, Any]) -> tuple[datetime, int]:
    job_id = job.get("id")
    if not core._positive_int(job_id):
        raise RuntimeError("GitHub returned malformed protected MONDE Gate job id")
    started = core._timestamp(job.get("started_at"), "protected MONDE Gate job started_at")
    return started, int(job_id)


def _prove_candidate_attempt_frontier(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: datetime,
) -> None:
    run_id, job_id = base._validate_gate_check(candidate, head)
    candidate_started = core._timestamp(
        candidate.get("started_at"),
        "required MONDE Merge Gate started_at",
    )
    frontier = core._utc_second(frontier)
    if candidate_started > frontier:
        raise RuntimeError("required-check authority frontier precedes candidate check start")

    direct_run = core.request_data(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
    if not isinstance(direct_run, dict):
        raise RuntimeError("GitHub returned malformed candidate canonical MONDE Gate run")
    direct_attempt = base._validate_canonical_run(
        direct_run, run_id, head, require_completed=False
    )
    direct_started = _run_attempt_started_at(direct_run)
    if direct_started > frontier:
        raise RuntimeError("candidate current workflow attempt started after authority frontier")

    direct_job = core.request_data(f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}", token)
    if not isinstance(direct_job, dict):
        raise RuntimeError("GitHub returned malformed candidate protected MONDE Gate job")
    base._validate_protected_job(
        direct_job,
        job_id=job_id,
        run_id=run_id,
        run_attempt=direct_attempt,
        head=head,
    )
    direct_job_started = core._timestamp(
        direct_job.get("started_at"),
        "candidate protected MONDE Gate job started_at",
    )
    if direct_job_started != candidate_started:
        raise RuntimeError("candidate required check disagrees with protected job start identity")
    if direct_job.get("conclusion") != candidate.get("conclusion"):
        raise RuntimeError("candidate required check disagrees with protected job conclusion")
    rows = _attempt_frontier_runs(repo, head, token, frontier)
    if not rows:
        raise RuntimeError("candidate canonical MONDE Gate run is absent from attempt frontier")

    authority: list[tuple[tuple[datetime, int], dict[str, Any], dict[str, Any]]] = []
    matched = 0
    for run in rows:
        row_id = run.get("id")
        if not core._positive_int(row_id):
            raise RuntimeError("GitHub returned malformed canonical MONDE Gate frontier run id")
        attempt = base._validate_canonical_run(
            run, int(row_id), head, require_completed=False
        )
        attempt_started = _run_attempt_started_at(run)
        if attempt_started > frontier:
            raise RuntimeError("canonical MONDE Gate current attempt started after authority frontier")

        job = _protected_gate_job(repo, token, run, head)
        job_started = core._timestamp(
            job.get("started_at"),
            "protected MONDE Gate job started_at",
        )
        if job_started > frontier:
            raise RuntimeError("canonical MONDE Gate protected job started after authority frontier")

        if int(row_id) == run_id:
            matched += 1
            if (
                run.get("run_number") != direct_run.get("run_number")
                or attempt != direct_attempt
                or core._run_created_at(run) != core._run_created_at(direct_run)
                or attempt_started != direct_started
                or int(job["id"]) != job_id
                or job_started != direct_job_started
            ):
                raise RuntimeError("candidate canonical MONDE Gate attempt changed during authority proof")
        authority.append((_attempt_authority_key(job), run, job))

    if matched != 1:
        raise RuntimeError("candidate canonical MONDE Gate run is absent or ambiguous in attempt frontier")

    latest_key, latest_run, latest_job = max(authority, key=lambda item: item[0])
    del latest_key
    if int(latest_run["id"]) != run_id or int(latest_job["id"]) != job_id:
        raise RuntimeError(
            "required-check authority advanced to a newer protected MONDE Gate job before the captured frontier"
        )


def _attempt_latest_required_check(repo: str, head: str, token: str) -> dict[str, Any] | None:
    candidate = _ORIGINAL_LATEST_REQUIRED_CHECK(repo, head, token)
    if not base._latest_check_is_merge_acceptable(candidate):
        return candidate
    assert candidate is not None
    frontier = previous._authority_frontier()
    _prove_candidate_attempt_frontier(repo, head, token, candidate, frontier)
    return candidate


def install() -> None:
    previous.install()
    core.latest_required_check = _attempt_latest_required_check


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
