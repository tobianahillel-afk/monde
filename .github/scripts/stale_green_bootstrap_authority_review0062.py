from __future__ import annotations

import os
from typing import Any

import stale_green_bootstrap as core
import stale_green_bootstrap_authority as base
import stale_green_bootstrap_authority_review0051_recovery as recovery
import stale_green_bootstrap_authority_review0061 as previous


RECOVERY_ACTION = recovery.RECOVERY_ACTION
_ORIGINAL_CHRONOLOGY_PROVE = previous._chronology_prove_candidate_attempt_frontier
_ORIGINAL_CHRONOLOGY_PROTECTED_GATE_JOB = previous._chronology_protected_gate_job


def _terminal_snapshot(job: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        job.get("status"),
        job.get("conclusion"),
        job.get("completed_at"),
    )


def _terminal_stability_prove(
    repo: str,
    head: str,
    token: str,
    candidate: dict[str, Any],
    frontier: Any,
) -> None:
    run_id, job_id = base._validate_gate_check(candidate, head)
    original_request = core.request_data
    original_chronology_job = previous._chronology_protected_gate_job
    direct_job: dict[str, Any] | None = None
    frontier_job: dict[str, Any] | None = None

    def guarded_request(url: str, request_token: str, *args: Any, **kwargs: Any) -> Any:
        nonlocal direct_job
        payload = original_request(url, request_token, *args, **kwargs)
        if url == f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}":
            if isinstance(payload, dict):
                direct_job = dict(payload)
        return payload

    def guarded_chronology_job(
        guarded_repo: str,
        request_token: str,
        run: dict[str, Any],
        guarded_head: str,
    ) -> dict[str, Any]:
        nonlocal frontier_job
        job = original_chronology_job(guarded_repo, request_token, run, guarded_head)
        if run.get("id") == run_id and job.get("id") == job_id:
            frontier_job = dict(job)
        return job

    core.request_data = guarded_request
    previous._chronology_protected_gate_job = guarded_chronology_job
    try:
        _ORIGINAL_CHRONOLOGY_PROVE(repo, head, token, candidate, frontier)
    finally:
        previous._chronology_protected_gate_job = original_chronology_job
        core.request_data = original_request

    if direct_job is None or frontier_job is None:
        raise RuntimeError(
            "candidate protected MONDE Gate job snapshot was not observed twice during authority proof"
        )
    if _terminal_snapshot(frontier_job) != _terminal_snapshot(direct_job):
        raise RuntimeError(
            "candidate protected MONDE Gate terminal state changed during authority proof"
        )


def install() -> None:
    previous.install()
    previous._chronology_prove_candidate_attempt_frontier = _terminal_stability_prove


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
