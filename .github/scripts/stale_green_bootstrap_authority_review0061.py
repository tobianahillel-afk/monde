from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0060 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_LATEST_REQUIRED_CHECK = previous._ORIGINAL_LATEST_REQUIRED_CHECK
_ORIGINAL_PROVE = previous._prove_candidate_attempt_frontier
_ORIGINAL_PROTECTED_GATE_JOB = previous._protected_gate_job


def _validate_attempt_job_chronology(run: dict[str, Any], job: dict[str, Any]) -> None:
    attempt_started = previous._run_attempt_started_at(run)
    job_started = core._timestamp(
        job.get("started_at"),
        "protected MONDE Gate job started_at",
    )
    if job_started < attempt_started:
        raise RuntimeError(
            "GitHub returned protected MONDE Gate job starting before current workflow attempt"
        )


def _chronology_protected_gate_job(
    repo: str,
    token: str,
    run: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    job = _ORIGINAL_PROTECTED_GATE_JOB(repo, token, run, head)
    _validate_attempt_job_chronology(run, job)
    return job


def _chronology_prove_candidate_attempt_frontier(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: Any,
) -> None:
    run_id, job_id = base._validate_gate_check(candidate, head)
    original_request = core.request_data
    direct_run: dict[str, Any] | None = None

    def guarded_request(url: str, request_token: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal direct_run
        payload = original_request(url, request_token, *args, **kwargs)
        if url == f"https://api.github.com/repos/{repo}/actions/runs/{run_id}":
            if isinstance(payload, dict):
                direct_run = payload
        elif url == f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}":
            if isinstance(payload, dict) and direct_run is not None:
                _validate_attempt_job_chronology(direct_run, payload)
        return payload

    core.request_data = guarded_request
    previous._protected_gate_job = _chronology_protected_gate_job
    try:
        _ORIGINAL_PROVE(repo, head, token, candidate, frontier)
    finally:
        previous._protected_gate_job = _ORIGINAL_PROTECTED_GATE_JOB
        core.request_data = original_request


def _chronology_latest_required_check(repo: str, head: str, token: str) -> dict[str, Any] | None:
    candidate = _ORIGINAL_LATEST_REQUIRED_CHECK(repo, head, token)
    if not base._latest_check_is_merge_acceptable(candidate):
        return candidate
    assert candidate is not None
    frontier = previous.previous._authority_frontier()
    _chronology_prove_candidate_attempt_frontier(repo, head, token, candidate, frontier)
    return candidate


def install() -> None:
    previous.install()
    core.latest_required_check = _chronology_latest_required_check


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
